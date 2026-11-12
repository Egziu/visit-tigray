import { Container } from "@/components/ui";
import { CreatorProfile } from "@/components/site/memories";

export default async function CreatorPage({ params }: PageProps<"/[locale]/creators/[handle]">) {
  const { handle } = await params;
  return (
    <Container className="py-14">
      <CreatorProfile handle={decodeURIComponent(handle)} />
    </Container>
  );
}
