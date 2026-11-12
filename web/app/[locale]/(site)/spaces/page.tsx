import type { Metadata } from "next";
import { Container, PageHeader } from "@/components/ui";
import { SpacesApp, SpacesSignedOutNote } from "@/components/site/spaces";
import { makeT } from "@/lib/i18n";

export async function generateMetadata({ params }: PageProps<"/[locale]/spaces">): Promise<Metadata> {
  const { locale } = await params;
  const t = makeT(locale);
  return { title: t("spaces.title"), description: t("spaces.lead") };
}

export default async function SpacesPage({ params }: PageProps<"/[locale]/spaces">) {
  const { locale } = await params;
  const t = makeT(locale);
  return (
    <>
      <PageHeader eyebrow={t("spaces.eyebrow")} title={t("spaces.title")} lead={t("spaces.lead")} />
      <Container className="py-8">
        <SpacesSignedOutNote />
        <SpacesApp />
      </Container>
    </>
  );
}
