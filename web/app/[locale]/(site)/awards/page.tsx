import type { Metadata } from "next";
import { Alert, Container, PageHeader } from "@/components/ui";
import { CompetitionList } from "@/components/site/directory";
import { makeT } from "@/lib/i18n";

export async function generateMetadata({ params }: PageProps<"/[locale]/awards">): Promise<Metadata> {
  const { locale } = await params;
  return { title: makeT(locale)("awards.title") };
}

export default async function AwardsPage({ params }: PageProps<"/[locale]/awards">) {
  const { locale } = await params;
  const t = makeT(locale);
  return (
    <>
      <PageHeader title={t("awards.title")} lead={t("awards.lead")} />
      <Container className="space-y-8 py-10">
        <Alert tone="caution">{t("awards.notOpen")}</Alert>
        <CompetitionList />
      </Container>
    </>
  );
}
