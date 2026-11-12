import { Container } from "@/components/ui";
import { ProviderDetail } from "@/components/site/directory";

export default async function ProviderPage({ params }: PageProps<"/[locale]/providers/[slug]">) {
  const { slug } = await params;
  return (
    <Container className="py-14">
      <ProviderDetail slug={slug} />
    </Container>
  );
}
