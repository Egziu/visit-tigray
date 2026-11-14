import en from "@/messages/en.json";
import ti from "@/messages/ti.json";
import am from "@/messages/am.json";

export const LOCALES = ["en", "ti", "am"] as const;
export type AppLocale = (typeof LOCALES)[number];
export const LOCALE_NAMES: Record<AppLocale, string> = { en: "English", ti: "ትግርኛ", am: "አማርኛ" };

export type Dict = typeof en;

const DICTS: Record<AppLocale, unknown> = { en, ti, am };

export function isLocale(v: string): v is AppLocale {
  return (LOCALES as readonly string[]).includes(v);
}

export function getDict(locale: string): Dict {
  return (DICTS[isLocale(locale) ? locale : "en"] ?? en) as Dict;
}

type Leaves<T, P extends string = ""> = {
  [K in keyof T & string]: T[K] extends string ? `${P}${K}` : T[K] extends object ? Leaves<T[K], `${P}${K}.`> : never;
}[keyof T & string];
export type MsgKey = Exclude<Leaves<Dict>, `_meta.${string}`>;

function lookup(dict: unknown, key: string): string | undefined {
  let cur: unknown = dict;
  for (const part of key.split(".")) {
    if (cur && typeof cur === "object" && part in (cur as Record<string, unknown>)) {
      cur = (cur as Record<string, unknown>)[part];
    } else return undefined;
  }
  return typeof cur === "string" ? cur : undefined;
}

/** Translate with {var} interpolation; falls back to English, then to the key itself. */
export function translate(dict: unknown, key: MsgKey | string, vars?: Record<string, string | number>): string {
  const raw = lookup(dict, key) ?? lookup(en, key) ?? key;
  if (!vars) return raw;
  return raw.replace(/\{(\w+)\}/g, (_, k: string) => (k in vars ? String(vars[k]) : `{${k}}`));
}

export function makeT(locale: string) {
  const dict = getDict(locale);
  return (key: MsgKey, vars?: Record<string, string | number>) => translate(dict, key, vars);
}

/** Flatten nested message keys — used by the i18n completeness test. */
export function flatKeys(obj: unknown, prefix = ""): string[] {
  if (!obj || typeof obj !== "object") return [];
  return Object.entries(obj as Record<string, unknown>).flatMap(([k, v]) =>
    typeof v === "string" ? [`${prefix}${k}`] : flatKeys(v, `${prefix}${k}.`),
  );
}
