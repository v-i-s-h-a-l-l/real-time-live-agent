/**
 * Public runtime configuration.
 * Only NEXT_PUBLIC_* values are available in the browser.
 */

/** WebSocket endpoint for the existing FastAPI / Pipecat voice engine. */
export const VOICE_WS_URL =
  process.env.NEXT_PUBLIC_VOICE_WS_URL ?? "ws://127.0.0.1:8805/ws";

/** Language query param forwarded to the voice engine (`auto` = multilingual). */
export const VOICE_DEFAULT_LANG = process.env.NEXT_PUBLIC_VOICE_LANG ?? "auto";

if (
  process.env.NODE_ENV === "production" &&
  VOICE_WS_URL.includes("127.0.0.1")
) {
  console.warn(
    "[Lumina] NEXT_PUBLIC_VOICE_WS_URL is still the local default. Set it to the deployed engine (wss://…) or voice will not connect.",
  );
}

/** AudioWorklet module URL (served from /public). */
export const AUDIO_WORKLET_URL = "/audio-processor.js";
