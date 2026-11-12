import type { Metadata } from "next";
import { Container, PageHeader } from "@/components/ui";
import { JournalEditor } from "@/components/site/journal";
import { makeT } from "@/lib/i18n";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps<"/[locale]/journal/[id]/edit">): Promise<Metadata> {
  const { locale } = await params;
  return { title: makeT(locale)("journal.editTitle"), robots: { index: false } };
}

export default async function EditJournalPage({ params }: PageProps<"/[locale]/journal/[id]/edit">) {
  const { locale, id } = await params;
  const t = makeT(locale);
  return (
    <>
      <PageHeader title={t("journal.editTitle")} />
      <Container className="py-10">
        <JournalEditor id={id} />
      </Container>
    </>
  );
}
