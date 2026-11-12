import Link from "next/link";
import { Alert, Badge, cn } from "@/components/ui";
import { formatDate } from "@/lib/format";
import { makeT } from "@/lib/i18n";
import type { Advisory, AdvisoryLevel, Destination, MediaItem } from "@/lib/types";
import { CardArt } from "./illustrations";

const LEVEL_TONE: Record<AdvisoryLevel, "info" | "caution" | "danger"> = {
  info: "info",
  caution: "caution",
  avoid_nonessential: "danger",
  travel_not_advised: "danger",
};

export function ServiceDown({ locale, message }: { locale: string; message?: string }) {
  const t = makeT(locale);
  return (
    <Alert tone="caution" title={t("common.serviceDown")}>
      {message && <span className="text-xs">{message}</span>}
    </Alert>
  );
}

export function TrustBadges({ d, locale }: { d: Pick<Destination, "verified_at" | "is_stale" | "is_synthetic" | "translation_status" | "locale" | "requested_locale">; locale: string }) {
  const t = makeT(locale);
  return (
    <div className="flex flex-wrap gap-2">
      {d.is_synthetic && <Badge tone="caution">{t("common.synthetic")}</Badge>}
      {d.verified_at ? (
        <Badge tone={d.is_stale ? "caution" : "success"}>
          {d.is_stale ? t("common.stale") : t("common.lastVerified", { date: formatDate(d.verified_at, locale) })}
        </Badge>
      ) : (
        <Badge tone="neutral">{t("common.neverVerified")}</Badge>
      )}
      {d.translation_status === "machine" && <Badge tone="earth">{t("common.machineTranslation")}</Badge>}
      {d.locale && d.requested_locale && d.locale !== d.requested_locale && <Badge tone="neutral">{t("common.shownInEnglish")}</Badge>}
    </div>
  );
}

export function DestinationCard({ d, locale }: { d: Destination; locale: string }) {
  const t = makeT(locale);
  const hero = d.media?.find((m) => m.is_hero) ?? d.media?.[0];
  return (
    <article className="lift group relative flex flex-col overflow-hidden rounded-[var(--radius)] border border-line bg-surface">
      <div className="relative aspect-[16/10] overflow-hidden bg-surface-2">
        {hero ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={hero.urls.md ?? hero.urls.sm} alt={hero.alt_text_i18n?.[locale] ?? hero.alt_text_i18n?.en ?? ""} loading="lazy" className="saver-hide h-full w-full object-cover" />
        ) : (
          <CardArt seed={d.slug} className="h-full w-full" />
        )}
        {!hero && (
          <span className="absolute bottom-2 right-2 rounded bg-black/45 px-1.5 py-0.5 text-[0.65rem] uppercase tracking-wider text-white">
            {t("common.illustration")}
          </span>
        )}
        {d.advisory_level && (
          <span className="absolute left-3 top-3">
            <Badge tone={LEVEL_TONE[d.advisory_level]} className="bg-surface/95">
              {t(`advisory.level.${d.advisory_level}`)}
            </Badge>
          </span>
        )}
      </div>
      <div className="flex flex-1 flex-col p-6">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-earth">
          {[d.eyebrow || d.category?.name, d.area].filter(Boolean).join(" · ")}
        </p>
        <h3 className="mt-2 text-3xl">
          <Link href={`/${locale}/destinations/${d.slug}`} className="after:absolute after:inset-0 hover:underline">
            {d.name}
          </Link>
        </h3>
        <p className="mt-3 line-clamp-3 text-muted">{d.summary}</p>
        <div className="mt-auto pt-5">
          <TrustBadges d={d} locale={locale} />
        </div>
      </div>
    </article>
  );
}

export function AdvisoryCard({ a, locale }: { a: Advisory; locale: string }) {
  const t = makeT(locale);
  return (
    <Alert tone={LEVEL_TONE[a.level] === "danger" ? "danger" : LEVEL_TONE[a.level]} title={`${t(`advisory.level.${a.level}`)} — ${a.title}`}>
      <p className="text-ink">{a.body}</p>
      <p className="mt-2 text-sm">
        {t("advisory.issuedBy", { authority: a.issuing_authority })} · {t("advisory.effective", { date: formatDate(a.effective_from, locale) })}
        {a.effective_until ? ` ${t("advisory.until", { date: formatDate(a.effective_until, locale) })}` : ""}
        {a.source_url && (
          <>
            {" · "}
            <a href={a.source_url} rel="noopener noreferrer" target="_blank" className="underline">
              {t("advisory.source")}
            </a>
          </>
        )}
        {a.is_synthetic && <> · {t("common.synthetic")}</>}
      </p>
    </Alert>
  );
}

export function MediaFigure({ m, locale, className, size = "md" }: { m: MediaItem; locale: string; className?: string; size?: "sm" | "md" | "lg" }) {
  const t = makeT(locale);
  const alt = m.alt_text_i18n?.[locale] ?? m.alt_text_i18n?.en ?? "";
  const caption = m.caption_i18n?.[locale] ?? m.caption_i18n?.en;
  return (
    <figure className={cn("overflow-hidden rounded-[var(--radius)] border border-line bg-surface", className)}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={m.urls[size] ?? m.urls.md} alt={alt} width={m.width} height={m.height} loading="lazy" className="saver-hide h-auto w-full" />
      <figcaption className="space-y-1 px-4 py-3 text-xs text-muted">
        {caption && <p className="text-sm text-ink">{caption}</p>}
        <div className="flex flex-wrap gap-2">
          {m.is_illustrative && <Badge tone="earth">{t("common.illustration")}</Badge>}
          {m.is_reconstruction && <Badge tone="earth">{t("common.reconstruction")}</Badge>}
          {m.is_ai_generated && <Badge tone="caution">{t("common.aiGenerated")}</Badge>}
        </div>
        {m.credit && <p>{t("common.credit", { credit: m.credit })}</p>}
        {m.license && <p>{t("common.licence", { licence: m.license })}</p>}
      </figcaption>
    </figure>
  );
}
