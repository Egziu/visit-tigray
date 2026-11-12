import type { Metadata } from "next";
import { ButtonLink, Container, PageHeader } from "@/components/ui";
import { MemoryFeed } from "@/components/site/memories";
import { makeT } from "@/lib/i18n";

export async function generateMetadata({ params }: PageProps<"/[locale]/memories">): Promise<Metadata> {
  const { locale } = await params;
  return { title: makeT(locale)("memories.title") };
}

export default async function MemoriesPage({ params }: PageProps<"/[locale]/memories">) {
  const { locale } = await params;
  const t = makeT(locale);
  return (
    <>
      <PageHeader eyebrow={t("home.memoriesLead")} title={t("memories.title")} lead={t("memories.lead")}>
        <div className="mt-8">
          <ButtonLink href={`/${locale}/memories/new`} variant="gold">
            {t("memories.share")}
          </ButtonLink>
        </div>
      </PageHeader>
      <Container className="py-10">
        <MemoryFeed />
      </Container>
    </>
  );
}
