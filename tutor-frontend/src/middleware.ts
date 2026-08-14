import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_PREFIXES = [
  "/signin",
  "/signup",
  "/api/auth/signin",
  "/api/auth/signup",
  "/api/auth/refresh",
];

function isPublic(pathname: string): boolean {
  if (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/audio-processor") ||
    pathname === "/favicon.ico"
  ) {
    return true;
  }
  return PUBLIC_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (isPublic(pathname)) {
    return NextResponse.next();
  }
  const access = request.cookies.get("lumina_at")?.value;
  const refresh = request.cookies.get("lumina_rt")?.value;
  if (!access && !refresh) {
    if (pathname.startsWith("/api/")) {
      return NextResponse.json({ error: "unauthorized" }, { status: 401 });
    }
    const url = request.nextUrl.clone();
    url.pathname = "/signin";
    url.search = "";
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image).*)"],
};
