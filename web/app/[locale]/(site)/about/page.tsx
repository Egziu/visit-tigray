import type { Metadata } from "next";
import { Container, PageHeader } from "@/components/ui";
import { makeT } from "@/lib/i18n";

export async function generateMetadata({ params }: PageProps<"/[locale]/about">): Promise<Metadata> {
  const { locale } = await params;
  return { title: makeT(locale)("about.title") };
}

export default async function AboutPage({ params }: PageProps<"/[locale]/about">) {
  const { locale } = await params;
  const t = makeT(locale);
  const sections = [
    ["about.statusTitle", "about.statusBody"],
    ["about.dataTitle", "about.dataBody"],
    ["about.aiTitle", "about.aiBody"],
    ["about.privacyTitle", "about.privacyBody"],
  ] as const;
  return (
    <>
      <PageHeader title={t("about.title")} lead={t("brand.tagline")} />
      <Container className="max-w-3xl space-y-10 py-14">
        {sections.map(([h, b]) => (
          <section key={h}>
            <h2 className="text-3xl">{t(h)}</h2>
            <p className="mt-3 text-lg text-muted">{t(b)}</p>
          </section>
        ))}
        <p className="text-sm text-muted">{t("footer.partner")}</p>
      </Container>
    </>
  );
}
