# Backend — FastAPI + Pipecat (Render)

Voice engine for the Lumina tutor. Deploy to **Render**; the Next.js UI lives in [`../tutor-frontend/`](../tutor-frontend/) (Vercel).

## Local development

```bash
# From repository root
cp .env.example .env          # fill API keys + SESSION_SECRET
pip install -r requirements.txt

cd server
uvicorn main:app --reload --host 0.0.0.0 --port 8805
```

Health: `GET http://127.0.0.1:8805/health`  
Readiness: `GET http://127.0.0.1:8805/ready` (checks API keys + production config)

WebSocket: `ws://127.0.0.1:8805/ws`

## Render (native Python)

Use [`../render.yaml`](../render.yaml) Blueprint or manual Web Service:

| Setting | Value |
|---------|-------|
| **Root directory** | `.` (repo root) |
| **Build** | `pip install --upgrade pip && pip install -r requirements.txt` |
| **Start** | `uvicorn main:app --host 0.0.0.0 --port $PORT --app-dir server` |
| **Health check** | `/health` |

Set environment variables from [`.env.example`](../.env.example) in the Render dashboard.

## Docker (optional)

Build from **repository root**:

```bash
docker build -f server/Dockerfile -t lumina-voice .
docker run --env-file .env -p 8805:8805 -e PORT=8805 lumina-voice
```

## Environment

See [`../.env.example`](../.env.example). Production minimum:

- `ENVIRONMENT=production`
- `SESSION_SECRET`, `AUTH_SECRET` (or shared secret)
- `FRONTEND_ORIGIN=https://your-app.vercel.app`
- `SARVAM_API_KEY`, `CEREBRAS_API_KEY`, `CARTESIA_API_KEY`
- `ALLOW_ANONYMOUS_WS=0`

## Persistence warning

Auth uses **SQLite** at `server/data/auth.sqlite` by default. Render’s filesystem is **ephemeral** — user accounts may be lost on redeploy unless you attach a persistent disk or migrate to PostgreSQL (planned separately).

## Tests

```bash
cd server && pytest -q
```

Full deployment guide: [`../docs/deployment.md`](../docs/deployment.md)
