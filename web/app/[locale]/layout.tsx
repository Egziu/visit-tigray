import type { Metadata, Viewport } from "next";
import { notFound } from "next/navigation";
import "@fontsource-variable/inter";
import "@fontsource/cormorant-garamond/500.css";
import "@fontsource/cormorant-garamond/600.css";
import "@fontsource/cormorant-garamond/500-italic.css";
import "@fontsource/noto-sans-ethiopic/ethiopic-400.css";
import "@fontsource/noto-sans-ethiopic/ethiopic-600.css";
import "@fontsource/noto-serif-ethiopic/ethiopic-600.css";
import "../globals.css";
import { Providers } from "@/components/site/providers";
import { ServiceWorkerRegistration } from "@/components/site/pwa";
import { isLocale, LOCALES, makeT } from "@/lib/i18n";

export const dynamicParams = false;

export function generateStaticParams() {
  return LOCALES.map((locale) => ({ locale }));
}

export async function generateMetadata({ params }: LayoutProps<"/[locale]">): Promise<Metadata> {
  const { locale } = await params;
  const t = makeT(locale);
  return {
    title: { default: `${t("brand.name")} — ${t("brand.tagline")}`, template: `%s · ${t("brand.name")}` },
    description: t("home.lead"),
    manifest: "/manifest.webmanifest",
    icons: { icon: "/icons/icon.svg", apple: "/icons/icon-192.png" },
    alternates: { languages: Object.fromEntries(LOCALES.map((l) => [l, `/${l}`])) },
  };
}

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#102d27" },
    { media: "(prefers-color-scheme: dark)", color: "#0c1512" },
  ],
  width: "device-width",
  initialScale: 1,
};

// Applies the saved theme / data-saver preference before first paint (no flash).
const PREFS_SCRIPT = `try{var t=localStorage.getItem('vt_theme');if(t==='light'||t==='dark')document.documentElement.dataset.theme=t;if(localStorage.getItem('vt_saver')==='on')document.documentElement.dataset.saver='on'}catch(e){}`;

export default async function RootLayout({ children, params }: LayoutProps<"/[locale]">) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  return (
    <html lang={locale} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: PREFS_SCRIPT }} />
      </head>
      <body className="min-h-screen antialiased">
        <Providers locale={locale}>
          {children}
          <ServiceWorkerRegistration />
        </Providers>
      </body>
    </html>
  );
}
