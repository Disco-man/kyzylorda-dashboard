import json
import os
import re
from typing import Literal, Optional, List

import requests
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Kyzylorda Incident Parser API")

# --- 1. GEOCODING SERVICE (REAL MAP DATA) ---
def geocode_street(location: str) -> dict:
    """
    Превращает название улицы в координаты через OpenStreetMap.
    """
    # Очищаем название от лишнего мусора, чтобы поиск работал лучше
    clean_loc = location.replace("улица", "").replace("просп.", "").strip()
    
    queries = [
        f"{location}, Кызылорда",          # Полный запрос
        f"{clean_loc}, Кызылорда",         # Без типа улицы
        f"{clean_loc}, Kyzylorda",         # На латинице
    ]

    headers = {"User-Agent": "KyzylordaHackathon/1.0"}

    print(f"🔍 Searching coords for: {location}")

    for q in queries:
        try:
            url = "https://nominatim.openstreetmap.org/search"
            resp = requests.get(url, params={"q": q, "format": "json", "limit": 1}, headers=headers, timeout=3)
            if resp.status_code == 200 and resp.json():
                data = resp.json()[0]
                lat, lng = float(data["lat"]), float(data["lon"])
                
                # Проверка, что мы внутри Кызылорды (примерно)
                if 44.70 < lat < 44.95 and 65.40 < lng < 65.65:
                    print(f"✅ Found: {lat}, {lng}")
                    return {"lat": lat, "lng": lng}
        except Exception:
            continue

    # Если не нашли — возвращаем центр города (но со смещением, чтобы точки не слипались)
    print("⚠️ Coordinates not found, using default center")
    import random
    base_lat, base_lng = 44.8488, 65.4823
    # Добавляем микро-шум, чтобы точки не лежали одна на другой
    return {
        "lat": base_lat + random.uniform(-0.005, 0.005), 
        "lng": base_lng + random.uniform(-0.005, 0.005)
    }

# --- 2. WEBSOCKET MANAGER ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Разрешаем всем для хакатона
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 3. MODELS ---
class NewsRequest(BaseModel):
    text: str

class Coordinates(BaseModel):
    lat: float
    lng: float

class ParsedNews(BaseModel):
    location: str
    event_type: str
    severity: str
    duration: str
    summary: str # Краткое описание для попапа
    coordinates: Coordinates

# --- 4. AI LOGIC ---
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

def clean_json_string(text: str) -> str:
    """Очищает ответ ИИ от markdown и комментариев"""
    # Удаляем ```json и ```
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```', '', text)
    # Ищем текст от первой { до последней }
    match = re.search(r'(\{.*\})', text, re.DOTALL)
    if match:
        return match.group(1)
    return text

def parse_with_gemini(news_text: str) -> dict:
    prompt = f"""
    You are a smart city assistant for Kyzylorda.
    Analyze the following news text and extract structured data.
    
    TEXT: "{news_text}"

    RETURN JSON ONLY using this structure (NO null values allowed):
    {{
        "location_search_query": "Name of the street or place in Russian for map search (e.g. 'улица Абая')",
        "event_type": "One of: repair, accident, road_closed, event, other",
        "severity": "One of: low, medium, high",
        "duration": "Estimated duration as STRING (e.g. '2 часа', 'до вечера', 'неизвестно')",
        "summary": "Short title for the map popup (max 5 words, Russian)"
    }}
    
    IMPORTANT: If duration is not specified in text, use "неизвестно" instead of null.
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    
    resp = requests.post(GEMINI_URL, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
    
    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail=f"AI Error: {resp.text}")
        
    try:
        raw_text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        json_str = clean_json_string(raw_text)
        return json.loads(json_str)
    except Exception as e:
        print(f"❌ JSON Parse Error. Raw text: {raw_text}")
        raise HTTPException(status_code=500, detail="Failed to parse AI response")

# --- 5. ENDPOINTS ---

@app.post("/parse-news", response_model=ParsedNews)
async def parse_news(payload: NewsRequest):
    # 1. Спрашиваем ИИ (получаем адрес текстом)
    ai_data = parse_with_gemini(payload.text)
    
    # 2. Ищем реальные координаты через OpenStreetMap
    search_query = ai_data.get("location_search_query", "Kyzylorda")
    coords = geocode_street(search_query)
    
    # 3. Собираем итоговый ответ
    return ParsedNews(
        location=ai_data.get("location_search_query") or "Неизвестно",
        event_type=ai_data.get("event_type") or "other",
        severity=ai_data.get("severity") or "low",
        duration=ai_data.get("duration") or "неизвестно",
        summary=ai_data.get("summary") or "Событие",
        coordinates=Coordinates(lat=coords["lat"], lng=coords["lng"])
    )

@app.post("/broadcast-incident")
async def broadcast_incident(incident: ParsedNews):
    """
    Endpoint for Telegram monitor to broadcast parsed incidents to all WebSocket clients.
    """
    # Wrap in expected format for frontend
    message = {
        "type": "new_incident",
        "data": incident.model_dump() if hasattr(incident, 'model_dump') else incident.dict()
    }
    await manager.broadcast(message)
    print(f"✅ Broadcasted incident to {len(manager.active_connections)} clients")
    return {"status": "broadcasted", "clients": len(manager.active_connections)}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text() # keep alive
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

