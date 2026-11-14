import { describe, expect, it } from "vitest";
import { daysSince, formatDate, formatDuration } from "@/lib/format";
import { formatBytes } from "@/lib/offline";

describe("formatDate", () => {
  it("formats ISO dates without timezone drift", () => {
    expect(formatDate("2024-09-11", "en")).toBe("11 September 2024");
    expect(formatDate("2024-09-11T23:30:00Z", "en")).toBe("11 September 2024");
  });
  it("returns empty string for missing or invalid input", () => {
    expect(formatDate(null)).toBe("");
    expect(formatDate("not-a-date")).toBe("");
  });
  it("does not throw for Ethiopian locales", () => {
    expect(formatDate("2024-09-11", "ti")).not.toBe("");
    expect(formatDate("2024-09-11", "am")).not.toBe("");
  });
});

describe("formatDuration", () => {
  it("keeps unknown durations explicit", () => {
    expect(formatDuration(null, "Unknown")).toBe("Unknown");
    expect(formatDuration(undefined, "Unknown")).toBe("Unknown");
  });
  it("formats minutes", () => {
    expect(formatDuration(45, "?")).toBe("45 min");
    expect(formatDuration(120, "?")).toBe("2 h");
    expect(formatDuration(150, "?")).toBe("2 h 30 min");
  });
});

describe("daysSince / formatBytes", () => {
  it("computes whole days", () => {
    expect(daysSince("2026-01-01T00:00:00Z", new Date("2026-01-11T12:00:00Z"))).toBe(10);
    expect(daysSince(null)).toBeNull();
  });
  it("formats storage sizes", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2 KB");
    expect(formatBytes(5 * 1024 * 1024)).toBe("5.0 MB");
  });
});
