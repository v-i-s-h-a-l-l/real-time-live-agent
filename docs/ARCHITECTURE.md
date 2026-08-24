# Architecture

Lumina is a Class 10 Mathematics voice tutor. The student studies a lesson in the browser and talks to the tutor over a WebSocket. Speech in, reasoning, and speech out stay on the FastAPI process; the Next.js app never holds API keys.

```
Browser (tutor-frontend, :3000)
  lesson UI ──► conversation panel
  mic PCM  ──► WebSocket /ws ──► FastAPI + Pipecat (:8805)
  typed text ─► JSON control messages (see protocol below)
                                    │
                                    ├─ Sarvam STT
                                    ├─ Tutor Engine (intent → policy → prompt)
                                    ├─ OpenAI LLM (LLM_PROVIDER=openai)
                                    ├─ speak_math + Naturalizer
                                    └─ Cartesia TTS
```

## Where things live

| Concern | Location |
|---|---|
| Lesson UI, practice, transcript | `tutor-frontend/src/components/` |
| Voice WebSocket client | `tutor-frontend/src/lib/voice/` |
| Curriculum content | `tutor-frontend/src/content/curriculum/` |
| Pipeline assembly | `server/pipeline.py` |
| Wire protocol (browser → server) | `server/protocol.py` ↔ `tutor-frontend/src/lib/voice/protocol.ts` |
| Tutor policy / scope | `server/tutor/` |
| Math → spoken English | `server/processors/speak_math.py` |
| Session / slide / practice context | `server/processors/session_context.py` |
| Config / secrets | `server/config.py`, root `.env` |

## WebSocket protocol

The socket carries **binary PCM-16 mono @ 16 kHz** and **JSON** with a `type` field.

Browser → server (`server/protocol.py`):

- `interrupt` — barge-in
- `text_input` — typed chat (same tutor path as speech)
- `tts_voice` — Cartesia voice id
- `session_context` — topic the student opened
- `learning_context` — slide / section / practice question on screen
- `tutor_context` — hints/solutions, never shown on screen

Server → browser events come from Pipecat RTVI (`bot-llm-text`, `user-transcription`, `bot-started-speaking`, …) plus application events (`break_*`, `practice_progress`), all listed in `tutor-frontend/src/lib/voice/protocol.ts`.

Changing a wire string on one side without the other breaks the session. Both sides have tests that pin the literals.

## Adaptive practice

The tutor scores practice attempts itself instead of asking the LLM whether the student was right.

- `server/tutor/practice.py` is the source of truth: answer evaluation, per-question attempts and hint level, per-topic counters, mastery, and the difficulty step. Pure and deterministic — no LLM call, ~0.1 ms per turn.
- Evaluation is notation-aware, not string equality: `2 and 3`, `x = 3, 2`, `(x-2)(x-3)` and `0.5` vs `1/2` all resolve correctly, and a student who reaches only one of two roots is *partially* correct. Hint requests, "I don't know", and concept questions are never scored as wrong answers.
- Repeated failure walks a hint ladder (small nudge → sharper hint → step guidance → work it through together). The LLM receives the verdict and the rung, then does all the talking, so the persona is unchanged.
- `practice_progress` mirrors that state to the browser. The lesson UI uses it for feedback, a small progress chip, and the next question; question selection itself is local application logic (`domain/practice/adaptive.ts`).
- `tutor-frontend/src/domain/practice/evaluation.ts` is a deliberate port of the Python evaluator so the practice card can react before the tutor replies. `shared/practice-answer-cases.json` is asserted by both test suites, so the two cannot drift.

State is session-scoped: a refresh starts a fresh practice session. The data structures are shaped for persistence when that is added.

## Tutor context flow

1. Student opens a topic page.
2. After the socket is up, the browser sends `session_context`, then `learning_context` whenever the visible unit changes.
3. `SessionContextProcessor` stores the payload and injects a short system note into the LLM context.
4. `TutorTurnProcessor` runs the Tutor Engine (intent + scope lock + policy) and writes a per-turn directive.
5. The LLM streams tokens; the Naturalizer + `speak_math` rewrite the text for TTS; Cartesia speaks it. The transcript shows the original (with KaTeX), not the spoken form.

## Local development

```powershell
# backend
cd real-time-live-agent\server
..\voice-agent\.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8805 --reload

# frontend
cd real-time-live-agent\tutor-frontend
npm run dev
```

Open `http://localhost:3000`. The engine is `ws://127.0.0.1:8805/ws`.

- `GET /health` — process is up (liveness; no key checks)
- `GET /ready` — STT, LLM, and TTS keys plus production blockers (`FRONTEND_ORIGIN`, `SESSION_SECRET`, `ALLOW_ANONYMOUS_WS`). Railway healthcheck uses this path. The JSON body does **not** include `LLM_PROVIDER`; a missing `OPENAI_API_KEY` (when `LLM_PROVIDER=openai`) still returns 503.

Required secrets (root `.env` / Railway dashboard): `SARVAM_API_KEY`, `OPENAI_API_KEY`, `CARTESIA_API_KEY`. Production also requires `SESSION_SECRET`, `FRONTEND_ORIGIN`, `REDIS_URL`, `ENVIRONMENT=production`. `LLM_PROVIDER` defaults to `openai`. `GROQ_API_KEY` / `GEMINI_API_KEY` / `OPENROUTER_API_KEY` are optional and only used if you switch `LLM_PROVIDER`. There is no `CEREBRAS_API_KEY` and no Sentry DSN in `config.py`.

Inventory that must stay in sync: [`railway.toml`](../railway.toml) comments, [`.env.example`](../.env.example), [`docs/deployment.md`](./deployment.md).

## Tests

```powershell
# backend
cd real-time-live-agent
voice-agent\.venv\Scripts\python.exe -m pytest server/tests -q

# frontend
cd real-time-live-agent\tutor-frontend
npm run typecheck
npm run lint
npm test
```

Do not treat `client/` as the product UI. It is a leftover static page still mounted at `http://localhost:8805/` for engine-only debugging.

`/session` redirects home. Lesson pages live under `/subjects/.../topics/...`.
