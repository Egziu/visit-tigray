import { Container } from "@/components/ui";
import { MemoryDetail } from "@/components/site/memories";

export default async function MemoryPage({ params }: PageProps<"/[locale]/memories/[id]">) {
  const { id } = await params;
  return (
    <Container className="max-w-4xl py-14">
      <MemoryDetail id={id} />
    </Container>
  );
}
