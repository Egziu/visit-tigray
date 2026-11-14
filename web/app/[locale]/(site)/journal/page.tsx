import type { Metadata } from "next";
import { Container, PageHeader } from "@/components/ui";
import { JournalFeed } from "@/components/site/journal";
import { makeT } from "@/lib/i18n";

export async function generateMetadata({ params }: PageProps<"/[locale]/journal">): Promise<Metadata> {
  const { locale } = await params;
  const t = makeT(locale);
  return { title: t("journal.title"), description: t("journal.lead") };
}

export default async function JournalPage({ params }: PageProps<"/[locale]/journal">) {
  const { locale } = await params;
  const t = makeT(locale);
  return (
    <>
      <PageHeader eyebrow={t("journal.eyebrow")} title={t("journal.title")} lead={t("journal.lead")} />
      <Container className="py-10">
        <JournalFeed />
      </Container>
    </>
  );
}
