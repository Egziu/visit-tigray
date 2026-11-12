import type { Metadata } from "next";
import { Container } from "@/components/ui";
import { SpacesApp, SpacesSignedOutNote } from "@/components/site/spaces";
import { makeT } from "@/lib/i18n";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps<"/[locale]/spaces/[space]">): Promise<Metadata> {
  const { locale } = await params;
  return { title: makeT(locale)("spaces.title") };
}

export default async function SpacePage({ params }: PageProps<"/[locale]/spaces/[space]">) {
  const { space } = await params;
  return (
    <Container className="py-8">
      <SpacesSignedOutNote />
      <SpacesApp spaceSlug={decodeURIComponent(space)} />
    </Container>
  );
}
