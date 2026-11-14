import type { Metadata } from "next";
import { Container, PageHeader } from "@/components/ui";
import { ProviderList } from "@/components/site/directory";
import { makeT } from "@/lib/i18n";

export async function generateMetadata({ params }: PageProps<"/[locale]/providers">): Promise<Metadata> {
  const { locale } = await params;
  return { title: makeT(locale)("providers.title") };
}

export default async function ProvidersPage({ params }: PageProps<"/[locale]/providers">) {
  const { locale } = await params;
  const t = makeT(locale);
  return (
    <>
      <PageHeader title={t("providers.title")} lead={t("providers.lead")} />
      <Container className="py-10">
        <ProviderList />
      </Container>
    </>
  );
}
