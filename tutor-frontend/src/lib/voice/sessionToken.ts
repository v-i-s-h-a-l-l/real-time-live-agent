/** Mint a short-lived HMAC token for the FastAPI voice engine. */

export async function mintVoiceToken(): Promise<string | null> {
  const response = await fetch("/api/voice/session", {
    method: "POST",
    credentials: "same-origin",
  });
  if (response.status === 401) {
    throw new Error("Please sign in to start a voice session.");
  }
  if (!response.ok) {
    throw new Error("Could not start a secure session.");
  }
  const data = (await response.json()) as { token?: string | null };
  return typeof data.token === "string" && data.token ? data.token : null;
}
