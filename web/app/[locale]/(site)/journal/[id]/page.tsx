import type { Metadata } from "next";
import { Container } from "@/components/ui";
import { JournalReader } from "@/components/site/journal";
import { makeT } from "@/lib/i18n";
import { serverGet } from "@/lib/server-api";
import type { JournalPost } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps<"/[locale]/journal/[id]">): Promise<Metadata> {
  const { locale, id } = await params;
  const r = await serverGet<JournalPost>(`/api/journal/${encodeURIComponent(id)}?locale=${locale}`);
  if (!r.ok) return { title: makeT(locale)("journal.title") };
  const image = r.data.cover?.urls.lg ?? "/brand/og-image.png";
  return {
    title: r.data.title,
    description: r.data.subtitle || r.data.excerpt,
    openGraph: { title: r.data.title, description: r.data.subtitle || r.data.excerpt, type: "article", images: [{ url: image }] },
  };
}

export default async function JournalPostPage({ params }: PageProps<"/[locale]/journal/[id]">) {
  const { id } = await params;
  return (
    <Container>
      <JournalReader id={id} />
    </Container>
  );
}
