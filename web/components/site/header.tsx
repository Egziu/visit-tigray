"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { cn } from "@/components/ui";
import { LOCALE_NAMES, LOCALES, type MsgKey } from "@/lib/i18n";
import { api } from "@/lib/api";
import { Emblem } from "./illustrations";
import { useI18n, useSession } from "./providers";

const NAV: { href: string; key: MsgKey }[] = [
  { href: "/destinations", key: "nav.destinations" },
  { href: "/map", key: "nav.map" },
  { href: "/events", key: "nav.events" },
  { href: "/guide", key: "nav.guide" },
  { href: "/plan", key: "nav.plan" },
  { href: "/memories", key: "nav.memories" },
  { href: "/providers", key: "nav.providers" },
];

export function LanguageSwitcher() {
  const { locale, t } = useI18n();
  const pathname = usePathname();
  const router = useRouter();
  return (
    <label className="flex items-center gap-2 text-sm">
      <span className="sr-only">{t("nav.language")}</span>
      <select
        value={locale}
        onChange={(e) => {
          const next = e.target.value;
          document.cookie = `vt_locale=${next}; path=/; max-age=31536000; samesite=lax`;
          router.push(pathname.replace(/^\/(en|ti|am)(?=\/|$)/, `/${next}`));
        }}
        className="min-h-[40px] rounded-full border border-line bg-surface px-3 py-1.5 text-sm"
        aria-label={t("nav.language")}
      >
        {LOCALES.map((l) => (
          <option key={l} value={l} lang={l}>
            {LOCALE_NAMES[l]}
          </option>
        ))}
      </select>
    </label>
  );
}

type Theme = "system" | "light" | "dark";

export function ThemeToggle() {
  const { t } = useI18n();
  const [theme, setTheme] = useState<Theme>("system");
  useEffect(() => {
    const saved = localStorage.getItem("vt_theme");
    if (saved === "light" || saved === "dark") setTheme(saved);
  }, []);
  function apply(next: Theme) {
    setTheme(next);
    if (next === "system") {
      localStorage.removeItem("vt_theme");
      delete document.documentElement.dataset.theme;
    } else {
      localStorage.setItem("vt_theme", next);
      document.documentElement.dataset.theme = next;
    }
  }
  const order: Theme[] = ["system", "light", "dark"];
  const label = { system: t("nav.themeSystem"), light: t("nav.themeLight"), dark: t("nav.themeDark") }[theme];
  return (
    <button
      type="button"
      onClick={() => apply(order[(order.indexOf(theme) + 1) % order.length])}
      className="min-h-[40px] rounded-full border border-line bg-surface px-3 py-1.5 text-sm"
      aria-label={`${t("nav.theme")}: ${label}`}
      title={`${t("nav.theme")}: ${label}`}
    >
      <span aria-hidden="true">{theme === "dark" ? "☾" : theme === "light" ? "☀" : "◐"}</span>
      <span className="ml-1.5 hidden xl:inline">{label}</span>
    </button>
  );
}

export function DataSaverToggle() {
  const { t } = useI18n();
  const [on, setOn] = useState(false);
  useEffect(() => setOn(localStorage.getItem("vt_saver") === "on"), []);
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={() => {
        const next = !on;
        setOn(next);
        if (next) {
          localStorage.setItem("vt_saver", "on");
          document.documentElement.dataset.saver = "on";
        } else {
          localStorage.removeItem("vt_saver");
          delete document.documentElement.dataset.saver;
        }
      }}
      className={cn(
        "min-h-[40px] rounded-full border px-3 py-1.5 text-sm",
        on ? "border-forest bg-forest text-on-forest" : "border-line bg-surface",
      )}
    >
      {t("nav.dataSaver")}
    </button>
  );
}

export function Header() {
  const { locale, t } = useI18n();
  const { me, refresh } = useSession();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  useEffect(() => setOpen(false), [pathname]);
  const isStaff = !!me && (me.permissions.length > 0 || me.pending_permissions.length > 0);

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-bg/90 backdrop-blur supports-[backdrop-filter]:bg-bg/75">
      <div className="mx-auto flex h-[72px] max-w-7xl items-center gap-4 px-5 sm:px-8">
        <Link href={`/${locale}`} className="flex items-center gap-3" aria-label={t("brand.home")}>
          <Emblem className="h-9 w-9 text-forest" />
          <span className="leading-none">
            <span className="block font-display text-xl tracking-wide">{t("brand.name")}</span>
            <span className="block text-[0.68rem] uppercase tracking-[0.2em] text-muted">{t("brand.tagline")}</span>
          </span>
        </Link>
        <nav aria-label={t("nav.primary")} className="ml-auto hidden lg:block">
          <ul className="flex items-center gap-1">
            {NAV.map((n) => {
              const href = `/${locale}${n.href}`;
              const active = pathname.startsWith(href);
              return (
                <li key={n.href}>
                  <Link
                    href={href}
                    aria-current={active ? "page" : undefined}
                    className={cn("rounded-full px-3 py-2 text-[0.92rem] hover:bg-surface-2", active && "bg-surface-2 font-medium")}
                  >
                    {t(n.key)}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
        <div className="ml-auto hidden items-center gap-2 lg:ml-2 lg:flex">
          <LanguageSwitcher />
          <ThemeToggle />
          {me ? (
            <>
              {isStaff && (
                <Link href={`/${locale}/bureau`} className="rounded-full px-3 py-2 text-sm hover:bg-surface-2">
                  {t("nav.bureau")}
                </Link>
              )}
              <Link href={`/${locale}/account`} className="rounded-full border border-line px-3 py-2 text-sm">
                {me.display_name}
              </Link>
            </>
          ) : (
            <Link href={`/${locale}/account`} className="rounded-full bg-forest px-4 py-2 text-sm text-on-forest">
              {t("common.signIn")}
            </Link>
          )}
        </div>
        <button
          type="button"
          className="ml-auto min-h-[44px] rounded-full border border-line px-4 py-2 text-sm lg:hidden"
          aria-expanded={open}
          aria-controls="mobile-menu"
          onClick={() => setOpen((o) => !o)}
        >
          {t("nav.menu")}
        </button>
      </div>
      {open && (
        <div id="mobile-menu" className="border-t border-line bg-bg px-5 pb-6 lg:hidden">
          <nav aria-label={t("nav.primary")}>
            <ul className="flex flex-col py-3">
              {[...NAV, { href: "/awards", key: "nav.awards" as MsgKey }, { href: "/travel", key: "nav.travel" as MsgKey }, { href: "/offline", key: "nav.offline" as MsgKey }].map((n) => (
                <li key={n.href}>
                  <Link href={`/${locale}${n.href}`} className="block rounded-lg px-2 py-3 text-lg">
                    {t(n.key)}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
          <div className="flex flex-wrap items-center gap-2">
            <LanguageSwitcher />
            <ThemeToggle />
            <DataSaverToggle />
            <Link href={`/${locale}/account`} className="rounded-full bg-forest px-4 py-2 text-sm text-on-forest">
              {me ? t("common.account") : t("common.signIn")}
            </Link>
            {me && (
              <button
                type="button"
                className="rounded-full border border-line px-4 py-2 text-sm"
                onClick={async () => {
                  await api("/auth/logout", { method: "POST" }).catch(() => undefined);
                  await refresh();
                }}
              >
                {t("common.signOut")}
              </button>
            )}
          </div>
        </div>
      )}
    </header>
  );
}

export function TranslationNotice() {
  const { locale, t } = useI18n();
  if (locale === "en") return null;
  return (
    <div className="border-b border-line bg-surface-2 px-5 py-2 text-center text-sm text-muted" role="note">
      {t("common.translationReview")}
    </div>
  );
}
