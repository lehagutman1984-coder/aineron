import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PROTECTED_PATHS = ["/account", "/keys", "/studio"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const isProtected = PROTECTED_PATHS.some((p) => pathname.startsWith(p));
  if (!isProtected) return NextResponse.next();

  // Check for Django session cookie (set by Django on login)
  const sessionCookie =
    request.cookies.get("sessionid") ?? request.cookies.get("session");

  if (!sessionCookie) {
    const loginUrl = new URL("/users/pages/auth/", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/account/:path*", "/keys/:path*", "/studio/:path*"],
};
