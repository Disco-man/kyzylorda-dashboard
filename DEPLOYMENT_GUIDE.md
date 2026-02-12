# Deployment Guide - Kyzylorda Dashboard

This guide shows how to deploy your dashboard so others can access it online.

---

## Architecture Overview

```
Users → Frontend (Vercel) → Backend (Railway) → Gemini API
                                    ↓
                              Telegram Monitor
```

---

## Option 1: Quick Deploy (Recommended for Demo)

**Best for**: Hackathons, demos, quick testing

### Step 1: Deploy Backend to Railway

**1. Create Railway account**: https://railway.app (sign up with GitHub)

**2. Prepare backend for deployment:**

Create `backend/Procfile`:
```bash
cd C:\Users\Lenovo\Desktop\Hakaton\backend
echo web: uvicorn main:app --host 0.0.0.0 --port $PORT > Procfile
echo worker: python telegram_monitor.py >> Procfile
```

Create `backend/runtime.txt`:
```bash
echo python-3.11 > runtime.txt
```

**3. Deploy on Railway:**
- Go to https://railway.app/new
- Click **"Deploy from GitHub repo"**
- Connect your GitHub account
- Push your code to GitHub first:
  ```bash
  cd C:\Users\Lenovo\Desktop\Hakaton
  git init
  git add .
  git commit -m "Initial commit"
  gh repo create kyzylorda-dashboard --public --source=.
  git push -u origin main
  ```
- Select your repo → Deploy
- Railway will auto-detect Python and install dependencies

**4. Set Environment Variables on Railway:**
- Go to your project → **Variables** tab
- Add:
  ```
  GOOGLE_API_KEY=AIzaSyC8yPsQsia4i35Q5c4AefyEz-j_y5eohUg
  GEMINI_MODEL=gemini-2.5-flash
  TELEGRAM_API_ID=35715704
  TELEGRAM_API_HASH=78b479c9a92a73114a37bf37c37dbc7e
  TELEGRAM_CHANNEL=@kyzylordanew
  PORT=8000
  ```

**5. Get your backend URL:**
- Railway will give you a URL like: `https://your-project.railway.app`
- Copy this URL

---

### Step 2: Deploy Frontend to Vercel

**1. Update frontend to use production backend:**

Edit `kyzylorda-dashboard/src/App.jsx`:
```javascript
// Replace ws://localhost:8000 with your Railway URL
const ws = new WebSocket("wss://your-project.railway.app/ws");
```

**2. Create Vercel account**: https://vercel.com (sign up with GitHub)

**3. Deploy:**
- Push frontend to GitHub (if not already):
  ```bash
  cd C:\Users\Lenovo\Desktop\Hakaton\kyzylorda-dashboard
  git init
  git add .
  git commit -m "Frontend"
  gh repo create kyzylorda-dashboard-frontend --public --source=.
  git push -u origin main
  ```
- Go to https://vercel.com/new
- Import your `kyzylorda-dashboard-frontend` repo
- Framework: **Vite**
- Click **Deploy**

**4. Get your frontend URL:**
- Vercel gives you: `https://your-project.vercel.app`
- Share this URL with others!

---

### Step 3: Keep Telegram Monitor Running

Railway can run multiple processes. In your Railway dashboard:
- Go to **Settings** → **Deploy**
- Add worker process: `python telegram_monitor.py`
- This keeps the Telegram monitor running 24/7

---

## Option 2: All-in-One Deploy (Render)

**Best for**: Simple single-platform deployment

### Deploy Everything to Render

**1. Create Render account**: https://render.com

**2. Deploy Backend:**
- New → **Web Service**
- Connect GitHub repo
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Add environment variables (same as Railway)

**3. Deploy Telegram Monitor:**
- New → **Background Worker**
- Same repo
- Build Command: `pip install -r requirements.txt`
- Start Command: `python telegram_monitor.py`
- Uses same environment variables

**4. Deploy Frontend:**
- New → **Static Site**
- Connect frontend repo
- Build Command: `npm install && npm run build`
- Publish Directory: `dist`

---

## Option 3: Free Alternatives

### Backend: Fly.io
```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

cd backend
fly launch
fly secrets set GOOGLE_API_KEY=... TELEGRAM_API_ID=...
fly deploy
```

### Frontend: Netlify
- Drag & drop the `dist` folder after `npm run build`
- Or connect GitHub repo

---

## Important Production Changes

### 1. Update CORS in `backend/main.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://your-project.vercel.app",  # Your Vercel URL
        "http://localhost:5173",  # Keep for local dev
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2. Update WebSocket URL in frontend:
```javascript
// In src/App.jsx, change:
const ws = new WebSocket("wss://your-backend-url.railway.app/ws");
```

### 3. Update `BACKEND_URL` in `.env`:
```
BACKEND_URL=https://your-backend-url.railway.app
```

---

## Quick Deploy Script (All Steps)

Save as `deploy.sh`:

```bash
#!/bin/bash

# 1. Deploy Backend
cd backend
railway login
railway up
BACKEND_URL=$(railway url)

# 2. Update Frontend
cd ../kyzylorda-dashboard
sed -i "s|ws://localhost:8000|wss://${BACKEND_URL}|g" src/App.jsx

# 3. Build and Deploy Frontend
npm run build
vercel --prod

echo "✅ Deployment complete!"
echo "Backend: https://${BACKEND_URL}"
echo "Frontend: Check Vercel dashboard for URL"
```

---

## Testing the Deployment

1. **Open your Vercel URL** in a browser
2. **Check browser console** (F12) - should see `✓ WebSocket connected`
3. **Post a test message** to [@kyzylordanew](https://t.me/kyzylordanew)
4. **Watch the map** - incident should appear in ~10-30 seconds

---

## Troubleshooting

### "WebSocket connection failed"
- Check Railway logs: `railway logs`
- Verify `BACKEND_URL` is correct in frontend
- Make sure you're using `wss://` (secure WebSocket) not `ws://`

### "Telegram monitor not running"
- Check Railway worker logs
- Verify environment variables are set
- Check session file exists (might need to login first locally)

### "CORS error"
- Update `allow_origins` in `main.py` with your Vercel URL
- Redeploy backend

### "Geocoding not working"
- Nominatim rate limits public IPs
- Consider adding a delay or using a paid geocoding service

---

## Cost Estimate (Free Tier)

| Service | Free Tier | Good For |
|---------|-----------|----------|
| **Railway** | $5 credit/month | Backend + Worker |
| **Vercel** | Unlimited hobby projects | Frontend |
| **Render** | 750 hours/month | Backend alternative |
| **Fly.io** | 3 small VMs free | Full control |

**Total**: FREE for demo/small traffic! 🎉

---

## For Production (Paid)

If you need more:
- **Railway Pro**: $20/month (higher limits)
- **Vercel Pro**: $20/month (custom domains, analytics)
- **Database**: Add PostgreSQL to save incidents
- **CDN**: Cloudflare for caching
- **Monitoring**: Sentry for error tracking

---

## Next Steps After Deploy

1. **Custom domain**: 
   - Buy domain on Namecheap
   - Point to Vercel in DNS settings

2. **HTTPS everywhere**:
   - Railway/Vercel auto-provide SSL
   - Update all URLs to `https://`

3. **Environment separation**:
   - Create separate Railway projects for dev/prod
   - Use different Telegram channels for testing

4. **Monitoring**:
   - Set up Railway/Vercel alerts
   - Add error logging with Sentry

5. **Database** (optional):
   - Add PostgreSQL on Railway
   - Save all incidents to DB
   - Show historical data

---

## Quick Links

- **Railway**: https://railway.app
- **Vercel**: https://vercel.com
- **Render**: https://render.com
- **Fly.io**: https://fly.io
- **GitHub**: https://github.com

---

## Summary

**Easiest path for demo:**
1. Push code to GitHub
2. Deploy backend to Railway (2 minutes)
3. Deploy frontend to Vercel (2 minutes)
4. Update WebSocket URL
5. Share Vercel URL with everyone! 🚀

**Total time**: ~10 minutes
**Cost**: FREE
**Result**: Public dashboard accessible to anyone!
