# Frontend — Next.js tutor (Vercel)

Student-facing Lumina tutor UI. Deploy to **Vercel**; voice engine runs on **Render** ([`../server/`](../server/)).

## Local development

```bash
cd tutor-frontend
cp .env.example .env.local    # match SESSION_SECRET with backend .env
npm ci
npm run dev                   # http://localhost:3000
```

Backend must be running at `VOICE_API_URL` (default `http://127.0.0.1:8805`).

## Vercel deployment

| Setting | Value |
|---------|-------|
| **Root directory** | `tutor-frontend` |
| **Framework** | Next.js (auto-detected) |
| **Build** | `npm run build` |
| **Install** | `npm ci` |

Or connect the repo and set **Root Directory** to `tutor-frontend` in the Vercel project settings.

[`vercel.json`](./vercel.json) is included for install/build defaults.

## Environment variables (Vercel dashboard)

### Browser-safe (`NEXT_PUBLIC_*`)

| Variable | Example |
|----------|---------|
| `NEXT_PUBLIC_VOICE_WS_URL` | `wss://your-service.onrender.com/ws` |
| `NEXT_PUBLIC_VOICE_LANG` | `auto` |

### Server-only (Next.js API routes — never `NEXT_PUBLIC_`)

| Variable | Example |
|----------|---------|
| `VOICE_API_URL` | `https://your-service.onrender.com` |
| `SESSION_SECRET` | same as Render backend |
| `AUTH_SECRET` | optional; defaults to `SESSION_SECRET` |

**Important:** Voice WebSocket connects **browser → Render directly** (`NEXT_PUBLIC_VOICE_WS_URL`). Audio is **not** proxied through Vercel.

Auth and voice tickets: browser → Vercel `/api/*` → Render HTTP API.

## API / voice modules

| Module | Purpose |
|--------|---------|
| [`src/lib/api.ts`](./src/lib/api.ts) | Server-side Render HTTP proxy |
| [`src/lib/voice.ts`](./src/lib/voice.ts) | WebSocket URL + voice constants |

## Scripts

```bash
npm run lint
npm run typecheck
npm test
npm run build
```

Full deployment guide: [`../docs/deployment.md`](../docs/deployment.md)
