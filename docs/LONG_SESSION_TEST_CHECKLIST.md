# Long-session manual test checklist

Use this after production-hardening or voice-pipeline changes. **Do not run in CI** — these exercises need a mic, speakers, and live provider keys.

## Setup

- Backend: `ENVIRONMENT=development`, voice server on `:8805`
- Frontend: `npm run dev` on `:3000`, `.env.local` with matching secrets
- Use a real lesson (e.g. Euclid's Division Lemma)
- Open browser devtools → Network → WS to watch reconnects

## Sessions

| # | Scenario | Steps | Expected |
|---|----------|-------|----------|
| 1 | **5 min continuous** | Talk to tutor, ask 8–12 short questions, mix voice + typed | Transcripts appear each turn; tutor responds; no silent stall |
| 2 | **15 min continuous** | Same as above with longer explanations | STT may reconnect (check server `ops` logs for `stt_reconnect_*`); UI shows “Reconnecting…” then recovers |
| 3 | **Multiple interruptions** | Start tutor speaking, interrupt 5+ times mid-sentence | Barge-in works; truncated assistant text dropped from context; tutor continues coherently |
| 4 | **Repeated barge-ins** | Rapid back-to-back interrupts during long reply | No duplicate answers; audio gate recovers within ~350ms decay |
| 5 | **Hindi → English** | Start in Hindi, ask to switch to English, continue | Language tracker switches; TTS voice appropriate; STT still transcribes |
| 6 | **English → Hindi** | Reverse of above | Same |
| 7 | **Tamil → English** | Speak Tamil, then English follow-ups | Transcripts in correct script; tutor responds in requested language |
| 8 | **English → Tamil** | Reverse of above | Same |
| 9 | **Multiple questions** | 5+ distinct maths questions in one session | Context stays on topic; no cross-question bleed |
| 10 | **Long tutor explanations** | Ask “explain in detail” and let tutor speak 60s+ | Full reply streams; can interrupt; math spoken clearly |
| 11 | **STT reconnect** | Run 15 min session or simulate network blip | Server logs `stt_reconnect_attempt` / `stt_reconnect_success`; user sees reconnect banner; speech works after |
| 12 | **WebSocket reconnect** | Toggle airplane mode 3s mid-session (or kill/restart backend once) | Client shows “Voice connection lost” / “Reconnecting…”; recovers or prompts End + Talk again |
| 13 | **LLM failover** | (Optional) exhaust Cerebras quota | Server logs `cerebras_429` + `groq_failover`; tutor still answers (may be slower) |
| 14 | **TTS failure** | (Hard to trigger) if Cartesia errors | Spoken reply may stop; typed chat may still work; check server logs |
| 15 | **Break feature** | Ask for a short break | Break timer UI; tutor acknowledges; resume works |
| 16 | **Safety handling** | Trigger holding/distress phrasing (careful testing) | Safety banner; appropriate spoken response; lesson can resume |
| 17 | **FAQ handling** | Ask “who made you?” / platform FAQ | Brief answer; returns to lesson |

## Regression smoke (quick)

After any deploy:

1. Homepage loads
2. Sign in works
3. Open Maths → lesson loads
4. **Talk to tutor** → greeting plays
5. One voice question + one typed question
6. Sign out

## Automated (CI-safe)

These run in CI without external APIs:

- `server/tests/test_config_readiness.py` — production blockers
- `server/tests/test_ops_log.py` — structured log helper
- `tutor-frontend/src/components/lesson/VoiceConnectionBanner.test.ts` — connection notice logic

## Log events to watch (production)

Filter logs for `"event":` in `ops` lines:

- `ws_open`, `ws_close`, `ws_auth_failure`, `ws_auth_ok`
- `stt_connection_failure`, `stt_reconnect_attempt`, `stt_reconnect_success`
- `llm_request_failure`, `cerebras_429`, `groq_failover`
- `pipeline_exception`, `voice_session_failure`

Never expect secrets, JWTs, or raw audio in these lines.
