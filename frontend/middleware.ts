import createIntlMiddleware from "next-intl/middleware";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { routing } from "./i18n/routing";

const PROTECTED_SEGMENTS = ["account", "keys", "studio"];
const REF_COOKIE_MAX_AGE = 60 * 60 * 24 * 30; // 30 дней

const handleIntl = createIntlMiddleware(routing);

// Матчит опциональный /ru|/en|/fa... в начале пути — нужен, чтобы проверять
// защищённые сегменты и строить redirect-URL независимо от локали.
const LOCALE_PREFIX_RE = new RegExp(`^/(${routing.locales.join("|")})(?=/|$)`);

function stripLocale(pathname: string): string {
  return pathname.replace(LOCALE_PREFIX_RE, "") || "/";
}

export function middleware(request: NextRequest) {
  const { pathname, searchParams } = request.nextUrl;

  // Реферальный код из ?ref=CODE сохраняем в cookie: регистрация и соцвход
  // идут на тот же домен, Django прочитает её и привяжет реферера
  const ref = searchParams.get("ref");
  const refCookie =
    ref && /^[A-Za-z0-9]{4,20}$/.test(ref) ? ref.toUpperCase() : null;

  // UTM-метки первого захода — тем же способом, что ref_code: cookie на
  // 30 дней, Django читает её один раз при регистрации (см. GROWTH_PLAN_RU.md
  // §2.5/§7#4). Без этого нельзя посчитать, какой канал (vc/DTF/каталоги/
  // TG-посевы) реально приводит платящих пользователей, а не просто визиты.
  const UTM_RE = /^[A-Za-z0-9_.-]{1,100}$/;
  const utmParams: Record<string, string> = {};
  for (const key of ["utm_source", "utm_medium", "utm_campaign"] as const) {
    const value = searchParams.get(key);
    if (value && UTM_RE.test(value)) utmParams[key] = value;
  }

  const withAttributionCookies = (response: NextResponse) => {
    if (refCookie) {
      response.cookies.set("ref_code", refCookie, {
        maxAge: REF_COOKIE_MAX_AGE,
        path: "/",
        sameSite: "lax",
      });
    }
    // Пишем только если пришли новые метки — не затираем уже сохранённые
    // предыдущим визитом, если пользователь потом перешёл по ссылке без UTM.
    if (Object.keys(utmParams).length > 0) {
      for (const [key, value] of Object.entries(utmParams)) {
        response.cookies.set(key, value, {
          maxAge: REF_COOKIE_MAX_AGE,
          path: "/",
          sameSite: "lax",
        });
      }
    }
    return response;
  };

  const bare = stripLocale(pathname);
  const isProtected = PROTECTED_SEGMENTS.some((seg) => bare.startsWith(`/${seg}`));

  if (isProtected) {
    // Check for Django session cookie (set by Django on login)
    const sessionCookie =
      request.cookies.get("sessionid") ?? request.cookies.get("session");

    if (!sessionCookie) {
      const localeMatch = pathname.match(LOCALE_PREFIX_RE);
      const prefix = localeMatch ? localeMatch[0] : "";
      const loginUrl = new URL(`${prefix}/login/`, request.url);
      loginUrl.searchParams.set("next", pathname);
      return withAttributionCookies(NextResponse.redirect(loginUrl));
    }
  }

  return withAttributionCookies(handleIntl(request));
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\..*).*)"],
};
