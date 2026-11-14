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

/* ---------------------------------------------------------------- Ethiopian calendar
   Same fixed-day-number algorithm as backend/app/core/calendar.py (Reingold & Dershowitz):
   Ethiopic epoch is R.D. 2796; R.D. of 1970-01-01 is 719163. */

const ETHIOPIC_EPOCH = 2796;
const RD_UNIX_EPOCH = 719163;
const ETH_MONTHS: Record<string, string[]> = {
  en: ["Meskerem", "Tikimt", "Hidar", "Tahsas", "Tir", "Yekatit", "Megabit", "Miazia", "Ginbot", "Sene", "Hamle", "Nehase", "Pagume"],
  ti: ["መስከረም", "ጥቅምቲ", "ሕዳር", "ታሕሳስ", "ጥሪ", "ለካቲት", "መጋቢት", "ሚያዝያ", "ግንቦት", "ሰነ", "ሓምለ", "ነሓሰ", "ጳጉሜን"],
  am: ["መስከረም", "ጥቅምት", "ኅዳር", "ታኅሣሥ", "ጥር", "የካቲት", "መጋቢት", "ሚያዝያ", "ግንቦት", "ሰኔ", "ሐምሌ", "ነሐሴ", "ጳጉሜን"],
};

function ethFixed(year: number, month: number, day: number): number {
  return ETHIOPIC_EPOCH - 1 + 365 * (year - 1) + Math.floor(year / 4) + 30 * (month - 1) + day;
}

/** Convert a Gregorian calendar date (UTC) to the Ethiopian calendar. */
export function toEthiopian(date: Date): { year: number; month: number; day: number } {
  const fixed = Math.floor(date.getTime() / 86_400_000) + RD_UNIX_EPOCH;
  const year = Math.floor((4 * (fixed - ETHIOPIC_EPOCH) + 1463) / 1461);
  const month = Math.floor((fixed - ethFixed(year, 1, 1)) / 30) + 1;
  const day = fixed + 1 - ethFixed(year, month, 1);
  return { year, month, day };
}

export function formatEthiopian(iso: string, locale = "en"): string {
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso);
  if (Number.isNaN(d.getTime())) return "";
  const e = toEthiopian(d);
  const names = ETH_MONTHS[locale] ?? ETH_MONTHS.en;
  return `${names[e.month - 1]} ${e.day}, ${e.year} ${locale === "en" ? "E.C." : "ዓ.ም."}`;
}

export function formatTime(iso: string, locale = "en"): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  try {
    return new Intl.DateTimeFormat(INTL_LOCALE[locale] ?? "en-GB", { hour: "2-digit", minute: "2-digit" }).format(d);
  } catch {
    return d.toISOString().slice(11, 16);
  }
}

export function daysSince(iso: string | null | undefined, now = new Date()): number | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return Math.floor((now.getTime() - d.getTime()) / 86_400_000);
}
