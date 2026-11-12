import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Alert, ButtonLink, Container } from "@/components/ui";
import { AdvisoryCard, MediaFigure, ServiceDown, TrustBadges } from "@/components/site/content";
import { CardArt } from "@/components/site/illustrations";
import { SaveOffline } from "@/components/site/pwa";
import { formatDate, formatDuration } from "@/lib/format";
import { makeT } from "@/lib/i18n";
import { serverGet } from "@/lib/server-api";
import type { Destination, TriState } from "@/lib/types";

// Rendered on demand (no build-time API dependency); data fetches revalidate every 60 s.
export const dynamic = "force-dynamic";

async function load(slug: string, locale: string) {
  return serverGet<Destination>(`/api/destinations/${encodeURIComponent(slug)}?locale=${locale}`);
}

export async function generateMetadata({ params }: PageProps<"/[locale]/destinations/[slug]">): Promise<Metadata> {
  const { locale, slug } = await params;
  const r = await load(slug, locale);
  return r.ok ? { title: r.data.name, description: r.data.summary } : { title: makeT(locale)("destinations.title") };
}

export default async function DestinationPage({ params }: PageProps<"/[locale]/destinations/[slug]">) {
  const { locale, slug } = await params;
  const t = makeT(locale);
  const r = await load(slug, locale);
  if (!r.ok && r.status === 404) notFound();
  if (!r.ok) {
    return (
      <Container className="py-20">
        <ServiceDown locale={locale} message={r.message} />
        <p className="mt-6">
          <Link className="underline" href={`/${locale}/offline`}>
            {t("nav.offline")}
          </Link>
        </p>
      </Container>
    );
  }
  const d = r.data;
  const tri = (v: TriState | undefined) => (v === "yes" ? t("common.yes") : v === "no" ? t("common.no") : t("common.unknown"));
  const hero = d.media.find((m) => m.is_hero) ?? d.media[0];

  return (
    <article lang={d.locale ?? locale}>
      <header className="border-b border-line">
        <div className="relative h-[42vh] min-h-[280px] overflow-hidden bg-surface-2">
          {hero ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={hero.urls.lg ?? hero.urls.md} alt={hero.alt_text_i18n?.[locale] ?? hero.alt_text_i18n?.en ?? ""} className="saver-hide h-full w-full object-cover" />
          ) : (
            <>
              <CardArt seed={d.slug} className="h-full w-full" />
              <span className="absolute bottom-3 right-4 rounded bg-black/45 px-2 py-0.5 text-[0.65rem] uppercase tracking-wider text-white">{t("common.illustration")}</span>
            </>
          )}
        </div>
        <Container className="py-12">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-earth">
            {[d.eyebrow || d.category?.name, d.area].filter(Boolean).join(" · ")}
          </p>
          <h1 className="reveal mt-3 text-5xl sm:text-7xl">{d.name}</h1>
          <p className="reveal reveal-delay mt-5 max-w-3xl text-xl text-muted">{d.summary}</p>
          <div className="mt-6">
            <TrustBadges d={d} locale={locale} />
          </div>
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <SaveOffline item={{ key: `destination:${d.slug}:${locale}`, kind: "destination", title: d.name, href: `/${locale}/destinations/${d.slug}`, locale, sourceUpdatedAt: d.verified_at, data: d }} />
            <ButtonLink href={`/${locale}/guide?destination=${d.slug}`} variant="secondary" size="sm">
              {t("destinations.askGuide", { name: d.name })}
            </ButtonLink>
            <ButtonLink href={`/${locale}/plan?include=${d.slug}`} variant="secondary" size="sm">
              {t("destinations.planWith")}
            </ButtonLink>
          </div>
        </Container>
      </header>

      <Container className="grid gap-14 py-14 lg:grid-cols-[1.6fr_1fr]">
        <div className="space-y-12">
          {d.is_synthetic && <Alert tone="caution" title={t("common.synthetic")}>{t("common.syntheticNote")}</Alert>}
          {d.advisories && d.advisories.length > 0 && (
            <section className="space-y-3" aria-label={t("advisory.title")}>
              {d.advisories.map((a) => (
                <AdvisoryCard key={a.id} a={a} locale={locale} />
              ))}
            </section>
          )}
          <section aria-labelledby="overview">
            <h2 id="overview" className="text-3xl">
              {t("destinations.overview")}
            </h2>
            <div className="prose-vt mt-4 text-lg">{d.body || d.summary}</div>
          </section>

          {d.timeline && d.timeline.length > 0 && (
            <section aria-labelledby="timeline">
              <h2 id="timeline" className="text-3xl">
                {t("destinations.history")}
              </h2>
              <ol className="mt-6 border-l-2 border-sandstone pl-6">
                {d.timeline.map((item, i) => (
                  <li key={i} className="relative pb-6">
                    <span className="absolute -left-[31px] top-1.5 h-3 w-3 rounded-full bg-sandstone" aria-hidden="true" />
                    <p className="text-sm font-semibold text-earth">{item.period}</p>
                    <p>{item.label_i18n?.[locale] ?? item.label_i18n?.en ?? item.label}</p>
                  </li>
                ))}
              </ol>
            </section>
          )}

          {d.etiquette && (
            <section aria-labelledby="etiquette">
              <h2 id="etiquette" className="text-3xl">
                {t("destinations.etiquette")}
              </h2>
              <div className="prose-vt mt-4">{d.etiquette}</div>
            </section>
          )}

          {d.media.length > 0 && (
            <section aria-labelledby="gallery">
              <h2 id="gallery" className="text-3xl">
                {t("destinations.gallery")}
              </h2>
              <div className="mt-6 grid gap-5 sm:grid-cols-2">
                {d.media.map((m) => (
                  <MediaFigure key={m.id} m={m} locale={locale} />
                ))}
              </div>
            </section>
          )}

          <section aria-labelledby="sources">
            <h2 id="sources" className="text-3xl">
              {t("destinations.sources")}
            </h2>
            {d.sources.length === 0 ? (
              <p className="mt-3 text-muted">{t("destinations.noSources")}</p>
            ) : (
              <ol className="mt-4 list-decimal space-y-3 pl-6">
                {d.sources.map((s, i) => (
                  <li key={i}>
                    {s.url ? (
                      <a href={s.url} target="_blank" rel="noopener noreferrer" className="underline">
                        {s.title}
                      </a>
                    ) : (
                      s.title
                    )}
                    <span className="text-muted">{[s.author, s.publisher, s.year].filter(Boolean).map((x) => ` · ${x}`).join("")}</span>
                    {s.note && <p className="text-sm text-muted">{s.note}</p>}
                  </li>
                ))}
              </ol>
            )}
          </section>
        </div>

        <aside className="space-y-6" aria-label={t("destinations.practical")}>
          <div className="rounded-[var(--radius)] border border-line bg-surface p-6">
            <h2 className="text-2xl">{t("destinations.practical")}</h2>
            <dl className="mt-4 space-y-4 text-[0.95rem]">
              <Fact label={t("destinations.duration")} value={formatDuration(d.visit_duration_minutes, t("common.unknown"))} unknown={d.visit_duration_minutes === null} />
              <Fact label={t("destinations.permit")} value={tri(d.permit_required)} unknown={d.permit_required === "unknown"} />
              {d.permit_authority && <Fact label={t("destinations.permitAuthority")} value={d.permit_authority} />}
            </dl>
          </div>
          <div className="rounded-[var(--radius)] border border-line bg-surface p-6">
            <h2 className="text-2xl">{t("destinations.accessibility")}</h2>
            <dl className="mt-4 space-y-4 text-[0.95rem]">
              <Fact label={t("destinations.stepFree")} value={tri(d.accessibility?.step_free)} unknown={!d.accessibility?.step_free || d.accessibility.step_free === "unknown"} />
              <Fact label={t("destinations.terrain")} value={knownOr(d.accessibility?.terrain, t("common.unknown"))} unknown={!known(d.accessibility?.terrain)} />
              <Fact label={t("destinations.facilities")} value={knownOr(d.accessibility?.facilities, t("common.unknown"))} unknown={!known(d.accessibility?.facilities)} />
            </dl>
            {d.accessibility_notes && <p className="mt-4 text-sm text-muted">{d.accessibility_notes}</p>}
          </div>
          <div className="rounded-[var(--radius)] border border-line bg-surface p-6">
            <h2 className="text-2xl">{t("destinations.location")}</h2>
            {d.coordinates ? (
              <>
                <p className="mt-3 font-mono text-sm">
                  {d.coordinates.lat.toFixed(d.coordinates.precision === "exact" ? 4 : 1)}, {d.coordinates.lng.toFixed(d.coordinates.precision === "exact" ? 4 : 1)}
                </p>
                {d.coordinates.precision === "approximate" && <p className="mt-2 text-sm text-muted">{t("destinations.approximate")}</p>}
                <Link href={`/${locale}/map#${d.slug}`} className="mt-3 inline-block text-sm underline">
                  {t("nav.map")}
                </Link>
              </>
            ) : (
              <p className="mt-3 text-sm text-muted">{t("destinations.hiddenLocation")}</p>
            )}
          </div>
          <div className="rounded-[var(--radius)] border border-line bg-surface p-6">
            <h2 className="text-2xl">{t("destinations.contact")}</h2>
            {d.contact && Object.keys(d.contact).length > 0 ? (
              <dl className="mt-3 space-y-2 text-sm">
                {Object.entries(d.contact).map(([k, v]) => (
                  <div key={k}>
                    <dt className="text-muted">{k}</dt>
                    <dd>{v}</dd>
                  </div>
                ))}
              </dl>
            ) : (
              <p className="mt-3 text-sm text-muted">{t("destinations.noContact")}</p>
            )}
          </div>
          {d.heritage_designations && d.heritage_designations.length > 0 && (
            <div className="rounded-[var(--radius)] border border-line bg-surface p-6">
              <h2 className="text-2xl">{t("destinations.designations")}</h2>
              <ul className="mt-3 space-y-2 text-sm">
                {d.heritage_designations.map((h, i) => (
                  <li key={i}>{[h.name, h.body, h.year].filter(Boolean).join(" · ")}</li>
                ))}
              </ul>
            </div>
          )}
          {d.events && d.events.length > 0 && (
            <div className="rounded-[var(--radius)] border border-line bg-surface p-6">
              <h2 className="text-2xl">{t("destinations.events")}</h2>
              <ul className="mt-3 space-y-3 text-sm">
                {d.events.map((e) => (
                  <li key={e.slug}>
                    <p className="font-medium">{e.title}</p>
                    <p className="text-muted">
                      {e.ethiopian_date ?? t("events.dateTbc")}
                      {e.starts_on ? ` · ${formatDate(e.starts_on, locale)}` : ""}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <p className="text-sm text-muted">{t("advisory.checkOfficial")}</p>
        </aside>
      </Container>
    </article>
  );
}

function known(v?: string) {
  return !!v && v !== "unknown";
}
function knownOr(v: string | undefined, unknownLabel: string) {
  return known(v) ? (v as string) : unknownLabel;
}

function Fact({ label, value, unknown }: { label: string; value: string; unknown?: boolean }) {
  return (
    <div>
      <dt className="text-sm text-muted">{label}</dt>
      <dd className={unknown ? "mt-0.5 font-medium italic text-caution" : "mt-0.5 font-medium"}>{value}</dd>
    </div>
  );
}
