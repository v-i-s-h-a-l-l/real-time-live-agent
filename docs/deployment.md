# Production deployment — Vercel + Railway / Render

Deploy the Lumina voice tutor with **Vercel** (Next.js) and **Railway** (FastAPI + Pipecat). Render remains a documented alternative via `render.yaml`.

## Architecture

```
Browser
  ├─ HTTPS ──► Vercel (Next.js tutor-frontend)
  │              ├─ pages / API routes (auth BFF)
  │              └─ HTTP ──► Railway REST (/auth/*, voice ticket minting via server routes)
  │
  └─ WSS ──────► Railway WebSocket (/ws) ──► Pipecat
                    ├─ Sarvam STT
                    ├─ OpenAI LLM (LLM_PROVIDER=openai)
                    └─ Cartesia TTS
```

**Latency rule:** Real-time audio uses **direct browser → Railway WebSocket**. Vercel does **not** proxy PCM streams.

Env inventory for the voice service lives in [`railway.toml`](../railway.toml) comments and must match this file and [`.env.example`](../.env.example).

## Repository layout

This repo uses stable directory names (no rename required for deploy):

| Path | Role | Platform |
|------|------|----------|
| [`tutor-frontend/`](../tutor-frontend/) | Next.js app | **Vercel** |
| [`server/`](../server/) | FastAPI + Pipecat | **Railway** (or Render) |
| [`requirements.txt`](../requirements.txt) | Python deps | Railway / Render build (repo root) |
| [`railway.toml`](../railway.toml) | Railway config-as-code | Railway |
| [`render.yaml`](../render.yaml) | Render Blueprint | Render |
| [`.env.example`](../.env.example) | Backend env template | Railway / Render dashboard |
| [`tutor-frontend/.env.example`](../tutor-frontend/.env.example) | Frontend env template | Vercel dashboard |

Conceptual mapping to a `frontend/` + `backend/` monorepo:

- `frontend/` → `tutor-frontend/`
- `backend/` → `server/`

---

## Deployment order

1. **Deploy backend to Railway** (see below). Note the public URL.
2. **Set Railway secrets** — API keys, `SESSION_SECRET`, `ENVIRONMENT=production`, `ALLOW_ANONYMOUS_WS=0`, `REDIS_URL`, `LLM_PROVIDER=openai`.
3. **Configure Vercel env vars** using the Railway HTTPS/WSS URLs.
4. **Deploy frontend to Vercel** with root directory `tutor-frontend`.
5. **Set `FRONTEND_ORIGIN`** on Railway to your Vercel URL, e.g. `https://lumina.vercel.app`.
6. **Redeploy or restart** the Railway service (CORS + WebSocket origin checks).
7. **Test:** sign in → open lesson → **Talk to tutor** → speak → verify STT/TTS/interruption.
8. **Long session:** see [`LONG_SESSION_TEST_CHECKLIST.md`](./LONG_SESSION_TEST_CHECKLIST.md).

---

## Backend — Railway (Railpack)

Railpack detects Python at the **repo root** and looks for `main.py` / `app.py` there. This app is `server/main.py`, so a start command is required.

[`railway.toml`](../railway.toml) and [`Procfile`](../Procfile):

```
uvicorn main:app --host 0.0.0.0 --port $PORT --app-dir server
```

| Setting | Value |
|---------|-------|
| Root directory | repository root (where `requirements.txt` is) |
| Custom start command | same uvicorn line as above (dashboard fallback) |
| Health check | `GET /ready` |
| RAM | ≥2 GB |

Do **not** change builder, start command, region, or replica count unless they still name Cerebras/Groq. Env vars cannot be declared in `railway.toml` (Railway schema has no `[variables]` section) — set them in the dashboard. See the inventory below.

If the dashboard still has no start command, set **Settings → Deploy → Custom Start Command** to that uvicorn line and redeploy.

---

## Backend — Render (alternative)

### Native Python

[`render.yaml`](../render.yaml) defines:

```yaml
buildCommand: pip install --upgrade pip && pip install -r requirements.txt
startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT --app-dir server
healthCheckPath: /health
```

Render still uses `GET /health` as a liveness probe (process up, no key checks). Railway uses `GET /ready`. Do not assume they are interchangeable.

| Setting | Value |
|---------|-------|
| Root directory | `.` (repository root) |
| Python | 3.12 |
| Plan | Standard (≥2 GB RAM — torch/Silero) |

### Docker (optional)

Production image: [`server/Dockerfile`](../server/Dockerfile) (multi-stage, non-root, CPU torch).

```bash
docker build -f server/Dockerfile -t lumina-backend .
docker run --rm -e PORT=8805 -p 8805:8805 --env-file .env lumina-backend
```

Render: set runtime to **Docker**, Dockerfile Path `server/Dockerfile`, context `.`. The container ENTRYPOINT binds `0.0.0.0:$PORT`. Do not bake secrets into the image.

---

### Health endpoints

| Route | Purpose |
|-------|---------|
| `GET /health` | Process alive — Render liveness (no key checks, no external API calls) |
| `GET /ready` | Config + API keys + production blockers — **Railway healthcheck**. Missing `OPENAI_API_KEY` (when `LLM_PROVIDER=openai`) returns 503. The JSON body does **not** include `LLM_PROVIDER`. `REDIS_URL` unset is a `config_warnings()` note, not a `/ready` blocker. |

### WebSocket

- Path: `/ws`
- Production: `wss://<railway-host>/ws`
- Query params: `lang`, `voice` (unchanged)
- Auth: first-message voice ticket (not query string)

### Backend environment variables

Set in the Railway (or Render) dashboard. Never commit `.env`. This table matches the [`railway.toml`](../railway.toml) comment inventory.

| Variable | Required (prod) | Notes |
|----------|-----------------|-------|
| `ENVIRONMENT` | yes | `production` |
| `SESSION_SECRET` | yes | Shared with Vercel; signs JWTs + voice tickets |
| `AUTH_SECRET` | optional | Defaults to `SESSION_SECRET` |
| `FRONTEND_ORIGIN` | yes | Exact Vercel origin, e.g. `https://app.vercel.app` |
| `SARVAM_API_KEY` | yes | STT |
| `OPENAI_API_KEY` | yes | LLM (`LLM_PROVIDER=openai`) |
| `CARTESIA_API_KEY` | yes | TTS |
| `LLM_PROVIDER` | yes | Default `openai`. Set explicitly so leftover Groq/Cerebras values cannot win. |
| `LLM_MODEL` | optional | Default `gpt-5.6-luna` when provider is openai |
| `REDIS_URL` | yes | Shared rate limits / tickets across instances. App currently *warns* if unset; still required here. |
| `ALLOW_ANONYMOUS_WS` | yes | `0` in production |
| `ENABLE_DEMO_LOGIN` | yes (unset/`0`) | Must be unset or false in prod. Ignored by app in production even if set. |
| `CALL_MUTE_TIMEOUT_SECS` | no | Default `40` |
| `CALL_MUTE_RESUME_MIN_WORDS` | no | Default `6` |
| `AWAITING_TIMEOUT_SECS` | no | Default `40` |
| `AWAITING_MISS_RESUME_AFTER` | no | Default `3` |
| `LLM_EMPTY_GUARD_TIMEOUT_SECS` | no | Default `20` |
| `TTS_FALLBACK_PROVIDER` | optional | `openai` for Cartesia 402 failover; uses `OPENAI_API_KEY` |
| `GROQ_API_KEY` | optional | Only if `LLM_PROVIDER=groq` |
| `GEMINI_API_KEY` | optional | Only if `LLM_PROVIDER=gemini` (also accepts `GOOGLE_API_KEY` / `GOOGLE_AI_API_KEY`) |
| `OPENROUTER_API_KEY` | optional | Only if `LLM_PROVIDER=openrouter` |
| `RNNOISE_ENABLED` | no | `false` default; optional denoising |
| `HOST` | auto | `0.0.0.0` (Railway/Render set `PORT`) |
| `MAX_CONCURRENT_SESSIONS` | no | Default `20` |

Do **not** set `CEREBRAS_API_KEY` or `CEREBRAS_API_KEY_2` — they are unused. There is no Sentry/APM DSN in `config.py`.

Template: [`.env.example`](../.env.example)

### CORS (production)

- `FRONTEND_ORIGIN` must match the Vercel URL exactly (scheme + host, no trailing path).
- Wildcard `*` is **blocked** when `ENVIRONMENT=production`.
- WebSocket origin check uses the same allowlist.

### Logging

Loguru writes to **stdout/stderr** — visible in Railway / Render logs. No local log files. Ops JSON events use the `ops` prefix (no secrets/audio).

### Persistence risks (Railway / Render)

| Data | Location | Risk |
|------|----------|------|
| User accounts / refresh tokens | SQLite `server/data/auth.sqlite` | **Lost on redeploy** unless persistent disk attached |
| Voice JTI single-use store | SQLite / Redis | Same |
| RNNoise / Silero models | Bundled in packages | OK |

**Do not assume ephemeral disk.** `REDIS_URL` is required in production. Migrate to PostgreSQL + Redis for durable multi-instance production (separate task).

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
| `NEXT_PUBLIC_VOICE_WS_URL` | `wss://YOUR-SERVICE.up.railway.app/ws` |
| `NEXT_PUBLIC_VOICE_LANG` | `auto` |

Build fails if production `NEXT_PUBLIC_VOICE_WS_URL` is not `wss://`.

#### Server-only (Next.js API routes)

| Variable | Production example |
|----------|-------------------|
| `VOICE_API_URL` | `https://YOUR-SERVICE.up.railway.app` |
| `SESSION_SECRET` | same long secret as Railway |
| `AUTH_SECRET` | optional |

**Do not** prefix secrets with `NEXT_PUBLIC_`.

There is **no** `NEXT_PUBLIC_API_URL` by design: the browser calls same-origin `/api/*`; only Next.js server routes contact Railway over HTTP.

### Centralized clients

| File | Use |
|------|-----|
| [`src/lib/api.ts`](../tutor-frontend/src/lib/api.ts) | `backendJson`, `voiceApiUrl` — API routes only |
| [`src/lib/config.ts`](../tutor-frontend/src/lib/config.ts) | `VOICE_WS_URL`, WebSocket helpers — browser |

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
- [ ] `FRONTEND_ORIGIN` set on Railway (no wildcard in prod)
- [ ] `NEXT_PUBLIC_VOICE_WS_URL` uses `wss://` in production
- [ ] Voice tickets not passed in WebSocket query strings
- [ ] `SESSION_SECRET` identical on Vercel and Railway
- [ ] `LLM_PROVIDER=openai` and `OPENAI_API_KEY` set; `CEREBRAS_*` removed
- [ ] `REDIS_URL` set; `ENABLE_DEMO_LOGIN` unset or `0`

---

## Troubleshooting

| Symptom | Check |
|---------|-------|
| 401 on voice session | `SESSION_SECRET` mismatch Vercel ↔ Railway |
| WebSocket instant close 4403 | `FRONTEND_ORIGIN` doesn’t match Vercel URL |
| WebSocket 4408 | `/ready` blockers — missing API keys or `FRONTEND_ORIGIN` |
| CORS error on sign-in | Railway `FRONTEND_ORIGIN`; restart backend after change |
| Build fails on Vercel | `NEXT_PUBLIC_VOICE_WS_URL` must be `wss://` |
| Voice silent after connect | Railway logs; Sarvam/OpenAI/Cartesia keys; `/ready` |
| Deploy healthcheck red | `GET /ready` 503 — missing `OPENAI_API_KEY` / other required keys, or prod blockers (`FRONTEND_ORIGIN`, `SESSION_SECRET`, `ALLOW_ANONYMOUS_WS`) |
| Users lost after deploy | SQLite on ephemeral disk — expected until Postgres migration |

---

## Verification matrix

After deploy:

| Test | Expected |
|------|----------|
| Vercel homepage | Loads |
| Sign in / sign up | Works via Railway auth API |
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
- WebSocket protocol and direct browser → Railway audio path
- Authentication design (JWT + voice tickets)
- SQLite storage (documented, not migrated in this task)
