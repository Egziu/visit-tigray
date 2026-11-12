import type { Metadata } from "next";
import { Badge, Container, EmptyState, PageHeader } from "@/components/ui";
import { ServiceDown } from "@/components/site/content";
import { formatDate } from "@/lib/format";
import { makeT } from "@/lib/i18n";
import { serverGet } from "@/lib/server-api";
import type { EventItem } from "@/lib/types";

export const revalidate = 60;

export async function generateMetadata({ params }: PageProps<"/[locale]/events">): Promise<Metadata> {
  const { locale } = await params;
  return { title: makeT(locale)("events.title") };
}

export default async function EventsPage({ params }: PageProps<"/[locale]/events">) {
  const { locale } = await params;
  const t = makeT(locale);
  const r = await serverGet<EventItem[]>(`/api/events?locale=${locale}`);
  return (
    <>
      <PageHeader title={t("events.title")} lead={t("events.lead")} />
      <Container className="py-10">
        {!r.ok ? (
          <ServiceDown locale={locale} message={r.message} />
        ) : r.data.length === 0 ? (
          <EmptyState title={t("events.none")} />
        ) : (
          <ul className="space-y-5">
            {r.data.map((e) => (
              <li key={e.slug} className="grid gap-6 rounded-[var(--radius)] border border-line bg-surface p-6 md:grid-cols-[220px_1fr]">
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-muted">{t("events.ethiopianDate")}</p>
                  <p className="font-display text-2xl text-earth">{e.ethiopian_date ?? t("events.dateTbc")}</p>
                  <p className="mt-2 text-xs uppercase tracking-[0.18em] text-muted">{t("events.gregorianDate")}</p>
                  <p>
                    {e.starts_on ? formatDate(e.starts_on, locale) : t("events.dateTbc")}
                    {e.ends_on && e.ends_on !== e.starts_on ? ` – ${formatDate(e.ends_on, locale)}` : ""}
                  </p>
                </div>
                <div>
                  <h2 className="text-3xl">{e.title}</h2>
                  {e.description && <p className="mt-2 text-muted">{e.description}</p>}
                  {e.date_note && <p className="mt-2 text-sm">{e.date_note}</p>}
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Badge tone="forest">{e.kind}</Badge>
                    {e.is_synthetic && <Badge tone="caution">{t("common.synthetic")}</Badge>}
                    {e.verified_at ? (
                      <Badge tone="success">{t("common.lastVerified", { date: formatDate(e.verified_at, locale) })}</Badge>
                    ) : (
                      <Badge>{t("common.notVerified")}</Badge>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Container>
    </>
  );
}
