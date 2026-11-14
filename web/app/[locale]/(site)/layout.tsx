import { Footer } from "@/components/site/footer";
import { Header, TranslationNotice } from "@/components/site/header";
import { OfflineBanner } from "@/components/site/pwa";
import { makeT } from "@/lib/i18n";

export default async function SiteLayout({ children, params }: LayoutProps<"/[locale]">) {
  const { locale } = await params;
  const t = makeT(locale);
  return (
    <>
      <a href="#main" className="skip-link">
        {t("common.skip")}
      </a>
      <OfflineBanner />
      <TranslationNotice />
      <Header />
      <main id="main" tabIndex={-1} className="outline-none">
        {children}
      </main>
      <Footer locale={locale} />
    </>
  );
}
