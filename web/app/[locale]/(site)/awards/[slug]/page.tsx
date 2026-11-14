import { Container } from "@/components/ui";
import { CompetitionDetail } from "@/components/site/directory";

export default async function CompetitionPage({ params }: PageProps<"/[locale]/awards/[slug]">) {
  const { slug } = await params;
  return (
    <Container className="py-14">
      <CompetitionDetail slug={slug} />
    </Container>
  );
}
