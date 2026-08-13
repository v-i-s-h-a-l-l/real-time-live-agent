# Lumina — Class 10 AI Tutor (Phase 1–2 frontend)

Next.js + TypeScript client for the **existing** FastAPI / Pipecat voice engine.

## Run locally

1. Start the voice engine (from `real-time-live-agent/server`):

```powershell
..\voice-agent\.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8805
```

2. Start this app:

```powershell
cd tutor-frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

Configure `NEXT_PUBLIC_VOICE_WS_URL` in `.env.local` (default `ws://127.0.0.1:8805/ws`).

## Architecture

| Layer | Location | Role |
|-------|----------|------|
| Content data | `src/content/curriculum/` | Static Class 10 Math chapters/topics |
| Domain | `src/domain/curriculum/` | Types + session context builder |
| CurriculumService | `src/services/curriculum/` | Read API for UI/session |
| Voice Engine | `../server` | Domain-agnostic Pipecat pipeline |
| Frontend | `src/app`, `src/components` | LMS navigation + voice session |

Do **not** put WebSocket / AudioWorklet logic in React components — use `src/lib/voice/VoiceAgentClient.ts` via `useVoiceSession`.

## Scripts

```powershell
npm run typecheck
npm run lint
npm test
npm run build
```
