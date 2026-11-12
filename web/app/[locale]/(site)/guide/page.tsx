import type { Metadata } from "next";
import { Container, PageHeader } from "@/components/ui";
import { GuideChat } from "@/components/site/guide-chat";
import { makeT } from "@/lib/i18n";

export async function generateMetadata({ params }: PageProps<"/[locale]/guide">): Promise<Metadata> {
  const { locale } = await params;
  return { title: makeT(locale)("guide.title") };
}

export default async function GuidePage({ params, searchParams }: PageProps<"/[locale]/guide">) {
  const { locale } = await params;
  const sp = await searchParams;
  const t = makeT(locale);
  const destination = typeof sp.destination === "string" ? sp.destination : undefined;
  return (
    <>
      <PageHeader eyebrow="TIE — Tigray Intelligence Engine" title={t("guide.title")} lead={t("guide.lead")} />
      <Container className="py-10">
        <GuideChat destinationSlug={destination} />
      </Container>
    </>
  );
}
