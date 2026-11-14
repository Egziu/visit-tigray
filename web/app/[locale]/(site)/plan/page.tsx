import type { Metadata } from "next";
import { Container, PageHeader } from "@/components/ui";
import { Planner } from "@/components/site/planner";
import { makeT } from "@/lib/i18n";

const str = (v: string | string[] | undefined) => (typeof v === "string" && v ? v : undefined);

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
        <Planner
          include={str(sp.include)}
          itineraryId={str(sp.itinerary)}
          initialDays={str(sp.days) ? Number(str(sp.days)) || undefined : undefined}
          initialInterests={str(sp.interests)?.split(",").filter(Boolean)}
          initialStart={str(sp.start)}
        />
      </Container>
    </>
  );
}
