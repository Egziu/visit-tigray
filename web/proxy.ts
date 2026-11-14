import { NextResponse, type NextRequest } from "next/server";

const LOCALES = ["en", "ti", "am"];

function preferred(request: NextRequest): string {
  const cookie = request.cookies.get("vt_locale")?.value;
  if (cookie && LOCALES.includes(cookie)) return cookie;
  const header = request.headers.get("accept-language") ?? "";
  for (const part of header.split(",")) {
    const tag = part.split(";")[0].trim().toLowerCase().split("-")[0];
    if (LOCALES.includes(tag)) return tag;
  }
  return "en";
}

/** Redirect locale-less paths (e.g. "/" or "/destinations") to their localized equivalent. */
export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (LOCALES.some((l) => pathname === `/${l}` || pathname.startsWith(`/${l}/`))) return;
  const url = request.nextUrl.clone();
  url.pathname = `/${preferred(request)}${pathname === "/" ? "" : pathname}`;
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/((?!api|_next|icons|sw\\.js|manifest\\.webmanifest|favicon\\.ico|robots\\.txt|.*\\..*).*)"],
};
