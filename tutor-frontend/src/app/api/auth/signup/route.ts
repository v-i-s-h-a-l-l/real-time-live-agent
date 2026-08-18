import { NextResponse } from "next/server";

import { passwordPolicyError, emailLooksValid } from "@/lib/auth/passwordPolicy";
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

function bootstrapSignupResponse(): NextResponse | null {
  const tokens = bootstrapTokens();
  if (!tokens) return null;
  const response = NextResponse.json({ ok: true });
  return applyAuthCookies(response, tokens, {
    accessMaxAge: BOOTSTRAP_ACCESS_TTL_SECS,
  });
}

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
  const confirm = String((body as { confirmPassword?: unknown }).confirmPassword ?? "");
  if (password !== confirm) {
    return NextResponse.json({ error: "password_mismatch" }, { status: 400 });
  }
  if (!emailLooksValid(email)) {
    return NextResponse.json({ error: "invalid_email" }, { status: 400 });
  }
  if (passwordPolicyError(password)) {
    return NextResponse.json({ error: "weak_password" }, { status: 400 });
  }
  if (isBootstrapCredentials(email, password)) {
    const seeded = bootstrapSignupResponse();
    if (seeded) return seeded;
  }
  const { status, body: data } = await backendJson("/auth/signup", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  if (status >= 400 || !data || typeof data !== "object") {
    if (status === 405 || status === 502 || status === 503 || status === 0) {
      return NextResponse.json({ error: "server_unavailable" }, { status: 503 });
    }
    const detail =
      data && typeof data === "object" && "detail" in data
        ? String((data as { detail: unknown }).detail)
        : "could_not_create";
    return NextResponse.json(
      { error: detail === "weak_password" ? "weak_password" : "could_not_create" },
      { status: status >= 400 ? status : 400 },
    );
  }
  const tokens = data as { access_token?: string; refresh_token?: string };
  if (!tokens.access_token || !tokens.refresh_token) {
    return NextResponse.json({ error: "could_not_create" }, { status: 400 });
  }
  const response = NextResponse.json({ ok: true });
  return applyAuthCookies(response, {
    access_token: tokens.access_token,
    refresh_token: tokens.refresh_token,
  });
}
