import type { Metadata } from "next";
import Link from "next/link";
import { Alert, Container, PageHeader } from "@/components/ui";
import { AdvisoryCard, ServiceDown } from "@/components/site/content";
import { makeT } from "@/lib/i18n";
import { serverGet } from "@/lib/server-api";
import type { Advisory } from "@/lib/types";

export const revalidate = 60;

export async function generateMetadata({ params }: PageProps<"/[locale]/advisories">): Promise<Metadata> {
  const { locale } = await params;
  return { title: makeT(locale)("advisory.title") };
}

export default async function AdvisoriesPage({ params }: PageProps<"/[locale]/advisories">) {
  const { locale } = await params;
  const t = makeT(locale);
  const r = await serverGet<Advisory[]>(`/api/advisories?locale=${locale}`);
  return (
    <>
      <PageHeader title={t("advisory.title")} lead={t("advisory.checkOfficial")} />
      <Container className="space-y-4 py-10">
        {!r.ok ? (
          <ServiceDown locale={locale} message={r.message} />
        ) : r.data.length === 0 ? (
          <Alert tone="info">{t("advisory.none")}</Alert>
        ) : (
          r.data.map((a) => <AdvisoryCard key={a.id} a={a} locale={locale} />)
        )}
        <p className="pt-4">
          <Link className="underline" href={`/${locale}/travel`}>
            {t("travel.title")} →
          </Link>
        </p>
      </Container>
    </>
  );
}
