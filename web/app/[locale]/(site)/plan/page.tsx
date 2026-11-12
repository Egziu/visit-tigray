import type { Metadata } from "next";
import { Container, PageHeader } from "@/components/ui";
import { Planner } from "@/components/site/planner";
import { makeT } from "@/lib/i18n";

export async function generateMetadata({ params }: PageProps<"/[locale]/plan">): Promise<Metadata> {
  const { locale } = await params;
  return { title: makeT(locale)("plan.title") };
}

export default async function PlanPage({ params, searchParams }: PageProps<"/[locale]/plan">) {
  const { locale } = await params;
  const sp = await searchParams;
  const t = makeT(locale);
  return (
    <>
      <PageHeader title={t("plan.title")} lead={t("plan.lead")} />
      <Container className="py-10">
        <Planner include={typeof sp.include === "string" ? sp.include : undefined} itineraryId={typeof sp.itinerary === "string" ? sp.itinerary : undefined} />
      </Container>
    </>
  );
}
