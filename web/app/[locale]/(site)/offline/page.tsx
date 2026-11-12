import type { Metadata } from "next";
import { Container, PageHeader } from "@/components/ui";
import { OfflineLibrary } from "@/components/site/offline-library";
import { makeT } from "@/lib/i18n";

export async function generateMetadata({ params }: PageProps<"/[locale]/offline">): Promise<Metadata> {
  const { locale } = await params;
  return { title: makeT(locale)("offline.title") };
}

export default async function OfflinePage({ params }: PageProps<"/[locale]/offline">) {
  const { locale } = await params;
  const t = makeT(locale);
  return (
    <>
      <PageHeader title={t("offline.title")} lead={t("offline.lead")} />
      <Container className="py-10">
        <OfflineLibrary />
      </Container>
    </>
  );
}
