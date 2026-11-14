"use client";

import Link from "next/link";
import { useI18n } from "@/components/site/providers";

// Rendered inside the [locale] root layout, so <html lang> and fonts are preserved.
export default function NotFound() {
  const { t, locale } = useI18n();
  return (
    <main id="main" className="mx-auto flex min-h-[70vh] max-w-2xl flex-col items-start justify-center px-5 py-20">
      <p className="text-xs font-semibold uppercase tracking-[0.22em] text-earth">404</p>
      <h1 className="mt-3 text-5xl">{t("common.pageNotFound")}</h1>
      <div className="mt-8 flex flex-wrap gap-4">
        <Link href={`/${locale}`} className="underline">
          {t("brand.home")}
        </Link>
        <Link href={`/${locale}/destinations`} className="underline">
          {t("nav.destinations")}
        </Link>
        <Link href={`/${locale}/offline`} className="underline">
          {t("nav.offline")}
        </Link>
      </div>
    </main>
  );
}
