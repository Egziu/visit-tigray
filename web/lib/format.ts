// Date/number formatting. Ethiopian-calendar strings come from the API (tested conversion);
// here we only format Gregorian values per locale.

const INTL_LOCALE: Record<string, string> = { en: "en-GB", ti: "ti-ET", am: "am-ET" };

export function formatDate(iso: string | null | undefined, locale = "en"): string {
  if (!iso) return "";
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso);
  if (Number.isNaN(d.getTime())) return "";
  try {
    return new Intl.DateTimeFormat(INTL_LOCALE[locale] ?? "en-GB", {
      year: "numeric",
      month: "long",
      day: "numeric",
      timeZone: "UTC",
    }).format(d);
  } catch {
    return d.toISOString().slice(0, 10);
  }
}

export function formatDateTime(iso: string | null | undefined, locale = "en"): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  try {
    return new Intl.DateTimeFormat(INTL_LOCALE[locale] ?? "en-GB", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "UTC",
    }).format(d) + " UTC";
  } catch {
    return d.toISOString();
  }
}

export function formatDuration(minutes: number | null | undefined, unknownLabel: string): string {
  if (minutes === null || minutes === undefined) return unknownLabel;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h && m) return `${h} h ${m} min`;
  if (h) return `${h} h`;
  return `${m} min`;
}

export function daysSince(iso: string | null | undefined, now = new Date()): number | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return Math.floor((now.getTime() - d.getTime()) / 86_400_000);
}
