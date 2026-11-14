import type { Metadata } from "next";
import { Container, PageHeader } from "@/components/ui";
import { AccountPanel } from "@/components/site/account";
import { PublicationSettings } from "@/components/site/journal";
import { makeT } from "@/lib/i18n";

export async function generateMetadata({ params }: PageProps<"/[locale]/account">): Promise<Metadata> {
  const { locale } = await params;
  return { title: makeT(locale)("account.title"), robots: { index: false } };
}

export default async function AccountPage({ params }: PageProps<"/[locale]/account">) {
  const { locale } = await params;
  const t = makeT(locale);
  return (
    <>
      <PageHeader title={t("account.title")} />
      <Container className="py-10">
        <AccountPanel />
        <div className="mt-8">
          <PublicationSettings />
        </div>
      </Container>
    </>
  );
}
