# Production deployment — Vercel + Render

Deploy the Lumina voice tutor with **Vercel** (Next.js) and **Render** (FastAPI + Pipecat).

## Architecture

```
Browser
  ├─ HTTPS ──► Vercel (Next.js tutor-frontend)
  │              ├─ pages / API routes (auth BFF)
  │              └─ HTTP ──► Render REST (/auth/*, voice ticket minting via server routes)
  │
  └─ WSS ──────► Render WebSocket (/ws) ──► Pipecat
                    ├─ Sarvam STT
                    ├─ Cerebras / Groq LLM
                    └─ Cartesia TTS
```

**Latency rule:** Real-time audio uses **direct browser → Render WebSocket**. Vercel does **not** proxy PCM streams.

## Repository layout

This repo uses stable directory names (no rename required for deploy):

| Path | Role | Platform |
|------|------|----------|
| [`tutor-frontend/`](../tutor-frontend/) | Next.js app | **Vercel** |
| [`server/`](../server/) | FastAPI + Pipecat | **Render** |
| [`requirements.txt`](../requirements.txt) | Python deps | Render build (repo root) |
| [`render.yaml`](../render.yaml) | Render Blueprint | Render |
| [`.env.example`](../.env.example) | Backend env template | Render dashboard |
| [`tutor-frontend/.env.example`](../tutor-frontend/.env.example) | Frontend env template | Vercel dashboard |

Conceptual mapping to a `frontend/` + `backend/` monorepo:

- `frontend/` → `tutor-frontend/`
- `backend/` → `server/`

---

## Deployment order

1. **Deploy backend to Render** (see below). Note the public URL, e.g. `https://ministros-voice.onrender.com`.
2. **Set Render secrets** — API keys, `SESSION_SECRET`, `ENVIRONMENT=production`, `ALLOW_ANONYMOUS_WS=0`.
3. **Configure Vercel env vars** using the Render HTTPS/WSS URLs.
4. **Deploy frontend to Vercel** with root directory `tutor-frontend`.
5. **Set `FRONTEND_ORIGIN`** on Render to your Vercel URL, e.g. `https://lumina.vercel.app`.
6. **Redeploy or restart** the Render service (CORS + WebSocket origin checks).
7. **Test:** sign in → open lesson → **Talk to tutor** → speak → verify STT/TTS/interruption.
8. **Long session:** see [`LONG_SESSION_TEST_CHECKLIST.md`](./LONG_SESSION_TEST_CHECKLIST.md).

---

## Backend — Render

### Native Python (recommended)

[`render.yaml`](../render.yaml) defines:

```yaml
buildCommand: pip install --upgrade pip && pip install -r requirements.txt
startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT --app-dir server
healthCheckPath: /health
```

| Setting | Value |
|---------|-------|
| Root directory | `.` (repository root) |
| Python | 3.12 |
| Plan | Standard (≥2 GB RAM — torch/Silero) |

### Docker (optional)

```bash
docker build -f server/Dockerfile -t lumina-voice .
docker run -e PORT=8805 -p 8805:8805 --env-file .env lumina-voice
```

### Health endpoints

| Route | Purpose |
|-------|---------|
| `GET /health` | Process alive — use for Render health checks (no external API calls) |
| `GET /ready` | Config + API keys + production blockers — use before routing traffic manually |

### WebSocket

- Path: `/ws`
- Production: `wss://<render-host>/ws`
- Query params: `lang`, `voice` (unchanged)
- Auth: first-message voice ticket (not query string)

### Backend environment variables

Set in Render dashboard (never commit `.env`):

| Variable | Required (prod) | Notes |
|----------|-----------------|-------|
| `ENVIRONMENT` | yes | `production` |
| `SESSION_SECRET` | yes | Shared with Vercel; signs JWTs + voice tickets |
| `AUTH_SECRET` | optional | Defaults to `SESSION_SECRET` |
| `FRONTEND_ORIGIN` | yes | Exact Vercel origin, e.g. `https://app.vercel.app` |
| `SARVAM_API_KEY` | yes | STT |
| `CEREBRAS_API_KEY` | yes | LLM |
| `CARTESIA_API_KEY` | yes | TTS |
| `GROQ_API_KEY` | recommended | LLM failover |
| `ALLOW_ANONYMOUS_WS` | yes | `0` in production |
| `REDIS_URL` | scale | Shared rate limits across instances |
| `RNNOISE_ENABLED` | no | `false` default; optional denoising |
| `HOST` | auto | `0.0.0.0` (Render sets `PORT`) |

Template: [`.env.example`](../.env.example)

### CORS (production)

- `FRONTEND_ORIGIN` must match the Vercel URL exactly (scheme + host, no trailing path).
- Wildcard `*` is **blocked** when `ENVIRONMENT=production`.
- WebSocket origin check uses the same allowlist.

### Logging

Loguru writes to **stdout/stderr** — visible in Render logs. No local log files. Ops JSON events use the `ops` prefix (no secrets/audio).

### Persistence risks (Render)

| Data | Location | Risk |
|------|----------|------|
| User accounts / refresh tokens | SQLite `server/data/auth.sqlite` | **Lost on redeploy** unless persistent disk attached |
| Voice JTI single-use store | SQLite / Redis | Same |
| RNNoise / Silero models | Bundled in packages | OK |

**Do not assume ephemeral disk.** Migrate to PostgreSQL + Redis for durable multi-instance production (separate task).

---

## Frontend — Vercel

### Project settings

| Setting | Value |
|---------|-------|
| Root Directory | `tutor-frontend` |
| Framework | Next.js |
| Node.js | 20.x |
| Build | `npm run build` |
| Install | `npm ci` |

[`tutor-frontend/vercel.json`](../tutor-frontend/vercel.json) documents defaults.

### Frontend environment variables

Set in Vercel → Settings → Environment Variables. **Redeploy after changes.**

#### Browser-safe

| Variable | Production example |
|----------|-------------------|
| `NEXT_PUBLIC_VOICE_WS_URL` | `wss://ministros-voice.onrender.com/ws` |
| `NEXT_PUBLIC_VOICE_LANG` | `auto` |

Build fails if production `NEXT_PUBLIC_VOICE_WS_URL` is not `wss://`.

#### Server-only (Next.js API routes)

| Variable | Production example |
|----------|-------------------|
| `VOICE_API_URL` | `https://ministros-voice.onrender.com` |
| `SESSION_SECRET` | same long secret as Render |
| `AUTH_SECRET` | optional |

**Do not** prefix secrets with `NEXT_PUBLIC_`.

There is **no** `NEXT_PUBLIC_API_URL` by design: the browser calls same-origin `/api/*`; only Next.js server routes contact Render over HTTP.

### Centralized clients

| File | Use |
|------|-----|
| [`src/lib/api.ts`](../tutor-frontend/src/lib/api.ts) | `backendJson`, `voiceApiUrl` — API routes only |
| [`src/lib/voice.ts`](../tutor-frontend/src/lib/voice.ts) | `VOICE_WS_URL`, WebSocket helpers — browser |

---

## Local development

### Backend

```bash
cp .env.example .env
pip install -r requirements.txt
cd server && uvicorn main:app --reload --host 0.0.0.0 --port 8805
```

### Frontend

```bash
cd tutor-frontend
cp .env.example .env.local
npm ci && npm run dev
```

Defaults:

- `VOICE_API_URL=http://127.0.0.1:8805`
- `NEXT_PUBLIC_VOICE_WS_URL=ws://127.0.0.1:8805/ws`

---

## Security checklist

- [ ] `.env` / `.env.local` gitignored
- [ ] No API keys in frontend source or `NEXT_PUBLIC_*`
- [ ] `FRONTEND_ORIGIN` set on Render (no wildcard in prod)
- [ ] `NEXT_PUBLIC_VOICE_WS_URL` uses `wss://` in production
- [ ] Voice tickets not passed in WebSocket query strings
- [ ] `SESSION_SECRET` identical on Vercel and Render

---

## Troubleshooting

| Symptom | Check |
|---------|-------|
| 401 on voice session | `SESSION_SECRET` mismatch Vercel ↔ Render |
| WebSocket instant close 4403 | `FRONTEND_ORIGIN` doesn’t match Vercel URL |
| WebSocket 4408 | `/ready` blockers — missing API keys or `FRONTEND_ORIGIN` |
| CORS error on sign-in | Render `FRONTEND_ORIGIN`; restart backend after change |
| Build fails on Vercel | `NEXT_PUBLIC_VOICE_WS_URL` must be `wss://` |
| Voice silent after connect | Render logs; Sarvam/Cerebras keys; `/ready` |
| Users lost after deploy | SQLite on ephemeral disk — expected until Postgres migration |

---

## Verification matrix

After deploy:

| Test | Expected |
|------|----------|
| Vercel homepage | Loads |
| Sign in / sign up | Works via Render auth API |
| Lesson page | Loads curriculum |
| Talk to tutor | WebSocket `wss://` connects |
| Microphone + STT | Transcripts appear |
| TTS | Tutor speaks |
| Interruption | Barge-in works |
| Typed chat | Works |
| Current-page context | Tutor references lesson |
| Multilingual | Hindi/English/Tamil as before |

---

## Intentionally unchanged

- Pipecat pipeline, STT, TTS, LLM, VAD, Smart Turn, barge-in
- WebSocket protocol and direct browser → Render audio path
- Authentication design (JWT + voice tickets)
- SQLite storage (documented, not migrated in this task)
