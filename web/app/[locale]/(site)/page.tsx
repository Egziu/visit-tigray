import Link from "next/link";
import { ButtonLink, Container, EmptyState, SectionHeading } from "@/components/ui";
import { AdvisoryCard, DestinationCard, ServiceDown } from "@/components/site/content";
import { HeroLandscape, PatternBand } from "@/components/site/illustrations";
import { formatDate } from "@/lib/format";
import { makeT } from "@/lib/i18n";
import { serverGet } from "@/lib/server-api";
import type { Advisory, Destination, EventItem } from "@/lib/types";

export const revalidate = 60;

export default async function Home({ params }: PageProps<"/[locale]">) {
  const { locale } = await params;
  const t = makeT(locale);
  const [dest, events, advisories] = await Promise.all([
    serverGet<{ items: Destination[] }>(`/api/destinations?locale=${locale}&limit=6`),
    serverGet<EventItem[]>(`/api/events?locale=${locale}`),
    serverGet<Advisory[]>(`/api/advisories?locale=${locale}`),
  ]);
  const regionWide = advisories.ok ? advisories.data.filter((a) => a.region_wide) : [];

  return (
    <>
      <section className="relative isolate overflow-hidden bg-[#102d27] text-[#f7f2e8]" aria-labelledby="hero-title">
        <HeroLandscape className="absolute inset-0 -z-10 h-full w-full opacity-95" />
        <div className="absolute inset-0 -z-10 bg-gradient-to-r from-[#0c1512]/85 via-[#0c1512]/45 to-transparent" />
        <Container className="flex min-h-[78vh] flex-col justify-end pb-16 pt-28 sm:pb-24">
          <p className="reveal text-xs font-semibold uppercase tracking-[0.3em] text-[#e2c48f]">{t("home.eyebrow")}</p>
          <h1 id="hero-title" className="reveal mt-5 max-w-4xl text-5xl leading-[1.02] sm:text-7xl">
            {t("home.title")}
          </h1>
          <p className="reveal reveal-delay mt-6 max-w-2xl text-lg text-[#e4dccd]">{t("home.lead")}</p>
          <div className="reveal reveal-delay mt-9 flex flex-wrap gap-3">
            <ButtonLink href={`/${locale}/destinations`} variant="gold" size="lg">
              {t("home.ctaDiscover")} <span aria-hidden="true">↗</span>
            </ButtonLink>
            <ButtonLink href={`/${locale}/guide`} variant="ghost" size="lg" className="border border-white/40 text-white hover:bg-white/10">
              {t("home.ctaGuide")}
            </ButtonLink>
          </div>
          <p className="mt-10 text-[0.65rem] uppercase tracking-[0.25em] text-white/60">{t("common.illustration")}</p>
        </Container>
      </section>

      {regionWide.length > 0 && (
        <Container className="mt-10 space-y-3">
          {regionWide.map((a) => (
            <AdvisoryCard key={a.id} a={a} locale={locale} />
          ))}
        </Container>
      )}

      <section className="py-20 sm:py-28" aria-labelledby="mission">
        <Container className="grid gap-10 md:grid-cols-[1fr_1.2fr] md:items-end">
          <h2 id="mission" className="text-5xl sm:text-6xl">
            {t("home.missionTitle")}
          </h2>
          <p className="text-lg text-muted">{t("home.missionBody")}</p>
        </Container>
      </section>

      <section aria-labelledby="featured" className="pb-8">
        <Container>
          <div className="flex flex-wrap items-end justify-between gap-4">
            <SectionHeading id="featured" eyebrow={t("nav.destinations")} title={t("home.featured")} />
            <Link href={`/${locale}/destinations`} className="mb-10 text-sm font-medium underline">
              {t("common.viewAll")}
            </Link>
          </div>
          {!dest.ok ? (
            <ServiceDown locale={locale} />
          ) : dest.data.items.length === 0 ? (
            <EmptyState title={t("home.noDestinations")} />
          ) : (
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {dest.data.items.map((d) => (
                <DestinationCard key={d.slug} d={d} locale={locale} />
              ))}
            </div>
          )}
        </Container>
      </section>

      <section className="mt-24 bg-surface-2/70 py-20" aria-labelledby="events-strip">
        <Container>
          <SectionHeading id="events-strip" eyebrow={t("nav.events")} title={t("home.upcoming")} lead={t("events.lead")} />
          {events.ok && events.data.length > 0 ? (
            <ul className="grid gap-4 md:grid-cols-3">
              {events.data.slice(0, 3).map((e) => (
                <li key={e.slug} className="rounded-[var(--radius)] border border-line bg-surface p-6">
                  <p className="font-display text-2xl">{e.title}</p>
                  <p className="mt-2 text-sm text-earth">{e.ethiopian_date ?? t("events.dateTbc")}</p>
                  {e.starts_on && <p className="text-sm text-muted">{formatDate(e.starts_on, locale)}</p>}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-muted">{events.ok ? t("events.none") : t("common.serviceDown")}</p>
          )}
          <Link href={`/${locale}/events`} className="mt-8 inline-block text-sm font-medium underline">
            {t("common.viewAll")}
          </Link>
        </Container>
      </section>

      <section className="py-24" aria-label={t("home.guideTitle")}>
        <Container className="grid gap-6 md:grid-cols-3">
          <Feature title={t("home.guideTitle")} body={t("home.guideBody")} href={`/${locale}/guide`} cta={t("home.ctaGuide")} />
          <Feature title={t("home.planTitle")} body={t("home.planBody")} href={`/${locale}/plan`} cta={t("plan.title")} />
          <Feature title={t("home.memoriesTitle")} body={t("home.memoriesLead")} href={`/${locale}/memories`} cta={t("memories.share")} />
        </Container>
      </section>
      <PatternBand className="mx-auto h-3 w-48 text-sandstone" />
    </>
  );
}

function Feature({ title, body, href, cta }: { title: string; body: string; href: string; cta: string }) {
  return (
    <div className="flex flex-col rounded-[var(--radius)] border border-line bg-surface p-8">
      <h3 className="text-3xl">{title}</h3>
      <p className="mt-3 flex-1 text-muted">{body}</p>
      <Link href={href} className="mt-6 text-sm font-semibold text-earth underline">
        {cta} →
      </Link>
    </div>
  );
}
