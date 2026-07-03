import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PROTECTED_PATHS = ["/account", "/keys", "/studio"];
const REF_COOKIE_MAX_AGE = 60 * 60 * 24 * 30; // 30 дней

export function middleware(request: NextRequest) {
  const { pathname, searchParams } = request.nextUrl;

  // Реферальный код из ?ref=CODE сохраняем в cookie: регистрация и соцвход
  // идут на тот же домен, Django прочитает её и привяжет реферера
  const ref = searchParams.get("ref");
  const refCookie =
    ref && /^[A-Za-z0-9]{4,20}$/.test(ref) ? ref.toUpperCase() : null;

  const withRefCookie = (response: NextResponse) => {
    if (refCookie) {
      response.cookies.set("ref_code", refCookie, {
        maxAge: REF_COOKIE_MAX_AGE,
        path: "/",
        sameSite: "lax",
      });
    }
    return response;
  };

  const isProtected = PROTECTED_PATHS.some((p) => pathname.startsWith(p));
  if (isProtected) {
    // Check for Django session cookie (set by Django on login)
    const sessionCookie =
      request.cookies.get("sessionid") ?? request.cookies.get("session");

    if (!sessionCookie) {
      const loginUrl = new URL("/login/", request.url);
      loginUrl.searchParams.set("next", pathname);
      return withRefCookie(NextResponse.redirect(loginUrl));
    }
  }

  return withRefCookie(NextResponse.next());
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\..*).*)"],
};
