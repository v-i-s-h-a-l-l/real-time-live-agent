import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import {
  ACCESS_COOKIE,
  backendJson,
  clearAuthCookies,
  csrfAllowed,
  REFRESH_COOKIE,
} from "@/lib/server/session";

export async function POST(request: Request) {
  if (!csrfAllowed(request)) {
    return NextResponse.json({ error: "forbidden" }, { status: 403 });
  }
  const jar = await cookies();
  const refresh = jar.get(REFRESH_COOKIE)?.value;
  const access = jar.get(ACCESS_COOKIE)?.value;
  await backendJson("/auth/signout", {
    method: "POST",
    body: JSON.stringify({ refresh_token: refresh ?? null }),
    headers: access ? { Authorization: `Bearer ${access}` } : {},
  }).catch(() => ({ status: 200, body: null }));
  const response = NextResponse.json({ ok: true });
  return clearAuthCookies(response);
}
