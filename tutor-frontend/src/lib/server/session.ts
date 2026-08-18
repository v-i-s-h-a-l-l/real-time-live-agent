import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { verifyAccessJwt } from "@/lib/server/jwt";
import { authSecret } from "@/lib/server/signing";
import { backendJson, voiceApiUrl } from "@/lib/server/backendApi";

export { backendJson, voiceApiUrl };

export const ACCESS_COOKIE = "lumina_at";
export const REFRESH_COOKIE = "lumina_rt";

const ACCESS_MAX_AGE = 15 * 60;
const REFRESH_MAX_AGE = 14 * 24 * 60 * 60;

function cookieSecure(): boolean {
  return process.env.NODE_ENV === "production";
}

export function applyAuthCookies(
  response: NextResponse,
  tokens: { access_token: string; refresh_token: string },
  options?: { accessMaxAge?: number },
): NextResponse {
  const secure = cookieSecure();
  response.cookies.set(ACCESS_COOKIE, tokens.access_token, {
    httpOnly: true,
    secure,
    sameSite: "lax",
    path: "/",
    maxAge: options?.accessMaxAge ?? ACCESS_MAX_AGE,
  });
  response.cookies.set(REFRESH_COOKIE, tokens.refresh_token, {
    httpOnly: true,
    secure,
    sameSite: "lax",
    path: "/",
    maxAge: REFRESH_MAX_AGE,
  });
  return response;
}

export function clearAuthCookies(response: NextResponse): NextResponse {
  const secure = cookieSecure();
  response.cookies.set(ACCESS_COOKIE, "", {
    httpOnly: true,
    secure,
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });
  response.cookies.set(REFRESH_COOKIE, "", {
    httpOnly: true,
    secure,
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });
  return response;
}

export async function readAccessUserId(): Promise<string | null> {
  const jar = await cookies();
  const token = jar.get(ACCESS_COOKIE)?.value;
  if (!token) return null;
  const secret = authSecret();
  if (!secret) return null;
  const claims = verifyAccessJwt(token, secret);
  return claims?.sub ?? null;
}

export async function requireUserId(): Promise<string> {
  const userId = await readAccessUserId();
  if (!userId) {
    throw new AuthRequiredError();
  }
  return userId;
}

export class AuthRequiredError extends Error {
  constructor() {
    super("unauthorized");
  }
}

export function unauthorized(): NextResponse {
  return NextResponse.json({ error: "unauthorized" }, { status: 401 });
}

export function csrfAllowed(request: Request): boolean {
  const origin = request.headers.get("origin");
  if (!origin) {
    const site = request.headers.get("sec-fetch-site");
    return site === "same-origin" || site === "none" || site == null;
  }
  try {
    return new URL(origin).origin === new URL(request.url).origin;
  } catch {
    return false;
  }
}
