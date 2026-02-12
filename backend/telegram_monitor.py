"""
Telegram Channel Monitor for Kyzylorda Incident Dashboard

This script monitors a Telegram channel for new messages and automatically
sends them to the FastAPI /parse-news endpoint for AI parsing.
"""

import asyncio
import os
import sys
from datetime import datetime

import requests
from telethon import TelegramClient, events
from dotenv import load_dotenv


load_dotenv()

# Telegram API credentials (get from https://my.telegram.org)
API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
# Channel username or ID to monitor (e.g., "@kyzylorda_news" or "-1001234567890")
CHANNEL_USERNAME = os.getenv("TELEGRAM_CHANNEL")
# FastAPI backend URL
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# File to store session (so you don't need to login every time)
SESSION_NAME = "telegram_monitor_session"


def parse_news_via_api(text: str) -> dict:
    """
    Send news text to the FastAPI /parse-news endpoint.
    Returns the parsed incident data.
    """
    try:
        response = requests.post(
            f"{BACKEND_URL}/parse-news",
            json={"text": text},
            timeout=120,
        )
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Parsed: {data.get('location')} - {data.get('event_type')}")
            return data
        else:
            print(f"✗ API error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"✗ Failed to call API: {e}")
        return None


def broadcast_incident(incident_data: dict) -> bool:
    """
    Broadcast the parsed incident to all connected WebSocket clients.
    """
    try:
        response = requests.post(
            f"{BACKEND_URL}/broadcast-incident",
            json=incident_data,
            timeout=5,
        )
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Broadcasted to {result.get('connections', 0)} WebSocket clients")
            return True
        else:
            print(f"✗ Broadcast failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Failed to broadcast: {e}")
        return False


async def main():
    """
    Main function: connects to Telegram and monitors the channel.
    """
    if not API_ID or not API_HASH:
        print("ERROR: TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in .env")
        print("Get them from https://my.telegram.org/apps")
        sys.exit(1)

    if not CHANNEL_USERNAME:
        print("ERROR: TELEGRAM_CHANNEL must be set in .env")
        print("Example: TELEGRAM_CHANNEL=@kyzylorda_news")
        sys.exit(1)

    # Create Telegram client
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

    print("Starting Telegram monitor...")
    print(f"Monitoring channel: {CHANNEL_USERNAME}")
    print(f"Sending parsed data to: {BACKEND_URL}/parse-news")
    print("-" * 60)

    @client.on(events.NewMessage(chats=CHANNEL_USERNAME))
    async def handler(event):
        """
        Called when a new message is posted in the channel.
        """
        message_text = event.message.text
        if not message_text or len(message_text.strip()) < 10:
            # Ignore empty or very short messages
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{timestamp}] New message from {CHANNEL_USERNAME}:")
        print(f"  {message_text[:100]}...")

        # Send to /parse-news endpoint
        parsed = parse_news_via_api(message_text)
        if parsed:
            print(f"  → Location: {parsed.get('location')}")
            print(f"  → Type: {parsed.get('event_type')}")
            print(f"  → Severity: {parsed.get('severity')}")
            print(f"  → Coordinates: {parsed.get('coordinates')}")
            
            # Broadcast to WebSocket clients for real-time updates
            broadcast_incident(parsed)

    # Connect and start listening
    await client.start()
    print("Connected! Listening for new messages...")
    print("Press Ctrl+C to stop.\n")

    # Keep the script running
    await client.run_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nStopped by user.")
