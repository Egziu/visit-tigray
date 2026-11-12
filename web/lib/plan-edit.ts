import type { Plan } from "./types";

/** The slug grid sent to POST /api/planner/annotate after every manual edit. */
export function slugsOf(plan: Plan): string[][] {
  return plan.days.map((d) => d.stops.map((s) => s.slug));
}

/**
 * Move one stop. `to.index` is an insertion index in the grid *before* the move
 * (so "insert before the stop currently at index k"); it is clamped to the day length.
 */
export function moveStop(days: string[][], from: { day: number; index: number }, to: { day: number; index: number }): string[][] {
  if (!days[from.day] || !days[to.day]) return days;
  const next = days.map((d) => [...d]);
  const [slug] = next[from.day].splice(from.index, 1);
  if (slug === undefined) return days;
  let idx = to.index;
  if (from.day === to.day && from.index < to.index) idx -= 1;
  idx = Math.max(0, Math.min(idx, next[to.day].length));
  next[to.day].splice(idx, 0, slug);
  return next;
}
