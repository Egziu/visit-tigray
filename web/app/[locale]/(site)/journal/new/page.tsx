import type { Metadata } from "next";
import { Container, PageHeader } from "@/components/ui";
import { JournalEditor } from "@/components/site/journal";
import { makeT } from "@/lib/i18n";

export async function generateMetadata({ params }: PageProps<"/[locale]/journal/new">): Promise<Metadata> {
  const { locale } = await params;
  return { title: makeT(locale)("journal.newTitle"), robots: { index: false } };
}

export default async function NewJournalPage({ params }: PageProps<"/[locale]/journal/new">) {
  const { locale } = await params;
  const t = makeT(locale);
  return (
    <>
      <PageHeader title={t("journal.newTitle")} lead={t("journal.newLead")} />
      <Container className="py-10">
        <JournalEditor />
      </Container>
    </>
  );
}
