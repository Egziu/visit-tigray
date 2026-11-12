"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Alert, Loading, cn } from "@/components/ui";
import { MfaSetup } from "@/components/site/account";
import { LanguageSwitcher, ThemeToggle } from "@/components/site/header";
import { Emblem } from "@/components/site/illustrations";
import { useI18n, useSession } from "@/components/site/providers";
import { api } from "@/lib/api";
import type { MsgKey } from "@/lib/i18n";

export const BUREAU_NAV: { href: string; key: MsgKey; perms: string[] }[] = [
  { href: "", key: "bureau.nav.dashboard", perms: [] },
  { href: "/destinations", key: "bureau.nav.destinations", perms: ["destinations.read_draft"] },
  { href: "/translations", key: "bureau.nav.translations", perms: ["destinations.read_draft"] },
  { href: "/freshness", key: "bureau.nav.freshness", perms: ["destinations.read_draft"] },
  { href: "/advisories", key: "bureau.nav.advisories", perms: ["advisories.manage"] },
  { href: "/events", key: "bureau.nav.events", perms: ["events.manage"] },
  { href: "/media", key: "bureau.nav.media", perms: ["media.manage"] },
  { href: "/moderation", key: "bureau.nav.moderation", perms: ["community.moderate"] },
  { href: "/knowledge", key: "bureau.nav.knowledge", perms: ["knowledge.upload", "knowledge.review", "knowledge.publish"] },
  { href: "/ai", key: "bureau.nav.ai", perms: ["ai.admin"] },
  { href: "/analytics", key: "bureau.nav.analytics", perms: ["analytics.view"] },
  { href: "/assistant", key: "bureau.nav.assistant", perms: ["bureau.assistant"] },
  { href: "/users", key: "bureau.nav.users", perms: ["users.manage", "roles.manage"] },
  { href: "/audit", key: "bureau.nav.audit", perms: ["audit.view"] },
  { href: "/settings", key: "bureau.nav.settings", perms: ["settings.manage"] },
];

export function BureauShell({ children }: { children: ReactNode }) {
  const { t, locale } = useI18n();
  const { me, loading, refresh } = useSession();
  const pathname = usePathname();
  const router = useRouter();
  const [q, setQ] = useState("");
  const [hitState, setHitState] = useState<{ q: string; hits: { id: string; slug: string }[] }>({ q: "", hits: [] });
  const base = `/${locale}/bureau`;

  const nav = useMemo(
    () => BUREAU_NAV.filter((n) => n.perms.length === 0 || n.perms.some((p) => me?.permissions.includes(p))),
    [me],
  );
  const matches = q ? nav.filter((n) => t(n.key).toLowerCase().includes(q.toLowerCase())) : [];

  const canSearchDest = !!me?.permissions.includes("destinations.read_draft");
  useEffect(() => {
    if (q.length < 2 || !canSearchDest) return;
    const id = setTimeout(() => {
      api<{ id: string; slug: string }[]>("/bureau/destinations")
        .then((all) => setHitState({ q, hits: all.filter((d) => d.slug.includes(q.toLowerCase())).slice(0, 6) }))
        .catch(() => setHitState({ q, hits: [] }));
    }, 250);
    return () => clearTimeout(id);
  }, [q, canSearchDest]);
  const destHits = q.length >= 2 && hitState.q === q ? hitState.hits : [];

  let gate: ReactNode = null;
  if (loading) gate = <Loading label={t("common.loading")} />;
  else if (!me)
    gate = (
      <Alert tone="info" title={t("bureau.signInStaff")}>
        <Link className="underline" href={`/${locale}/account`}>
          {t("common.signIn")}
        </Link>
      </Alert>
    );
  else if (me.pending_permissions.length > 0 && !me.mfa_verified)
    gate = (
      <div className="max-w-xl space-y-6">
        <Alert tone="caution">{t("bureau.mfaGate")}</Alert>
        {me.mfa_enabled ? (
          <Link className="underline" href={`/${locale}/account`}>
            {t("account.mfaTitle")}
          </Link>
        ) : (
          <MfaSetup onDone={() => void refresh()} />
        )}
      </div>
    );
  else if (me.permissions.length === 0) gate = <Alert tone="caution">{t("bureau.noAccess")}</Alert>;

  return (
    <div className="min-h-screen bg-bg lg:grid lg:grid-cols-[264px_1fr]">
      <a href="#bureau-main" className="skip-link">
        {t("common.skip")}
      </a>
      <aside className="border-b border-line bg-surface lg:sticky lg:top-0 lg:h-screen lg:overflow-y-auto lg:border-b-0 lg:border-r">
        <div className="flex items-center gap-3 px-5 py-5">
          <Emblem className="h-8 w-8 text-forest" />
          <div>
            <p className="font-display text-lg leading-none">{t("brand.name")}</p>
            <p className="text-[0.68rem] uppercase tracking-[0.18em] text-muted">{t("bureau.title")}</p>
          </div>
        </div>
        {me && !gate && (
          <div className="relative px-4 pb-3">
            <label htmlFor="bureau-search" className="sr-only">
              {t("bureau.searchNav")}
            </label>
            <input
              id="bureau-search"
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder={t("bureau.searchPlaceholder")}
              className="min-h-[40px] w-full rounded-lg border border-line bg-bg px-3 text-sm"
              onKeyDown={(e) => {
                if (e.key === "Enter" && matches[0]) router.push(`${base}${matches[0].href}`);
              }}
            />
            {(matches.length > 0 || destHits.length > 0) && (
              <ul className="absolute left-4 right-4 z-10 mt-1 rounded-lg border border-line bg-surface py-1 text-sm shadow-lg">
                {matches.map((m) => (
                  <li key={m.href}>
                    <Link href={`${base}${m.href}`} className="block px-3 py-2 hover:bg-surface-2" onClick={() => setQ("")}>
                      {t(m.key)}
                    </Link>
                  </li>
                ))}
                {destHits.map((d) => (
                  <li key={d.id}>
                    <Link href={`${base}/destinations/${d.id}`} className="block px-3 py-2 hover:bg-surface-2" onClick={() => setQ("")}>
                      ◦ {d.slug}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
        <nav aria-label={t("bureau.title")} className="px-3 pb-4">
          <ul className="flex gap-1 overflow-x-auto lg:flex-col">
            {(gate ? [] : nav).map((n) => {
              const href = `${base}${n.href}`;
              const active = n.href === "" ? pathname === base : pathname.startsWith(href);
              return (
                <li key={n.href} className="shrink-0">
                  <Link
                    href={href}
                    aria-current={active ? "page" : undefined}
                    className={cn("block whitespace-nowrap rounded-lg px-3 py-2 text-sm", active ? "bg-forest text-on-forest" : "hover:bg-surface-2")}
                  >
                    {t(n.key)}
                  </Link>
                </li>
              );
            })}
            <li className="shrink-0 lg:mt-4">
              <Link href={`/${locale}`} className="block whitespace-nowrap rounded-lg px-3 py-2 text-sm text-muted hover:bg-surface-2">
                ← {t("bureau.nav.public")}
              </Link>
            </li>
          </ul>
        </nav>
        <div className="flex flex-wrap gap-2 px-4 pb-6">
          <LanguageSwitcher />
          <ThemeToggle />
        </div>
      </aside>
      <main id="bureau-main" tabIndex={-1} className="min-w-0 px-5 py-8 outline-none sm:px-10">
        {gate ?? children}
      </main>
    </div>
  );
}

export function BureauTitle({ title, lead, actions }: { title: ReactNode; lead?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-4xl">{title}</h1>
        {lead && <p className="mt-2 max-w-2xl text-muted">{lead}</p>}
      </div>
      {actions}
    </div>
  );
}
