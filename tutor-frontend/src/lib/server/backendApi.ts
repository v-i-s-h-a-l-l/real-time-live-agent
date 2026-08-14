/**
 * Server-side FastAPI client (Next.js API routes / Server Components only).
 * Browser code must use same-origin `/api/*` routes — never import this file
 * from client components.
 */

export function voiceApiUrl(): string {
  return (process.env.VOICE_API_URL ?? "http://127.0.0.1:8805").replace(
    /\/$/,
    "",
  );
}

export async function backendJson(
  path: string,
  init: RequestInit,
): Promise<{ status: number; body: unknown }> {
  const response = await fetch(`${voiceApiUrl()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
    cache: "no-store",
  });
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  return { status: response.status, body };
}
