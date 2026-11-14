import type { Metadata } from "next";
import { Container, PageHeader } from "@/components/ui";
import { NewMemoryForm } from "@/components/site/memories";
import { makeT } from "@/lib/i18n";

export async function generateMetadata({ params }: PageProps<"/[locale]/memories/new">): Promise<Metadata> {
  const { locale } = await params;
  return { title: makeT(locale)("memories.newTitle") };
}

export default async function NewMemoryPage({ params }: PageProps<"/[locale]/memories/new">) {
  const { locale } = await params;
  const t = makeT(locale);
  return (
    <>
      <PageHeader title={t("memories.newTitle")} lead={t("memories.lead")} />
      <Container className="py-10">
        <NewMemoryForm />
      </Container>
    </>
  );
}
