"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState, type DragEvent } from "react";
import { Alert, Badge, Button, Card, Checkbox, Input, Select, cn } from "@/components/ui";
import { ToggleChip } from "@/components/ui/client";
import { api, ApiError, errorMessage } from "@/lib/api";
import { formatDateTime, formatDuration } from "@/lib/format";
import { moveStop, slugsOf } from "@/lib/plan-edit";
import type { ChecklistItem, Destination, Plan, PlanStop } from "@/lib/types";
import { SaveOffline } from "./pwa";
import { useI18n, useSession } from "./providers";

export const INTERESTS = ["history", "heritage", "culture", "adventure", "nature", "food", "faith", "crafts", "photography"] as const;
const PACES = ["relaxed", "balanced", "full"] as const;
type Pace = (typeof PACES)[number];

interface Itinerary {
  id: string;
  title: string;
  plan: Plan;
  request?: unknown;
  shared?: boolean;
  updated_at?: string;
}

export interface PlannerProps {
  include?: string;
  itineraryId?: string;
  initialDays?: number;
  initialInterests?: string[];
  initialStart?: string;
}

/* ------------------------------------------------------------------ pure helpers (unit-tested) */

export function legLabel(leg: PlanStop["travel_from_previous"], t: (k: never, v?: Record<string, string | number>) => string): string {
  const tt = t as (k: string, v?: Record<string, string | number>) => string;
  if (!leg) return "";
  if (leg.verified && leg.distance_km != null) {
    return tt("plan.legVerified", { km: Math.round(leg.distance_km), duration: formatDuration(leg.duration_minutes, tt("common.unknown")) });
  }
  if (leg.distance_km != null) return tt("plan.legEstimate", { km: Math.round(leg.distance_km) });
  return tt("plan.legUnknown");
}

/* ------------------------------------------------------------------ route plot */

// Approximate bounding box (same schematic as the map page; not a cartographic product).
const BOX = { minLat: 12.2, maxLat: 14.95, minLng: 36.4, maxLng: 40.1 };
const DAY_COLORS = ["var(--color-forest)", "var(--color-earth)", "var(--color-olive)", "var(--color-terracotta)", "var(--color-sandstone)"];

function RoutePlot({ plan }: { plan: Plan }) {
  const { t } = useI18n();
  const W = 400;
  const H = 300;
  const xy = (c: NonNullable<PlanStop["coordinates"]>) => [((c.lng - BOX.minLng) / (BOX.maxLng - BOX.minLng)) * W, H - ((c.lat - BOX.minLat) / (BOX.maxLat - BOX.minLat)) * H] as const;
  const located = plan.days.flatMap((d) => d.stops.filter((s) => s.coordinates));
  if (located.length === 0) return null;
  const offsets = plan.days.map((_, di) => plan.days.slice(0, di).reduce((a, d) => a + d.stops.filter((s) => s.coordinates).length, 0));
  return (
    <figure className="rounded-[var(--radius)] border border-line bg-surface p-4">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={t("plan.plotLabel")} className="h-auto w-full rounded-xl bg-surface-2/60">
        {plan.days.map((d, di) => {
          const pts = d.stops.filter((s) => s.coordinates);
          const color = DAY_COLORS[di % DAY_COLORS.length];
          return (
            <g key={d.day}>
              {pts.slice(1).map((s, i) => {
                const [x1, y1] = xy(pts[i].coordinates!);
                const [x2, y2] = xy(s.coordinates!);
                return <line key={s.slug} x1={x1} y1={y1} x2={x2} y2={y2} stroke={color} strokeWidth={2.5} strokeDasharray={s.travel_from_previous?.verified ? undefined : "6 5"} />;
              })}
              {pts.map((s, pi) => {
                const [x, y] = xy(s.coordinates!);
                const n = offsets[di] + pi + 1;
                return (
                  <g key={s.slug}>
                    <circle cx={x} cy={y} r={9} fill={color} />
                    <text x={x} y={y + 3.5} textAnchor="middle" fontSize="10" fill="var(--color-bg)" fontWeight="700">
                      {n}
                    </text>
                    <title>{s.name}</title>
                  </g>
                );
              })}
            </g>
          );
        })}
      </svg>
      <figcaption className="mt-2 text-xs text-muted">{t("plan.plotCaption")}</figcaption>
    </figure>
  );
}

/* ------------------------------------------------------------------ checklist + summary */

const CHECK_ICON: Record<ChecklistItem["kind"], string> = { permit: "📄", advisory: "⚠️", accessibility: "♿", verification: "🔎", duration: "⏱", travel: "🛣" };

function Checklist({ items }: { items: ChecklistItem[] }) {
  const { t } = useI18n();
  const [done, setDone] = useState<Record<number, boolean>>({});
  return (
    <section aria-labelledby="checklist-h" className="rounded-[var(--radius)] border border-line bg-surface p-5">
      <h2 id="checklist-h" className="text-2xl">
        {t("plan.checklist")}
      </h2>
      <p className="mt-1 text-xs text-muted">{t("plan.checklistLead")}</p>
      {items.length === 0 ? (
        <p className="mt-3 text-sm text-muted">{t("plan.checklistEmpty")}</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {items.map((c, i) => (
            <li key={i} className="flex gap-3 text-sm">
              <input id={`chk-${i}`} type="checkbox" checked={!!done[i]} onChange={(e) => setDone((d) => ({ ...d, [i]: e.target.checked }))} className="mt-1 h-4 w-4 accent-[var(--color-forest)]" />
              <label htmlFor={`chk-${i}`} className={cn(done[i] && "text-muted line-through")}>
                <span aria-hidden="true" className="mr-1">
                  {CHECK_ICON[c.kind] ?? "•"}
                </span>
                <span className="sr-only">{t(`plan.checkKind.${c.kind}`)}: </span>
                {c.text}
              </label>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function SummaryHeader({ plan }: { plan: Plan }) {
  const { t } = useI18n();
  const s = plan.summary;
  if (!s) return null;
  const items = [
    [t("plan.sumDays"), String(s.days)],
    [t("plan.sumStops"), String(s.stop_count)],
    [t("plan.sumKnownTime"), s.known_minutes ? formatDuration(s.known_minutes, t("common.unknown")) : t("common.unknown")],
    [t("plan.sumLegs"), t("plan.sumLegsValue", { verified: s.verified_legs, unverified: s.unverified_legs })],
  ];
  return (
    <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-[var(--radius)] border border-line bg-line sm:grid-cols-4">
      {items.map(([k, v]) => (
        <div key={k} className="bg-surface px-4 py-3">
          <dt className="text-[0.65rem] uppercase tracking-[0.15em] text-muted">{k}</dt>
          <dd className="mt-1 font-display text-2xl">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

/* ------------------------------------------------------------------ stop card */

function StopCard({
  s,
  dayIdx,
  idx,
  dayCount,
  lastInDay,
  busy,
  onMove,
  onRemove,
  onSwap,
  onDragStart,
  onDropHere,
}: {
  s: PlanStop;
  dayIdx: number;
  idx: number;
  dayCount: number;
  lastInDay: boolean;
  busy: boolean;
  onMove: (to: { day: number; index: number }) => void;
  onRemove: () => void;
  onSwap: (slug: string) => void;
  onDragStart: (e: DragEvent) => void;
  onDropHere: (e: DragEvent) => void;
}) {
  const { t, locale } = useI18n();
  const [over, setOver] = useState(false);
  const leg = s.travel_from_previous;
  return (
    <li
      className="relative"
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        setOver(false);
        onDropHere(e);
      }}
    >
      {leg && (
        <div className="relative my-2 ml-4 flex items-center gap-2 border-l-2 border-dashed border-line py-2 pl-5">
          <span className={cn("rounded-full border px-3 py-0.5 text-xs", leg.verified ? "border-forest/50 bg-forest/5 text-forest" : "border-line text-muted")}>
            🛣 {legLabel(leg, t as never)}
          </span>
        </div>
      )}
      <article
        draggable={!busy}
        onDragStart={onDragStart}
        className={cn("rounded-2xl border bg-bg p-4 shadow-sm transition-colors print:shadow-none", over ? "border-forest" : "border-line")}
        aria-label={s.name}
      >
        <div className="flex items-start gap-3">
          <span aria-hidden="true" className="no-print mt-1 cursor-grab select-none text-muted" title={t("plan.dragHint")}>
            ⠿
          </span>
          <div className="min-w-0 flex-1">
            <h4 className="text-2xl leading-tight">
              <Link href={`/${locale}/destinations/${s.slug}`} className="hover:underline">
                {s.name}
              </Link>
            </h4>
            <p className="text-sm text-muted">{s.area}</p>
            <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
              <Badge tone="neutral">⏱ {s.visit_duration_minutes != null ? formatDuration(s.visit_duration_minutes, t("common.unknown")) : t("plan.durationUnknown")}</Badge>
              {s.permit_required === "yes" && <Badge tone="caution">{t("plan.permitNeeded")}</Badge>}
              {s.permit_required === "unknown" && <Badge tone="neutral">{t("plan.permitUnknown")}</Badge>}
              {s.advisory_level && <Badge tone="caution">⚠ {t(`advisory.level.${s.advisory_level}`)}</Badge>}
            </div>
            {s.reasons.length > 0 && (
              <details className="mt-3 text-sm">
                <summary className="cursor-pointer text-xs font-semibold uppercase tracking-[0.15em] text-earth">{t("plan.why")}</summary>
                <ul className="mt-1 list-disc pl-5">
                  {s.reasons.map((r) => (
                    <li key={r}>{r}</li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        </div>
        <div className="no-print mt-3 flex flex-wrap items-center gap-1.5 border-t border-line pt-3 text-sm">
          <button type="button" disabled={busy || (idx === 0 && dayIdx === 0)} onClick={() => (idx === 0 ? onMove({ day: dayIdx - 1, index: Infinity }) : onMove({ day: dayIdx, index: idx - 1 }))} className="rounded-full border border-line px-2.5 py-1 disabled:opacity-40" aria-label={t("plan.moveUp", { name: s.name })}>
            ↑
          </button>
          <button type="button" disabled={busy || (lastInDay && dayIdx === dayCount - 1)} onClick={() => (lastInDay ? onMove({ day: dayIdx + 1, index: 0 }) : onMove({ day: dayIdx, index: idx + 2 }))} className="rounded-full border border-line px-2.5 py-1 disabled:opacity-40" aria-label={t("plan.moveDown", { name: s.name })}>
            ↓
          </button>
          {dayCount > 1 && (
            <label className="flex items-center gap-1">
              <span className="sr-only">{t("plan.moveToDay", { name: s.name })}</span>
              <select
                disabled={busy}
                value={dayIdx}
                onChange={(e) => onMove({ day: Number(e.target.value), index: Infinity })}
                className="rounded-full border border-line bg-surface px-2 py-1 text-sm"
              >
                {Array.from({ length: dayCount }, (_, d) => (
                  <option key={d} value={d}>
                    {t("plan.day", { n: d + 1 })}
                  </option>
                ))}
              </select>
            </label>
          )}
          {(s.alternatives?.length ?? 0) > 0 && (
            <details className="relative">
              <summary className="cursor-pointer list-none rounded-full border border-line px-3 py-1">⇄ {t("plan.swap")}</summary>
              <ul className="absolute left-0 z-10 mt-1 w-64 rounded-xl border border-line bg-surface p-2 shadow-[var(--shadow)]">
                {s.alternatives!.map((a) => (
                  <li key={a.slug}>
                    <button type="button" disabled={busy} onClick={() => onSwap(a.slug)} className="w-full rounded-lg px-3 py-2 text-left hover:bg-surface-2">
                      <span className="block font-medium">{a.name}</span>
                      <span className="block text-xs text-muted">{a.reason}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </details>
          )}
          <button type="button" disabled={busy} onClick={onRemove} className="ml-auto rounded-full px-3 py-1 text-danger hover:bg-surface-2">
            {t("plan.remove")}
          </button>
        </div>
      </article>
    </li>
  );
}

/* ------------------------------------------------------------------ main */

export function Planner({ include, itineraryId, initialDays, initialInterests, initialStart }: PlannerProps) {
  const { t, locale } = useI18n();
  const { me } = useSession();
  const [destinations, setDestinations] = useState<Pick<Destination, "slug" | "name">[]>([]);
  const [step, setStep] = useState(0);
  const [days, setDays] = useState(Math.max(1, Math.min(14, initialDays ?? 3)));
  const [start, setStart] = useState(initialStart ?? include ?? "");
  const [interests, setInterests] = useState<string[]>(initialInterests?.length ? initialInterests.filter((i) => (INTERESTS as readonly string[]).includes(i)) : ["history", "heritage"]);
  const [pace, setPace] = useState<Pace>("balanced");
  const [stepFree, setStepFree] = useState(false);
  const [group, setGroup] = useState(2);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [busy, setBusy] = useState(false);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<Itinerary | null>(null);
  const [title, setTitle] = useState("");
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [mine, setMine] = useState<Itinerary[] | null>(null);
  const [announce, setAnnounce] = useState("");
  const drag = useRef<{ day: number; index: number } | null>(null);
  const resultsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api<{ items: Destination[] }>(`/destinations?locale=${locale}&limit=100`)
      .then((r) => setDestinations(r.items.map(({ slug, name }) => ({ slug, name }))))
      .catch(() => undefined);
  }, [locale]);

  useEffect(() => {
    if (!me) return;
    api<Itinerary[] | { items: Itinerary[] }>("/itineraries")
      .then((r) => setMine(Array.isArray(r) ? r : r.items))
      .catch(() => setMine(null));
    if (itineraryId) {
      api<Itinerary>(`/itineraries/${itineraryId}`)
        .then((it) => {
          setSaved(it);
          setPlan(it.plan);
          setTitle(it.title);
        })
        .catch((e) => setError(errorMessage(e)));
    }
  }, [me, itineraryId]);

  const request = {
    days,
    start_slug: start || undefined,
    interests,
    pace,
    accessibility: { step_free_required: stepFree },
    group_size: group,
    locale,
    avoid_slugs: [] as string[],
  };

  async function create() {
    setBusy(true);
    setError(null);
    setSaved(null);
    setShareUrl(null);
    try {
      setPlan(await api<Plan>("/planner/plan", { json: request }));
      requestAnimationFrame(() => resultsRef.current?.scrollIntoView({ block: "start", behavior: "smooth" }));
    } catch (err) {
      setError(err instanceof ApiError && err.notAvailable ? t("common.notAvailableYet") : errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  /** Re-validate an edited grid on the server; the planner stays deterministic and authoritative. */
  async function annotate(grid: string[][], message: string) {
    if (!plan) return;
    setChecking(true);
    setError(null);
    try {
      const next = await api<Plan>("/planner/annotate", { json: { days: grid.length ? grid : [[]], locale, interests } });
      setPlan(next);
      setAnnounce(message);
    } catch (err) {
      if (err instanceof ApiError && err.code === "unknown_destinations") setError(t("plan.errUnknown"));
      else if (err instanceof ApiError && (err.code === "advisory_blocked" || err.code === "travel_not_advised")) setError(err.message || t("plan.errAdvisory"));
      else setError(errorMessage(err));
    } finally {
      setChecking(false);
    }
  }

  function move(from: { day: number; index: number }, to: { day: number; index: number }) {
    if (!plan) return;
    const grid = slugsOf(plan);
    if (to.day < 0 || to.day >= grid.length) return;
    const index = to.index === Infinity ? grid[to.day].length + (from.day === to.day ? 1 : 0) : to.index;
    const name = plan.days[from.day].stops[from.index]?.name ?? "";
    void annotate(moveStop(grid, from, { day: to.day, index }), t("plan.moved", { name, n: to.day + 1 }));
  }

  function remove(day: number, index: number) {
    if (!plan) return;
    const grid = slugsOf(plan);
    const name = plan.days[day].stops[index]?.name ?? "";
    grid[day].splice(index, 1);
    void annotate(grid, t("plan.removed", { name }));
  }

  function swap(day: number, index: number, slug: string) {
    if (!plan) return;
    const grid = slugsOf(plan);
    grid[day][index] = slug;
    void annotate(grid, t("plan.swapped"));
  }

  async function save() {
    if (!plan) return;
    setError(null);
    try {
      const name = title.trim().length >= 2 ? title.trim() : `${t("plan.title")} — ${plan.days.length}`;
      let it = saved;
      if (!it) it = await api<Itinerary>("/itineraries", { json: { title: name, request } });
      if (saved || plan.edited) it = await api<Itinerary>(`/itineraries/${it.id}`, { method: "PUT", json: { title: name, days: slugsOf(plan), locale } });
      setSaved(it);
      setPlan(it.plan);
      setMine((m) => [it, ...(m ?? []).filter((x) => x.id !== it.id)]);
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function share() {
    if (!saved) return;
    try {
      const r = await api<{ url: string; token: string }>(`/itineraries/${saved.id}/share`, { method: "POST" });
      setShareUrl(`${window.location.origin}/${locale}/plan/shared/${r.token}`);
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function revoke() {
    if (!saved) return;
    try {
      await api(`/itineraries/${saved.id}/share`, { method: "DELETE" });
      setShareUrl(null);
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  const steps = [t("plan.stepTrip"), t("plan.stepInterests"), t("plan.stepNeeds")];
  const startName = useMemo(() => destinations.find((d) => d.slug === start)?.name, [destinations, start]);

  return (
    <div className="space-y-10">
      {/* ------------------------------------------------ brief */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (step < steps.length - 1) setStep(step + 1);
          else void create();
        }}
        className="no-print rounded-[var(--radius)] border border-line bg-surface p-6 shadow-[var(--shadow)] sm:p-8"
        aria-label={t("plan.briefLabel")}
      >
        <ol className="flex flex-wrap gap-2" aria-label={t("plan.stepsLabel")}>
          {steps.map((s, i) => (
            <li key={s}>
              <button
                type="button"
                onClick={() => setStep(i)}
                aria-current={i === step ? "step" : undefined}
                className={cn("flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm", i === step ? "border-forest bg-forest text-on-forest" : i < step ? "border-forest/40 text-forest" : "border-line text-muted")}
              >
                <span className="font-semibold">{i + 1}</span> {s}
              </button>
            </li>
          ))}
        </ol>

        <div className="mt-6 min-h-[180px]">
          {step === 0 && (
            <div className="grid gap-6 sm:grid-cols-2">
              <div>
                <label htmlFor="days" className="flex items-baseline justify-between text-sm font-medium">
                  {t("plan.days")}
                  <output htmlFor="days" className="font-display text-3xl text-forest">
                    {days}
                  </output>
                </label>
                <input id="days" type="range" min={1} max={14} value={days} onChange={(e) => setDays(Number(e.target.value))} className="mt-3 w-full accent-[var(--color-forest)]" />
                <p className="mt-1 flex justify-between text-xs text-muted">
                  <span>1</span>
                  <span>14</span>
                </p>
              </div>
              <Select id="start" label={t("plan.start")} value={start} onChange={(e) => setStart(e.target.value)} options={[{ value: "", label: t("plan.anyStart") }, ...destinations.map((d) => ({ value: d.slug, label: d.name }))]} />
            </div>
          )}
          {step === 1 && (
            <div className="space-y-6">
              <fieldset>
                <legend className="mb-2 text-sm font-medium">{t("plan.interests")}</legend>
                <div className="flex flex-wrap gap-2">
                  {INTERESTS.map((i) => (
                    <ToggleChip key={i} pressed={interests.includes(i)} onToggle={() => setInterests((xs) => (xs.includes(i) ? xs.filter((x) => x !== i) : [...xs, i]))}>
                      {t(`plan.interest.${i}`)}
                    </ToggleChip>
                  ))}
                </div>
                {interests.length === 0 && <p className="mt-2 text-sm text-caution">{t("plan.pickInterest")}</p>}
              </fieldset>
              <fieldset>
                <legend className="mb-2 text-sm font-medium">{t("plan.pace")}</legend>
                <div className="grid gap-2 sm:grid-cols-3">
                  {PACES.map((p) => (
                    <label key={p} className={cn("cursor-pointer rounded-xl border p-3 text-sm", pace === p ? "border-forest bg-surface-2" : "border-line")}>
                      <input type="radio" name="pace" value={p} checked={pace === p} onChange={() => setPace(p)} className="mr-2 accent-[var(--color-forest)]" />
                      <span className="font-medium">{t(`plan.pace${p[0].toUpperCase()}${p.slice(1)}` as "plan.paceRelaxed")}</span>
                      <span className="mt-1 block text-xs text-muted">{t(`plan.paceHint.${p}`)}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
            </div>
          )}
          {step === 2 && (
            <div className="grid gap-6 sm:grid-cols-2">
              <Input id="group" type="number" min={1} max={60} label={t("plan.groupSize")} value={group} onChange={(e) => setGroup(Math.max(1, Math.min(60, Number(e.target.value) || 1)))} />
              <div className="pt-7">
                <Checkbox id="stepfree" label={t("plan.stepFree")} checked={stepFree} onChange={(e) => setStepFree(e.target.checked)} />
              </div>
              <p className="text-sm text-muted sm:col-span-2">
                {t("plan.briefSummary", { days, interests: interests.map((i) => t(`plan.interest.${i as (typeof INTERESTS)[number]}`)).join(", ") || "—", start: startName ?? t("plan.anyStart") })}
              </p>
            </div>
          )}
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          {step > 0 && (
            <Button type="button" variant="ghost" onClick={() => setStep(step - 1)}>
              ← {t("plan.back")}
            </Button>
          )}
          {step < steps.length - 1 ? (
            <Button type="submit" disabled={step === 1 && interests.length === 0}>
              {t("plan.next")} →
            </Button>
          ) : null}
          <Button type="button" variant={step < steps.length - 1 ? "secondary" : "primary"} onClick={() => void create()} disabled={busy || interests.length === 0} className="ml-auto">
            {busy ? t("plan.creating") : t("plan.create")}
          </Button>
        </div>
        <p className="mt-4 text-xs text-muted">{t("plan.honest")}</p>
      </form>

      {/* ------------------------------------------------ results */}
      <div ref={resultsRef} className="scroll-mt-24 space-y-6">
        <p role="status" aria-live="polite" className="sr-only">
          {announce}
        </p>
        {error && <Alert tone="danger">{error}</Alert>}
        {plan && (
          <>
            <Alert tone={plan.mode === "virtual" ? "caution" : "info"} title={t("plan.notice")}>
              {plan.notice}
            </Alert>
            <SummaryHeader plan={plan} />
            {plan.edited && <p className="text-xs text-muted">{t("plan.editedNote")}</p>}

            {plan.mode === "virtual" && (
              <Card>
                <h2 className="text-2xl">{t("plan.virtualTitle")}</h2>
                <p className="mt-2">{t("plan.virtualMode")}</p>
                <ul className="mt-3 flex flex-wrap gap-2">
                  {plan.virtual_alternatives.map((v) => (
                    <li key={v.slug}>
                      <Link className="rounded-full border border-line px-3 py-1.5 text-sm hover:border-sandstone" href={`/${locale}/destinations/${v.slug}`}>
                        {v.name}
                      </Link>
                    </li>
                  ))}
                </ul>
              </Card>
            )}

            <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_340px]">
              <div className={cn("space-y-6", checking && "opacity-70")} aria-busy={checking}>
                {checking && (
                  <p role="status" className="text-sm text-muted">
                    {t("plan.rechecking")}
                  </p>
                )}
                {plan.mode === "operational" &&
                  plan.days.map((day, di) => (
                    <section key={day.day} aria-labelledby={`day-${day.day}`} className="rounded-[var(--radius)] border border-line bg-surface p-5 sm:p-6 print:break-inside-avoid">
                      <div className="flex items-baseline gap-3">
                        <span aria-hidden="true" className="h-3 w-3 rounded-full" style={{ background: DAY_COLORS[di % DAY_COLORS.length] }} />
                        <h3 id={`day-${day.day}`} className="text-3xl">
                          {t("plan.day", { n: day.day })}
                        </h3>
                        <span className="text-sm text-muted">{t("plan.stopsCount", { n: day.stops.length })}</span>
                      </div>
                      {day.stops.length === 0 ? (
                        <p
                          className="mt-3 rounded-xl border border-dashed border-line p-4 text-muted"
                          onDragOver={(e) => e.preventDefault()}
                          onDrop={() => {
                            if (drag.current) move(drag.current, { day: di, index: 0 });
                            drag.current = null;
                          }}
                        >
                          {t("plan.restDay")}
                        </p>
                      ) : (
                        <ol className="mt-4">
                          {day.stops.map((s, si) => (
                            <StopCard
                              key={`${s.slug}-${si}`}
                              s={s}
                              dayIdx={di}
                              idx={si}
                              dayCount={plan.days.length}
                              lastInDay={si === day.stops.length - 1}
                              busy={checking}
                              onMove={(to) => move({ day: di, index: si }, to)}
                              onRemove={() => remove(di, si)}
                              onSwap={(slug) => swap(di, si, slug)}
                              onDragStart={(e) => {
                                drag.current = { day: di, index: si };
                                e.dataTransfer.effectAllowed = "move";
                                e.dataTransfer.setData("text/plain", s.slug);
                              }}
                              onDropHere={(e) => {
                                e.preventDefault();
                                if (drag.current) move(drag.current, { day: di, index: si });
                                drag.current = null;
                              }}
                            />
                          ))}
                        </ol>
                      )}
                      {day.unknowns.length > 0 && (
                        <Alert tone="caution" title={t("plan.unknowns")} className="mt-5">
                          <ul className="list-disc pl-5">
                            {day.unknowns.map((u) => (
                              <li key={u}>{u}</li>
                            ))}
                          </ul>
                        </Alert>
                      )}
                    </section>
                  ))}
                {plan.excluded.length > 0 && (
                  <Card>
                    <h2 className="text-2xl">{t("plan.excluded")}</h2>
                    <ul className="mt-3 space-y-1 text-sm">
                      {plan.excluded.map((x) => (
                        <li key={x.slug}>
                          <strong>{x.name}</strong> — {x.reason}
                        </li>
                      ))}
                    </ul>
                  </Card>
                )}
                <p className="text-xs text-muted">{formatDateTime(plan.generated_at, locale)}</p>
              </div>

              <aside className="space-y-6 lg:sticky lg:top-24 lg:self-start">
                {plan.mode === "operational" && <RoutePlot plan={plan} />}
                <Checklist items={plan.checklist ?? []} />
                <div className="no-print space-y-4 rounded-[var(--radius)] border border-line bg-surface p-5">
                  <div className="flex flex-wrap gap-2">
                    <Button variant="secondary" size="sm" onClick={() => window.print()}>
                      {t("plan.print")}
                    </Button>
                    <SaveOffline item={{ key: `itinerary:${saved?.id ?? "draft"}:${locale}`, kind: "itinerary", title: title || t("plan.title"), href: saved ? `/${locale}/plan?itinerary=${saved.id}` : `/${locale}/plan`, locale, data: plan }} />
                  </div>
                  {plan.mode !== "operational" ? null : me ? (
                    <>
                      <Input id="it-title" label={t("plan.titleLabel")} value={title} onChange={(e) => setTitle(e.target.value)} maxLength={120} />
                      <Button onClick={save} className="w-full" disabled={checking}>
                        {t("plan.save")}
                      </Button>
                      {saved && (
                        <div className="flex flex-wrap gap-2">
                          <p role="status" className="w-full text-sm text-success">
                            {t("plan.saved")}
                          </p>
                          <a className="rounded-full border border-line px-3 py-1.5 text-sm" href={`/api/itineraries/${saved.id}/ics`}>
                            {t("plan.ics")}
                          </a>
                          <a className="rounded-full border border-line px-3 py-1.5 text-sm" href={`/api/itineraries/${saved.id}/pdf`}>
                            {t("plan.pdf")}
                          </a>
                          <Button variant="secondary" size="sm" onClick={share}>
                            {t("plan.share")}
                          </Button>
                          {shareUrl && (
                            <Button variant="ghost" size="sm" onClick={revoke}>
                              {t("plan.revokeShare")}
                            </Button>
                          )}
                        </div>
                      )}
                      {shareUrl && <Input id="share-url" label={t("plan.shareLink")} value={shareUrl} readOnly onFocus={(e) => e.currentTarget.select()} />}
                    </>
                  ) : (
                    <p className="text-sm text-muted">
                      <Link href={`/${locale}/account`} className="underline">
                        {t("common.signIn")}
                      </Link>{" "}
                      — {t("plan.signInToSave")}
                    </p>
                  )}
                </div>
              </aside>
            </div>
          </>
        )}
        {me && mine && mine.length > 0 && (
          <section className="no-print">
            <h2 className="text-2xl">{t("plan.myItineraries")}</h2>
            <ul className="mt-3 divide-y divide-line rounded-[var(--radius)] border border-line bg-surface">
              {mine.map((it) => (
                <li key={it.id} className="px-4 py-3">
                  <Link className="underline" href={`/${locale}/plan?itinerary=${it.id}`}>
                    {it.title}
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </div>
  );
}
