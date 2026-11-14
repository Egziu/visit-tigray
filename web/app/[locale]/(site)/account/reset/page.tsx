import { Container, PageHeader } from "@/components/ui";
import { ResetPassword } from "@/components/site/account";
import { makeT } from "@/lib/i18n";

export const metadata = { robots: { index: false } };

export default async function ResetPage({ params, searchParams }: PageProps<"/[locale]/account/reset">) {
  const { locale } = await params;
  const sp = await searchParams;
  const t = makeT(locale);
  const token = typeof sp.token === "string" ? sp.token : "";
  return (
    <>
      <PageHeader title={t("account.forgotTitle")} />
      <Container className="py-10">{token ? <ResetPassword token={token} /> : <p>{t("common.error")}</p>}</Container>
    </>
  );
}
