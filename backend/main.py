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


# Geocoding via Nominatim
def geocode_street(location: str) -> Optional[dict]:
    """
    Get coordinates for a street in Kyzylorda using OpenStreetMap Nominatim.
    Returns {"lat": float, "lng": float} or None if not found.
    """
    try:
        # Try multiple search strategies
        search_queries = [
            f"{location}, Кызылорда, Казахстан",
            f"{location}, Kyzylorda, Kazakhstan",
            f"{location.replace('улица', '').strip()}, Кызылорда",
            f"{location.replace('street', '').strip()}, Kyzylorda",
        ]
        
        for query in search_queries:
            url = "https://nominatim.openstreetmap.org/search"
            params = {
                "q": query,
                "format": "json",
                "limit": 1,
                "addressdetails": 1,
            }
            headers = {
                "User-Agent": "KyzylordaDashboard/1.0"
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data:
                    result = data[0]
                    lat = float(result["lat"])
                    lon = float(result["lon"])
                    
                    # Verify it's in Kyzylorda area (rough bounds)
                    if 44.7 < lat < 45.0 and 65.3 < lon < 65.7:
                        print(f"✓ Geocoded '{location}' → ({lat}, {lon})")
                        return {"lat": lat, "lng": lon}
        
        # If all queries fail, return city center
        print(f"⚠ Geocoding failed for '{location}' - using city center")
        return {"lat": 44.8488, "lng": 65.4823}
        
    except Exception as e:
        print(f"❌ Geocoding error: {e}")
        return {"lat": 44.8488, "lng": 65.4823}


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
You are an assistant for Kyzylorda city, Kazakhstan. Extract incident information from news text.

EXAMPLE OUTPUT (copy this format exactly):
{{"location": "улица Абая", "event_type": "road_work", "severity": "medium", "duration": "2 hours"}}

RULES:
1. Extract the EXACT street/location name from the text (keep it in original language - Russian or Kazakh)
2. event_type options: "road_work", "accident", "emergency", "repair", "road_closure"
3. severity options: "low", "medium", "high", "critical"
4. duration: extract from text or "unknown"
5. Return ONLY valid JSON - no comments, no markdown, no extra text

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
    
    # Get real coordinates from Nominatim instead of relying on Gemini
    location = data.get("location", "")
    coordinates = geocode_street(location)
    
    # Add coordinates to data
    data["coordinates"] = coordinates
    
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

