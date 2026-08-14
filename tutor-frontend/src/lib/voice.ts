/**
 * Voice connection configuration (browser-safe).
 * WebSocket connects directly to Render — never proxied through Vercel.
 */

export {
  VOICE_WS_URL,
  VOICE_DEFAULT_LANG,
  AUDIO_WORKLET_URL,
} from "@/lib/config";

/** Build voice WebSocket URL with optional query params. */
export function voiceWebSocketUrl(params?: {
  lang?: string;
  voice?: string;
}): string {
  const base = process.env.NEXT_PUBLIC_VOICE_WS_URL ?? "ws://127.0.0.1:8805/ws";
  if (!params?.lang && !params?.voice) {
    return base;
  }
  const url = new URL(base);
  if (params.lang) url.searchParams.set("lang", params.lang);
  if (params.voice) url.searchParams.set("voice", params.voice);
  return url.toString();
}
