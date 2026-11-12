import { describe, expect, it } from "vitest";
import { moveStop } from "@/lib/plan-edit";

const grid = [["a", "b", "c"], ["d"], []];

describe("moveStop", () => {
  it("moves a stop down within a day (insert before index+2)", () => {
    expect(moveStop(grid, { day: 0, index: 0 }, { day: 0, index: 2 })).toEqual([["b", "a", "c"], ["d"], []]);
  });
  it("moves a stop up within a day", () => {
    expect(moveStop(grid, { day: 0, index: 2 }, { day: 0, index: 1 })).toEqual([["a", "c", "b"], ["d"], []]);
  });
  it("moves a stop to another day, clamping the index", () => {
    expect(moveStop(grid, { day: 0, index: 1 }, { day: 1, index: 99 })).toEqual([["a", "c"], ["d", "b"], []]);
    expect(moveStop(grid, { day: 1, index: 0 }, { day: 2, index: 0 })).toEqual([["a", "b", "c"], [], ["d"]]);
  });
  it("does not mutate the input and ignores bad indexes", () => {
    const copy = JSON.parse(JSON.stringify(grid));
    moveStop(grid, { day: 0, index: 0 }, { day: 1, index: 0 });
    expect(grid).toEqual(copy);
    expect(moveStop(grid, { day: 2, index: 0 }, { day: 0, index: 0 })).toBe(grid);
    expect(moveStop(grid, { day: 0, index: 0 }, { day: 9, index: 0 })).toBe(grid);
  });
});
