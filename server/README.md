# Backend — FastAPI + Pipecat (Railway)

Voice engine for the Lumina tutor. Deploy to **Railway**; the Next.js UI lives in [`../tutor-frontend/`](../tutor-frontend/) (Vercel). Render is an alternative (`../render.yaml`).

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

## Railway

[`../railway.toml`](../railway.toml) — Railpack, start command unchanged, healthcheck `GET /ready`.

Set environment variables from [`.env.example`](../.env.example) in the Railway dashboard. Env vars cannot be declared in `railway.toml` (schema has no `[variables]` section).

## Render (native Python, alternative)

Use [`../render.yaml`](../render.yaml) Blueprint or manual Web Service:

| Setting | Value |
|---------|-------|
| **Root directory** | `.` (repo root) |
| **Build** | `pip install --upgrade pip && pip install -r requirements.txt` |
| **Start** | `uvicorn main:app --host 0.0.0.0 --port $PORT --app-dir server` |
| **Health check** | `/health` |

Set environment variables from [`.env.example`](../.env.example) in the Render dashboard.

## Docker (Render)

Multi-stage CPU image: [`Dockerfile`](./Dockerfile). Build from **repository root** (needs `requirements.txt`):

```bash
docker build -f server/Dockerfile -t lumina-backend .
docker run --rm -e PORT=8805 -p 8805:8805 --env-file .env lumina-backend
```

- Listens on `0.0.0.0:$PORT` (Render injects `PORT`; local default 8805)
- Runs as non-root user `lumina`
- Secrets come from environment variables — `.env` is not copied into the image
- Optional RNNoise: `librnnoise.so` is installed from the `pyrnnoise` wheel (`--no-deps`); enable with `RNNOISE_ENABLED=true`
- Health: `GET /health` (also Docker `HEALTHCHECK`)

On Render, either keep native Python (`render.yaml`) or switch the service to **Docker** with Dockerfile Path `server/Dockerfile` and context `.`.

## Environment

See [`../.env.example`](../.env.example). Production minimum (matches [`../railway.toml`](../railway.toml)):

- `ENVIRONMENT=production`
- `SESSION_SECRET`, `AUTH_SECRET` (or shared secret)
- `FRONTEND_ORIGIN=https://your-app.vercel.app`
- `SARVAM_API_KEY`, `OPENAI_API_KEY`, `CARTESIA_API_KEY`
- `LLM_PROVIDER=openai`
- `REDIS_URL`
- `ALLOW_ANONYMOUS_WS=0`
- `ENABLE_DEMO_LOGIN=0`

## Persistence warning

Auth uses **SQLite** at `server/data/auth.sqlite` by default. Railway/Render filesystems are **ephemeral** — user accounts may be lost on redeploy unless you attach a volume or migrate to PostgreSQL (planned separately).

## Tests

```bash
cd server && pytest -q
```

Full deployment guide: [`../docs/deployment.md`](../docs/deployment.md)
