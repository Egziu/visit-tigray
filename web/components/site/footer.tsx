import Link from "next/link";
import { makeT } from "@/lib/i18n";
import Image from "next/image";
import { PatternBand } from "./illustrations";

export function Footer({ locale }: { locale: string }) {
  const t = makeT(locale);
  const l = (p: string) => `/${locale}${p}`;
  return (
    <footer className="mt-24 bg-[#0a4424] text-[#efe9dc]">
      <PatternBand className="h-3 w-full text-[#c9a160]" />
      <div className="mx-auto grid max-w-7xl gap-12 px-5 py-16 sm:px-8 md:grid-cols-[2fr_1fr_1fr_1fr]">
        <div>
          <span className="inline-flex rounded-2xl bg-[#f8f2e9] p-3">
            <Image src="/brand/visit-tigray-logo-520.webp" alt="Visit Tigray" width={180} height={120} unoptimized className="h-[120px] w-auto" />
          </span>
          <p className="mt-4 font-display text-xl text-[#efe9dc]">{t("brand.tagline")}</p>
          <p className="mt-4 max-w-sm text-sm text-[#c9c1af]">{t("footer.status")}</p>
          <p className="mt-3 max-w-sm text-sm text-[#c9c1af]">{t("footer.partner")}</p>
        </div>
        <FooterCol title={t("footer.explore")}>
          <Link href={l("/destinations")}>{t("nav.destinations")}</Link>
          <Link href={l("/map")}>{t("nav.map")}</Link>
          <Link href={l("/events")}>{t("nav.events")}</Link>
          <Link href={l("/guide")}>{t("nav.guide")}</Link>
          <Link href={l("/plan")}>{t("nav.plan")}</Link>
        </FooterCol>
        <FooterCol title={t("footer.community")}>
          <Link href={l("/journal")}>{t("nav.journal")}</Link>
          <Link href={l("/spaces")}>{t("nav.spaces")}</Link>
          <Link href={l("/memories")}>{t("nav.memories")}</Link>
          <Link href={l("/awards")}>{t("nav.awards")}</Link>
          <Link href={l("/providers")}>{t("nav.providers")}</Link>
        </FooterCol>
        <FooterCol title={t("footer.practical")}>
          <Link href={l("/travel")}>{t("nav.travel")}</Link>
          <Link href={l("/advisories")}>{t("advisory.title")}</Link>
          <Link href={l("/offline")}>{t("nav.offline")}</Link>
          <Link href={l("/about")}>{t("nav.about")}</Link>
        </FooterCol>
      </div>
      <div className="border-t border-white/10">
        <p className="mx-auto max-w-7xl px-5 py-6 text-xs text-[#b5ad9b] sm:px-8">
          © 2026 SERK Technologies Group · {t("footer.rights")}
        </p>
      </div>
    </footer>
  );
}

function FooterCol({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="mb-4 text-xs font-semibold uppercase tracking-[0.2em] text-[#d9b37a]">{title}</p>
      <div className="flex flex-col gap-2.5 text-sm text-[#e4dccd] [&_a:hover]:underline">{children}</div>
    </div>
  );
}
