import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import {
  ACCESS_COOKIE,
  applyAuthCookies,
  backendJson,
  csrfAllowed,
  REFRESH_COOKIE,
  unauthorized,
} from "@/lib/server/session";

export async function POST(request: Request) {
  if (!csrfAllowed(request)) {
    return NextResponse.json({ error: "forbidden" }, { status: 403 });
  }
  const jar = await cookies();
  const refresh = jar.get(REFRESH_COOKIE)?.value;
  if (!refresh) {
    return unauthorized();
  }
  const access = jar.get(ACCESS_COOKIE)?.value;
  const { status, body: data } = await backendJson("/auth/refresh", {
    method: "POST",
    body: JSON.stringify({ refresh_token: refresh }),
    headers: access ? { Authorization: `Bearer ${access}` } : {},
  });
  if (status >= 400 || !data || typeof data !== "object") {
    return unauthorized();
  }
  const tokens = data as { access_token?: string; refresh_token?: string };
  if (!tokens.access_token || !tokens.refresh_token) {
    return unauthorized();
  }
  const response = NextResponse.json({ ok: true });
  return applyAuthCookies(response, {
    access_token: tokens.access_token,
    refresh_token: tokens.refresh_token,
  });
}
