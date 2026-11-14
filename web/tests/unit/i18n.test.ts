import { describe, expect, it } from "vitest";
import am from "@/messages/am.json";
import en from "@/messages/en.json";
import ti from "@/messages/ti.json";
import { flatKeys, makeT, translate } from "@/lib/i18n";

const enKeys = flatKeys(en).filter((k) => !k.startsWith("_meta."));

function lookup(obj: unknown, key: string): string | undefined {
  return key.split(".").reduce<unknown>((o, k) => (o && typeof o === "object" ? (o as Record<string, unknown>)[k] : undefined), obj) as string | undefined;
}

describe.each([
  ["ti", ti],
  ["am", am],
])("%s messages", (code, dict) => {
  it("define every English key", () => {
    const missing = enKeys.filter((k) => typeof lookup(dict, k) !== "string");
    expect(missing, `missing in ${code}`).toEqual([]);
  });

  it("have no keys that English lacks", () => {
    const extra = flatKeys(dict).filter((k) => !k.startsWith("_meta.") && !enKeys.includes(k));
    expect(extra).toEqual([]);
  });

  it("keep the same {placeholders} as English", () => {
    const mismatched = enKeys.filter((k) => {
      const ph = (s?: string) => [...(s ?? "").matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join(",");
      return ph(lookup(en, k)) !== ph(lookup(dict, k));
    });
    expect(mismatched).toEqual([]);
  });

  it("are flagged as machine drafts needing review", () => {
    expect((dict as { _meta: { status: string } })._meta.status).toMatch(/requires native-speaker review/);
  });

  it("are written in Ge'ez script (not copied English)", () => {
    expect(lookup(dict, "nav.destinations")).toMatch(/[ሀ-፿]/);
  });
});

describe("translate", () => {
  it("interpolates variables and falls back to English, then to the key", () => {
    expect(translate(en, "common.lastVerified", { date: "1 May 2026" })).toBe("Last verified 1 May 2026");
    expect(translate({}, "nav.map")).toBe("Map");
    expect(translate(en, "no.such.key")).toBe("no.such.key");
    expect(makeT("xx")("nav.map")).toBe("Map");
  });
});
