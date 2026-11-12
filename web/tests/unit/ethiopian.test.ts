import { describe, expect, it } from "vitest";
import { formatEthiopian, toEthiopian } from "@/lib/format";

// Same known dates as backend/tests/test_core_units.py
const CASES: [string, [number, number, number]][] = [
  ["2024-09-11", [2017, 1, 1]], // Enkutatash 2017 E.C.
  ["2023-09-12", [2016, 1, 1]], // after leap year 2015 E.C.
  ["2024-01-20", [2016, 5, 11]], // Timket in a Gregorian leap year
  ["2025-01-19", [2017, 5, 11]],
  ["2024-09-27", [2017, 1, 17]], // Meskel
  ["2023-09-11", [2015, 13, 6]], // Pagume 6 in leap year 2015
  ["1896-03-01", [1888, 6, 23]], // Battle of Adwa, Yekatit 23
];

describe("toEthiopian", () => {
  it.each(CASES)("%s", (iso, [y, m, d]) => {
    expect(toEthiopian(new Date(`${iso}T12:00:00Z`))).toEqual({ year: y, month: m, day: d });
  });
});

describe("formatEthiopian", () => {
  it("formats per locale", () => {
    expect(formatEthiopian("2024-09-27", "en")).toBe("Meskerem 17, 2017 E.C.");
    expect(formatEthiopian("2024-09-27", "ti")).toBe("መስከረም 17, 2017 ዓ.ም.");
    expect(formatEthiopian("bad")).toBe("");
  });
});
