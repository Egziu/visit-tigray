import { Container, PageHeader } from "@/components/ui";
import { VerifyEmail } from "@/components/site/account";
import { makeT } from "@/lib/i18n";

export const metadata = { robots: { index: false } };

export default async function VerifyPage({ params, searchParams }: PageProps<"/[locale]/account/verify">) {
  const { locale } = await params;
  const sp = await searchParams;
  const t = makeT(locale);
  const token = typeof sp.token === "string" ? sp.token : "";
  return (
    <>
      <PageHeader title={t("account.verifying")} />
      <Container className="py-10">{token ? <VerifyEmail token={token} /> : <p>{t("common.error")}</p>}</Container>
    </>
  );
}
