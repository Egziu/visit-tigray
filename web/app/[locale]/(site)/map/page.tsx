import type { Metadata } from "next";
import { Container, PageHeader } from "@/components/ui";
import { ServiceDown } from "@/components/site/content";
import { MapView } from "@/components/site/map-view";
import { makeT } from "@/lib/i18n";
import { serverGet } from "@/lib/server-api";
import type { Destination } from "@/lib/types";

export const revalidate = 60;

export async function generateMetadata({ params }: PageProps<"/[locale]/map">): Promise<Metadata> {
  const { locale } = await params;
  return { title: makeT(locale)("map.title") };
}

export default async function MapPage({ params }: PageProps<"/[locale]/map">) {
  const { locale } = await params;
  const t = makeT(locale);
  const r = await serverGet<{ items: Destination[] }>(`/api/destinations?locale=${locale}&limit=100`);
  return (
    <>
      <PageHeader title={t("map.title")} lead={t("map.lead")} />
      <Container className="py-10">
        {r.ok ? (
          <MapView pins={r.data.items.map(({ slug, name, area, coordinates }) => ({ slug, name, area, coordinates }))} />
        ) : (
          <ServiceDown locale={locale} message={r.message} />
        )}
      </Container>
    </>
  );
}
