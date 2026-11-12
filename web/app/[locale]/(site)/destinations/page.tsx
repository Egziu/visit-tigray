import type { Metadata } from "next";
import { Container, EmptyState, PageHeader } from "@/components/ui";
import { DestinationCard, ServiceDown } from "@/components/site/content";
import { makeT } from "@/lib/i18n";
import { serverGet } from "@/lib/server-api";
import type { Category, Destination } from "@/lib/types";

export const dynamic = "force-dynamic"; // depends on search params

export async function generateMetadata({ params }: PageProps<"/[locale]/destinations">): Promise<Metadata> {
  const { locale } = await params;
  return { title: makeT(locale)("destinations.title") };
}

const INTERESTS = ["history", "heritage", "culture", "adventure", "nature", "food", "faith", "crafts"];

export default async function DestinationsPage({ params, searchParams }: PageProps<"/[locale]/destinations">) {
  const { locale } = await params;
  const sp = await searchParams;
  const t = makeT(locale);
  const q = typeof sp.q === "string" ? sp.q.slice(0, 120) : "";
  const category = typeof sp.category === "string" ? sp.category : "";
  const interest = typeof sp.interest === "string" ? sp.interest : "";
  const qs = new URLSearchParams({ locale, limit: "60" });
  if (q) qs.set("q", q);
  if (category) qs.set("category", category);
  if (interest) qs.set("interest", interest);
  const [dest, cats] = await Promise.all([
    serverGet<{ items: Destination[] }>(`/api/destinations?${qs}`, 30),
    serverGet<Category[]>(`/api/categories?locale=${locale}`),
  ]);

  return (
    <>
      <PageHeader eyebrow={t("brand.name")} title={t("destinations.title")} lead={t("destinations.lead")} />
      <Container className="py-10">
        <form role="search" className="grid gap-4 rounded-[var(--radius)] border border-line bg-surface p-5 md:grid-cols-[2fr_1fr_1fr_auto] md:items-end" action="">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="q" className="text-sm font-medium">
              {t("destinations.searchLabel")}
            </label>
            <input id="q" name="q" type="search" defaultValue={q} placeholder={t("destinations.searchPlaceholder")} className="min-h-[44px] rounded-lg border border-line bg-bg px-3.5 py-2.5" />
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="category" className="text-sm font-medium">
              {t("destinations.category")}
            </label>
            <select id="category" name="category" defaultValue={category} className="min-h-[44px] rounded-lg border border-line bg-bg px-3">
              <option value="">{t("destinations.allCategories")}</option>
              {cats.ok &&
                cats.data.map((c) => (
                  <option key={c.slug} value={c.slug}>
                    {c.name}
                  </option>
                ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="interest" className="text-sm font-medium">
              {t("destinations.interest")}
            </label>
            <select id="interest" name="interest" defaultValue={interest} className="min-h-[44px] rounded-lg border border-line bg-bg px-3">
              <option value="">{t("destinations.anyInterest")}</option>
              {INTERESTS.map((i) => (
                <option key={i} value={i}>
                  {i}
                </option>
              ))}
            </select>
          </div>
          <button type="submit" className="min-h-[44px] rounded-full bg-forest px-6 text-on-forest">
            {t("common.search")}
          </button>
        </form>

        <div className="mt-10" aria-live="polite">
          {!dest.ok ? (
            <ServiceDown locale={locale} message={dest.message} />
          ) : dest.data.items.length === 0 ? (
            <EmptyState title={t("destinations.none")} />
          ) : (
            <>
              <p className="mb-6 text-sm text-muted">{t("destinations.results", { count: dest.data.items.length })}</p>
              <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                {dest.data.items.map((d) => (
                  <DestinationCard key={d.slug} d={d} locale={locale} />
                ))}
              </div>
            </>
          )}
        </div>
      </Container>
    </>
  );
}
