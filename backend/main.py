import json
import os
from typing import Literal, Optional, List

import requests
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv


load_dotenv()

app = FastAPI(title="Kyzylorda Incident Parser API")


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"✓ WebSocket client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        print(f"✗ WebSocket client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients."""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Failed to send to WebSocket client: {e}")


manager = ConnectionManager()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "*",  # loosen as needed
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class NewsRequest(BaseModel):
    text: str = Field(..., description="Raw news text from a channel / feed.")


class Coordinates(BaseModel):
    lat: float = Field(..., description="Approximate latitude within Kyzylorda.")
    lng: float = Field(..., description="Approximate longitude within Kyzylorda.")


Severity = Literal["low", "medium", "high", "critical"]


class ParsedNews(BaseModel):
    location: str = Field(
        ..., description="Street, intersection, or district mentioned in the news."
    )
    event_type: str = Field(
        ...,
        description="Canonical event type, e.g. 'repair', 'emergency', 'road_work', 'accident'.",
    )
    severity: Severity = Field(
        ..., description="Overall severity level: low, medium, high, or critical."
    )
    duration: str = Field(
        ...,
        description="Human-readable estimated duration (e.g. '30 minutes', '2-3 hours', 'unknown').",
    )
    coordinates: Coordinates
    # Optional raw model output for debugging / future tuning
    raw_model_response: Optional[dict] = None


GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
# Use flash model - good balance of speed and accuracy
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_URL = (
    f"https://generativelanguage.googleapis.com/v1/models/{GEMINI_MODEL}:generateContent"
)


def build_prompt(text: str) -> str:
    return f"""
You are an assistant for the city of Kyzylorda, Kazakhstan. Your task is to read a short news-style incident report
and extract structured information suitable for a city incident map.

RULES:
- Assume ALL incidents occur in or near Kyzylorda city.
- If the location is vague (e.g. 'downtown', 'city center'), infer a reasonable location within Kyzylorda.
- For coordinates, choose an approximate point that lies within the urban area of Kyzylorda.
- If the text does not specify duration, set duration to "unknown".
- Choose severity from: "low", "medium", "high", "critical".

EXAMPLE OUTPUT (copy this format exactly):
{{"location": "Abay Street", "event_type": "road_work", "severity": "medium", "duration": "2 hours", "coordinates": {{"lat": 44.85, "lng": 65.48}}}}

STRICT JSON RULES:
1. Return ONLY the JSON object - NO explanation text before or after
2. Use double quotes for ALL strings
3. DO NOT add comments (no // or /* */)
4. DO NOT add trailing commas
5. DO NOT use markdown code fences (no ```)
6. Coordinates MUST be in Kyzylorda (lat: 44.84-44.87, lng: 65.45-65.52)
7. event_type options: "road_work", "accident", "emergency", "repair", "road_closure"
8. severity options: "low", "medium", "high", "critical"

NEWS TEXT:
\"\"\"{text}\"\"\""""


def _extract_json(text: str) -> dict:
    """
    Extract a JSON object from the model text response.
    Handles cases where the response is wrapped in ```json ... ``` fences or has comments.
    """
    import re
    
    original_text = text
    text = text.strip()
    
    # Remove markdown code fences
    if text.startswith("```"):
        lines = text.splitlines()
        # Remove first line (```json or ```)
        if lines:
            lines = lines[1:]
        # Remove last line (```)
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    
    # Remove inline comments that break JSON parsing
    # Remove // comments
    text = re.sub(r'//[^\n]*', '', text)
    # Remove /* */ comments
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    # Remove trailing commas before } or ]
    text = re.sub(r',(\s*[}\]])', r'\1', text)
    
    # Try to extract JSON object if there's extra text
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        text = json_match.group(0)
    
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"❌ JSON parse error: {e}")
        print(f"📄 Original text (first 500 chars):\n{original_text[:500]}")
        print(f"🧹 Cleaned text (first 500 chars):\n{text[:500]}")
        raise


def parse_with_gemini(text: str) -> ParsedNews:
    if not GEMINI_API_KEY:
        raise ValueError("GOOGLE_API_KEY (or GEMINI_API_KEY) is not set.")

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": build_prompt(text),
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "topP": 0.95,
            "topK": 40,
            "maxOutputTokens": 512,
            "candidateCount": 1
        }
    }

    resp = requests.post(
        GEMINI_API_URL,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_API_KEY,
        },
        json=payload,
        timeout=30,
    )

    if resp.status_code != 200:
        raise ValueError(f"Gemini API error {resp.status_code}: {resp.text}")

    resp_json = resp.json()
    try:
        model_text = resp_json["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as exc:
        raise ValueError(f"Unexpected Gemini response: {resp_json}") from exc

    data = _extract_json(model_text)
    return ParsedNews(
        **data,
        raw_model_response={
            "provider": "gemini",
            "model": GEMINI_MODEL,
        },
    )


@app.post("/parse-news", response_model=ParsedNews)
async def parse_news(payload: NewsRequest) -> ParsedNews:
    """
    Parse a raw news string into structured incident data that can be rendered on the Kyzylorda map.
    """
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Text must not be empty.")

    try:
        return parse_with_gemini(payload.text)
    except Exception as exc:
        # In a real system, log full details to your logging solution.
        raise HTTPException(
            status_code=500, detail=f"Failed to parse news text: {exc}"
        ) from exc


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time incident updates.
    Frontend connects here to receive new parsed incidents instantly.
    """
    await manager.connect(websocket)
    try:
        # Keep connection alive
        while True:
            # Wait for any message from client (just to keep connection alive)
            data = await websocket.receive_text()
            # Echo back as confirmation
            await websocket.send_json({"type": "ping", "status": "connected"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.post("/broadcast-incident")
async def broadcast_incident(incident: dict):
    """
    Internal endpoint for telegram_monitor.py to broadcast new incidents.
    """
    await manager.broadcast({"type": "new_incident", "data": incident})
    return {"status": "broadcasted", "connections": len(manager.active_connections)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))

