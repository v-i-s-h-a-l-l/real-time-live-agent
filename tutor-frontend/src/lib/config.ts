/**
 * Public runtime configuration.
 * Only NEXT_PUBLIC_* values are available in the browser.
 */

/** WebSocket endpoint for the existing FastAPI / Pipecat voice engine. */
export const VOICE_WS_URL =
  process.env.NEXT_PUBLIC_VOICE_WS_URL ?? "ws://127.0.0.1:8805/ws";

/** Language query param forwarded to the voice engine (`auto` = multilingual). */
export const VOICE_DEFAULT_LANG = process.env.NEXT_PUBLIC_VOICE_LANG ?? "auto";

const _prodWsInsecure =
  process.env.NODE_ENV === "production" &&
  !VOICE_WS_URL.startsWith("wss://");

if (_prodWsInsecure) {
  const message =
    "[Lumina] NEXT_PUBLIC_VOICE_WS_URL must use wss:// in production.";
  if (typeof window === "undefined") {
    throw new Error(message);
  }
  console.error(message);
}

/** AudioWorklet module URL (served from /public). */
export const AUDIO_WORKLET_URL = "/audio-processor.js";

/** Build voice WebSocket URL with optional query params. */
export function voiceWebSocketUrl(params?: {
  lang?: string;
  voice?: string;
}): string {
  const base = VOICE_WS_URL;
  if (!params?.lang && !params?.voice) {
    return base;
  }
  const url = new URL(base);
  if (params.lang) url.searchParams.set("lang", params.lang);
  if (params.voice) url.searchParams.set("voice", params.voice);
  return url.toString();
}
