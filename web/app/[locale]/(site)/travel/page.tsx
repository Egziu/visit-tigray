import type { Metadata } from "next";
import Link from "next/link";
import { Alert, Container, PageHeader } from "@/components/ui";
import { CalendarConverter } from "@/components/site/calendar-converter";
import { makeT } from "@/lib/i18n";

export async function generateMetadata({ params }: PageProps<"/[locale]/travel">): Promise<Metadata> {
  const { locale } = await params;
  return { title: makeT(locale)("travel.title") };
}

export default async function TravelPage({ params }: PageProps<"/[locale]/travel">) {
  const { locale } = await params;
  const t = makeT(locale);
  const blocks = [
    ["travel.etiquetteTitle", "travel.etiquetteBody"],
    ["travel.permitsTitle", "travel.permitsBody"],
    ["travel.connectivityTitle", "travel.connectivityBody"],
    ["travel.calendarTitle", "travel.calendarBody"],
  ] as const;
  return (
    <>
      <PageHeader title={t("travel.title")} lead={t("travel.lead")} />
      <Container className="space-y-10 py-12">
        <Alert tone="caution" title={t("advisory.title")}>
          {t("advisory.checkOfficial")}{" "}
          <Link href={`/${locale}/advisories`} className="underline">
            {t("advisory.title")}
          </Link>
        </Alert>
        <div className="grid gap-6 md:grid-cols-2">
          {blocks.map(([title, body]) => (
            <section key={title} className="rounded-[var(--radius)] border border-line bg-surface p-7">
              <h2 className="text-3xl">{t(title)}</h2>
              <p className="mt-3 text-muted">{t(body)}</p>
            </section>
          ))}
        </div>
        <CalendarConverter />
      </Container>
    </>
  );
}
