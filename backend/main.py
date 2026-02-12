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
# Default to a newer flash model; the code expects just the short name here,
# e.g. "gemini-2.5-flash" (without the "models/" prefix).
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_URL = (
    f"https://generativelanguage.googleapis.com/v1/models/{GEMINI_MODEL}:generateContent"
)


def build_prompt(text: str) -> str:
    return f"""
You are a precise geolocation assistant for the city of Kyzylorda, Kazakhstan. Your task is to read a short news-style incident report
and extract structured information suitable for a city incident map.

CRITICAL GEOGRAPHIC CONTEXT FOR KYZYLORDA:
Kyzylorda is located at approximately 44.8488°N, 65.4823°E. The city's urban area spans:
- Latitude range: 44.78 to 44.87
- Longitude range: 65.45 to 65.55

MAJOR STREETS IN KYZYLORDA (use these as reference when estimating coordinates):
- Qorqyt Ata street (Коркыт Ата): central, around 44.847, 65.522
- Aiteke bi street (Айтеке би): central, around 44.847, 65.517
- Auezov street (Ауэзова): central, around 44.848, 65.496
- Abai avenue (проспект Абая): eastern area, around 44.832, 65.508
- Zhibek zholy street (Жибек жолы): southern, around 44.782, 65.534

RULES FOR COORDINATE ESTIMATION:
- If you recognize a major street from the list above, use coordinates close to the reference point.
- For unknown streets, make an educated guess based on typical city street patterns:
  * North side: lat 44.85-44.87, lng 65.48-65.53
  * Central area: lat 44.84-44.85, lng 65.49-65.52
  * South side: lat 44.78-44.82, lng 65.50-65.54
- Distribute coordinates reasonably - don't place multiple different streets at exactly the same point.
- Use slight variations (0.003-0.008 degrees) for different streets to create realistic spread.
- NEVER place coordinates outside the city bounds (44.78-44.87, 65.45-65.55)
- If the text does not specify duration, set duration to "unknown".
- Choose severity from: "low", "medium", "high", "critical".

Return ONLY a single JSON object with the following shape:
{{
  "location": "string – street / intersection / district name",
  "event_type": "string – normalized event type such as 'repair', 'emergency', 'road_work', 'accident'",
  "severity": "low | medium | high | critical",
  "duration": "string – human readable duration estimate, or 'unknown'",
  "coordinates": {{
    "lat": float,   // precise latitude within Kyzylorda bounds
    "lng": float    // precise longitude within Kyzylorda bounds
  }}
}}

IMPORTANT:
- The coordinates MUST be within Kyzylorda city bounds (lat 44.78-44.87, lng 65.45-65.55).
- Do not add any extra fields.
- Do not add any explanation text, markdown, or comments – only raw JSON.

NEWS TEXT:
\"\"\"{text}\"\"\""""


def _extract_json(text: str) -> dict:
    """
    Extract a JSON object from the model text response.
    Handles cases where the response is wrapped in ```json ... ``` fences.
    """
    text = text.strip()
    if text.startswith("```"):
        # Remove first and last fenced lines
        lines = text.splitlines()
        # drop first and last fence lines
        inner = "\n".join(lines[1:-1]).strip()
        text = inner
    return json.loads(text)


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
        ]
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

