import { NextResponse } from "next/server";

import {
  BOOTSTRAP_ACCESS_TTL_SECS,
  bootstrapTokens,
  isBootstrapCredentials,
} from "@/lib/server/bootstrapAuth";
import {
  applyAuthCookies,
  backendJson,
  csrfAllowed,
} from "@/lib/server/session";

export async function POST(request: Request) {
  if (!csrfAllowed(request)) {
    return NextResponse.json({ error: "forbidden" }, { status: 403 });
  }
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "invalid" }, { status: 400 });
  }
  if (!body || typeof body !== "object") {
    return NextResponse.json({ error: "invalid" }, { status: 400 });
  }
  const email = String((body as { email?: unknown }).email ?? "");
  const password = String((body as { password?: unknown }).password ?? "");
  if (isBootstrapCredentials(email, password)) {
    const tokens = bootstrapTokens();
    if (tokens) {
      const response = NextResponse.json({ ok: true });
      return applyAuthCookies(response, tokens, {
        accessMaxAge: BOOTSTRAP_ACCESS_TTL_SECS,
      });
    }
  }
  const { status, body: data } = await backendJson("/auth/signin", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  if (status >= 400 || !data || typeof data !== "object") {
    return NextResponse.json(
      { error: "invalid_credentials" },
      { status: status === 429 ? 429 : 401 },
    );
  }
  const tokens = data as { access_token?: string; refresh_token?: string };
  if (!tokens.access_token || !tokens.refresh_token) {
    return NextResponse.json({ error: "invalid_credentials" }, { status: 401 });
  }
  const response = NextResponse.json({ ok: true });
  return applyAuthCookies(response, {
    access_token: tokens.access_token,
    refresh_token: tokens.refresh_token,
  });
}
