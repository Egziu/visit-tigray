import Link from "next/link";
import { notFound } from "next/navigation";
import { Alert, Container, PageHeader } from "@/components/ui";
import { ServiceDown } from "@/components/site/content";
import { formatDuration } from "@/lib/format";
import { makeT } from "@/lib/i18n";
import { serverGet } from "@/lib/server-api";
import type { Plan } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function SharedItinerary({ params }: PageProps<"/[locale]/plan/shared/[token]">) {
  const { locale, token } = await params;
  const t = makeT(locale);
  const r = await serverGet<{ title: string; plan: Plan }>(`/api/shared-itineraries/${encodeURIComponent(token)}`, 0);
  if (!r.ok && (r.status === 404 || r.status === 410)) notFound();
  if (!r.ok) return <Container className="py-16"><ServiceDown locale={locale} message={r.message} /></Container>;
  const { title, plan } = r.data;
  return (
    <>
      <PageHeader title={title} lead={t("plan.lead")} />
      <Container className="space-y-6 py-10">
        <Alert tone={plan.mode === "virtual" ? "caution" : "info"} title={t("plan.notice")}>
          {plan.notice}
        </Alert>
        {plan.days.map((d) => (
          <section key={d.day} className="rounded-[var(--radius)] border border-line bg-surface p-6">
            <h2 className="text-3xl">{t("plan.day", { n: d.day })}</h2>
            <ol className="mt-4 space-y-3">
              {d.stops.length === 0 && <li className="text-muted">{t("plan.restDay")}</li>}
              {d.stops.map((s) => (
                <li key={s.slug}>
                  <Link className="font-display text-2xl hover:underline" href={`/${locale}/destinations/${s.slug}`}>
                    {s.name}
                  </Link>
                  <p className="text-sm text-muted">
                    {s.area} · {formatDuration(s.visit_duration_minutes, t("common.unknown"))}
                  </p>
                </li>
              ))}
            </ol>
            {d.unknowns.length > 0 && (
              <Alert tone="caution" title={t("plan.unknowns")} className="mt-4">
                <ul className="list-disc pl-5">
                  {d.unknowns.map((u) => (
                    <li key={u}>{u}</li>
                  ))}
                </ul>
              </Alert>
            )}
          </section>
        ))}
      </Container>
    </>
  );
}
