import type { Metadata } from "next";
import { Container } from "@/components/ui";
import { PublicationView } from "@/components/site/journal";
import { makeT } from "@/lib/i18n";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps<"/[locale]/journal/p/[handle]">): Promise<Metadata> {
  const { locale, handle } = await params;
  return { title: `${handle} · ${makeT(locale)("journal.title")}` };
}

export default async function PublicationPage({ params }: PageProps<"/[locale]/journal/p/[handle]">) {
  const { handle } = await params;
  return (
    <Container className="py-10">
      <PublicationView handle={decodeURIComponent(handle)} />
    </Container>
  );
}
