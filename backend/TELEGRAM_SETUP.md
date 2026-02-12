# Telegram Channel Monitor Setup

This guide explains how to connect your dashboard to a Telegram channel so it automatically parses new incident reports.

## How it works

1. `telegram_monitor.py` connects to Telegram and listens to a specific channel
2. When a new message appears, it sends the text to `http://localhost:8000/parse-news`
3. The AI parses it and extracts: location, event type, severity, duration, coordinates
4. The parsed data can be saved to a database or pushed to the frontend

---

## Setup Steps

### 1. Get Telegram API Credentials

1. Go to https://my.telegram.org/apps
2. Log in with your phone number
3. Click **"API development tools"**
4. Create a new application (any name/description is fine)
5. Copy the **`api_id`** and **`api_hash`**

### 2. Find the Channel Username

- If the channel is public: use the username like `@kyzylorda_news`
- If the channel is private: you'll need the channel ID (looks like `-1001234567890`)
  - To get the ID, forward a message from the channel to @userinfobot on Telegram

### 3. Configure Environment Variables

Create a `.env` file in the `backend` folder:

```bash
cd C:\Users\Lenovo\Desktop\Hakaton\backend
copy .env.example .env
```

Edit `.env` and fill in:

```env
# Your Gemini key (already set)
GOOGLE_API_KEY=your_gemini_key_here
GEMINI_MODEL=gemini-2.5-flash

# Telegram credentials from step 1
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890

# Channel to monitor from step 2
TELEGRAM_CHANNEL=@kyzylorda_news

# Backend URL (leave as-is if running locally)
BACKEND_URL=http://localhost:8000
```

### 4. Install Dependencies

```bash
cd C:\Users\Lenovo\Desktop\Hakaton\backend
pip install -r requirements.txt
```

### 5. Run the Services

You need **three** terminal windows:

**Terminal 1 - Backend API:**
```bash
cd C:\Users\Lenovo\Desktop\Hakaton\backend
python -m uvicorn main:app --reload
```

**Terminal 2 - Telegram Monitor:**
```bash
cd C:\Users\Lenovo\Desktop\Hakaton\backend
python telegram_monitor.py
```
- First time: it will ask for your **phone number** and **login code** (sent via Telegram)
- After login, it saves the session so you won't need to login again

**Terminal 3 - Frontend:**
```bash
cd C:\Users\Lenovo\Desktop\Hakaton\kyzylorda-dashboard
npm run dev
```

---

## Usage

Once running:

1. Post a message in your Telegram channel (or wait for a new post)
2. `telegram_monitor.py` will detect it and send it to `/parse-news`
3. The console will show:
   ```
   [2026-02-12 15:30:45] New message from @kyzylorda_news:
     В центре Кызылорды на улице Абая произошла авария...
   ✓ Parsed: Qorqyt Ata Street - accident
     → Location: Qorqyt Ata Street
     → Type: accident
     → Severity: high
     → Coordinates: {'lat': 44.847, 'lng': 65.522}
   ```

4. **To add it to the live map**, you can:
   - Manually refresh the frontend (it doesn't auto-update yet)
   - Or extend the code to save to a database / push via WebSocket

---

## Next Steps (Optional)

### Option A: Auto-add to the map (database approach)

1. Add SQLite/PostgreSQL to store parsed incidents
2. Frontend fetches from database instead of mock `events.js`
3. Telegram monitor saves parsed data to database

### Option B: Real-time updates (WebSocket approach)

1. Add WebSocket endpoint to FastAPI
2. Frontend connects to WebSocket
3. Telegram monitor broadcasts new incidents via WebSocket
4. Frontend auto-adds markers without refresh

### Option C: Webhook approach (for deployment)

1. Deploy backend to a public server (e.g., Railway, Render)
2. Register a Telegram webhook pointing to your server
3. No need to keep `telegram_monitor.py` running 24/7

---

## Troubleshooting

**"TELEGRAM_API_ID and TELEGRAM_API_HASH must be set"**
- Make sure you created a `.env` file (not `.env.example`)
- Check that the values are correct (no quotes needed)

**"Could not find the input entity for ..."**
- The channel username is wrong or you're not a member
- Try using the channel ID instead of username

**"Phone number is invalid"**
- Use international format: `+77001234567` (with country code)

**"The API key is invalid"**
- Your Gemini key is wrong or expired
- Check `GOOGLE_API_KEY` in `.env`

---

## Security Notes

- **Never commit `.env` to git** (it's already in `.gitignore`)
- Keep your `TELEGRAM_API_HASH` and `GOOGLE_API_KEY` private
- The `telegram_monitor_session.session` file contains your login; keep it safe
