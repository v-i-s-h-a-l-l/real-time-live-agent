# Ministros Voice Agent

Real-time voice AI: mic → WebSocket → Pipecat (STT → LLM → TTS) with barge-in.

**Stack:** FastAPI · Pipecat · Sarvam STT · Cerebras/Groq LLM · Cartesia TTS

## Local run

```powershell
cd real-time-live-agent\server
..\voice-agent\.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8805
```

Open **http://localhost:8805/**

## Deploy: Vercel (frontend) + Render (backend)

### A. Backend on Render

1. Push this repo to GitHub (include `real-time-live-agent/`).
2. [Render](https://dashboard.render.com) → **New → Web Service** → connect the repo.
3. Settings:
   - **Root Directory:** `real-time-live-agent`
   - **Runtime:** Python 3.12
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT --app-dir server`
   - **Instance:** at least **Standard** (~2 GB RAM). Free tier usually fails (sleep + torch RAM).
4. Environment variables:
   - `CEREBRAS_API_KEY`
   - `SARVAM_API_KEY`
   - `CARTESIA_API_KEY`
   - `GROQ_API_KEY`
   - `FRONTEND_ORIGIN` = your Vercel URL, e.g. `https://ministros.vercel.app`  
     (comma-separate multiple; use `*` only for quick tests)
5. Deploy → copy the service URL, e.g. `https://ministros-voice.onrender.com`
6. Check `https://YOUR-RENDER.onrender.com/health` → `{"status":"ok"}`

Or use the Blueprint: **New → Blueprint** → select `real-time-live-agent/render.yaml`.

### B. Frontend on Vercel

1. [Vercel](https://vercel.com) → **Add New Project** → import the same repo.
2. Settings:
   - **Root Directory:** `real-time-live-agent/client`
   - **Framework Preset:** Other
   - **Build Command:** `npm run build`
   - **Output Directory:** `.` (leave default / `.`)
3. Environment variable:
   - `MINISTROS_WS_URL` = `wss://YOUR-RENDER.onrender.com/ws`  
     (must be **wss**, not ws, and must end with `/ws`)
4. Deploy → open the Vercel URL → **Connect** → allow microphone.

### C. Order matters

1. Deploy **Render** first and confirm `/health`.
2. Then deploy **Vercel** with `MINISTROS_WS_URL` pointing at Render.
3. After you know the final Vercel URL, set `FRONTEND_ORIGIN` on Render and redeploy (or save env).

### Notes

- Mic only works on **HTTPS** (Vercel provides this).
- Render cold starts with torch can take 1–2 minutes after idle — upgrade plan or keep the service awake.
- Local still works unchanged: open FastAPI at `:8805` (same-origin `/ws`).
- Quick test without rebuilding Vercel:  
  `https://your-app.vercel.app/?ws=wss://YOUR-RENDER.onrender.com/ws`
