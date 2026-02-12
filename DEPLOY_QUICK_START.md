# 🚀 Quick Deploy Guide (5 Minutes)

Make your Kyzylorda Dashboard public in 3 steps!

---

## Step 1: Push to GitHub (2 min)

```bash
cd C:\Users\Lenovo\Desktop\Hakaton

# Initialize git if not already done
git init
git add .
git commit -m "Initial commit - Kyzylorda Dashboard"

# Create GitHub repo (requires GitHub CLI)
gh auth login
gh repo create kyzylorda-dashboard --public --source=. --remote=origin --push
```

**Or manually**: Go to https://github.com/new → Create repo → Follow GitHub's push instructions

---

## Step 2: Deploy Backend (2 min)

### Option A: Railway (Easiest)

1. Go to https://railway.app
2. Click **"Start a New Project"** → **"Deploy from GitHub repo"**
3. Select `kyzylorda-dashboard` repo → Select `backend` folder
4. Click **"Add Variables"** → Add these:
   ```
   GOOGLE_API_KEY=AIzaSyC8yPsQsia4i35Q5c4AefyEz-j_y5eohUg
   GEMINI_MODEL=gemini-2.5-flash
   TELEGRAM_API_ID=35715704
   TELEGRAM_API_HASH=78b479c9a92a73114a37bf37c37dbc7e
   TELEGRAM_CHANNEL=@kyzylordanew
   ```
5. Click **"Deploy"**
6. Wait 2-3 minutes
7. Copy your URL: `https://YOUR-PROJECT.railway.app`

### Option B: Render

1. Go to https://render.com
2. **New** → **Web Service** → Connect GitHub
3. Select `backend` folder
4. Runtime: **Python 3**
5. Build: `pip install -r requirements.txt`
6. Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
7. Add same environment variables
8. Click **"Create Web Service"**

---

## Step 3: Deploy Frontend (1 min)

**First, update the WebSocket URL:**

Edit `kyzylorda-dashboard/src/App.jsx`, find line ~151:
```javascript
const ws = new WebSocket("ws://localhost:8000/ws");
```

**Replace with your Railway URL** (use `wss://` for secure):
```javascript
const ws = new WebSocket("wss://YOUR-PROJECT.railway.app/ws");
```

Save and commit:
```bash
cd kyzylorda-dashboard
git add .
git commit -m "Update WebSocket URL for production"
git push
```

### Deploy to Vercel:

1. Go to https://vercel.com
2. Click **"Add New"** → **"Project"**
3. Import `kyzylorda-dashboard` from GitHub
4. Framework preset: **Vite**
5. Root Directory: **`kyzylorda-dashboard`**
6. Click **"Deploy"**
7. Wait 1 minute
8. Get your URL: `https://YOUR-PROJECT.vercel.app`

---

## ✅ Done! Test It

1. Open your Vercel URL: `https://YOUR-PROJECT.vercel.app`
2. Press **F12** → Console should show: `✓ WebSocket connected`
3. Post a test message to [@kyzylordanew](https://t.me/kyzylordanew):
   ```
   Тестовое сообщение: Авария на улице Коркыт Ата
   ```
4. Watch it appear on the map in ~10-20 seconds!

---

## Share Your Dashboard! 🎉

**Your public URL**: `https://YOUR-PROJECT.vercel.app`

Anyone can now:
- ✅ View live incidents on the map
- ✅ Search streets
- ✅ See real-time updates from Telegram
- ✅ Filter by timeline
- ✅ Use the AI news parser

---

## Optional: Add Telegram Monitor Worker

**On Railway** (to keep Telegram monitoring 24/7):

1. In your Railway project
2. Click **"New"** → **"Empty Service"**
3. Connect same GitHub repo
4. Root directory: `backend`
5. Start command: `python telegram_monitor.py`
6. Add same environment variables
7. Deploy

Now the Telegram monitor runs automatically and sends incidents to the map!

---

## Troubleshooting

### WebSocket doesn't connect
- Check Railway logs: Click project → **"Deployments"** → **"View Logs"**
- Verify WebSocket URL in frontend uses `wss://` not `ws://`
- Make sure Railway backend is running

### CORS errors
Edit `backend/main.py`, update CORS:
```python
allow_origins=[
    "https://YOUR-PROJECT.vercel.app",
    "http://localhost:5173",
]
```
Commit and redeploy.

### Telegram monitor not working
- Check Railway worker logs
- First run needs phone login - check logs for prompt
- Session file might need manual setup

---

## Costs

**FREE for demos/hackathons!**

- Railway: $5 free credit/month (enough for demo)
- Vercel: Unlimited hobby projects
- **Total**: $0/month for small usage

---

## What's Next?

✅ **Custom domain**: Buy domain, point to Vercel
✅ **Database**: Add PostgreSQL to save incidents
✅ **Analytics**: Add Vercel Analytics
✅ **Monitoring**: Set up error alerts
✅ **Mobile**: Make it responsive (already done!)

---

**Need help?** Check `DEPLOYMENT_GUIDE.md` for detailed instructions.
