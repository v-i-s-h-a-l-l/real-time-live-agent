/** Calm copy for students. Never show raw protocol errors. */

const SAFE_COPY = new Set([
  "Start voice to send a message.",
  "Something went wrong. Try again.",
  "Connection lost. Reconnecting…",
  "Could not start a secure session.",
  "Please sign in to start a voice session.",
  "I can’t hear the microphone. Check permissions and try again.",
]);

export function studentFacingError(raw: string | null | undefined): string {
  if (!raw) return "Something went wrong. Try again.";
  if (SAFE_COPY.has(raw)) return raw;
  const text = raw.toLowerCase();
  if (
    text.includes("unauthorized") ||
    text.includes("secure session") ||
    text.includes("sign in") ||
    text.includes("4401")
  ) {
    return "Could not start a secure session.";
  }
  if (
    text.includes("websocket") ||
    text.includes("connect") ||
    text.includes("network") ||
    text.includes("offline")
  ) {
    return "Connection lost. Reconnecting…";
  }
  if (text.includes("microphone") || text.includes("permission")) {
    return "I can’t hear the microphone. Check permissions and try again.";
  }
  return "Something went wrong. Try again.";
}
