import type { Metadata } from "next";
import { Container } from "@/components/ui";
import { SpacesApp, SpacesSignedOutNote } from "@/components/site/spaces";
import { makeT } from "@/lib/i18n";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps<"/[locale]/spaces/[space]/[channel]">): Promise<Metadata> {
  const { locale, channel } = await params;
  return { title: `#${decodeURIComponent(channel)} · ${makeT(locale)("spaces.title")}` };
}

export default async function ChannelPage({ params }: PageProps<"/[locale]/spaces/[space]/[channel]">) {
  const { space, channel } = await params;
  return (
    <Container className="py-8">
      <SpacesSignedOutNote />
      <SpacesApp spaceSlug={decodeURIComponent(space)} channelSlug={decodeURIComponent(channel)} />
    </Container>
  );
}
