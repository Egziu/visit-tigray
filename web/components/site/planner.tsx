"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Alert, Badge, Button, Card, Checkbox, Input, Select } from "@/components/ui";
import { ToggleChip } from "@/components/ui/client";
import { api, ApiError, errorMessage } from "@/lib/api";
import { formatDateTime, formatDuration } from "@/lib/format";
import type { Destination, Plan } from "@/lib/types";
import { SaveOffline } from "./pwa";
import { useI18n, useSession } from "./providers";

const INTERESTS = ["history", "heritage", "culture", "adventure", "nature", "food", "faith", "crafts", "photography"];

interface Itinerary {
  id: string;
  title: string;
  plan: Plan;
  request?: unknown;
  share_token?: string | null;
  updated_at?: string;
}

export function Planner({ include, itineraryId }: { include?: string; itineraryId?: string }) {
  const { t, locale } = useI18n();
  const { me } = useSession();
  const [destinations, setDestinations] = useState<Pick<Destination, "slug" | "name">[]>([]);
  const [days, setDays] = useState(3);
  const [start, setStart] = useState("");
  const [interests, setInterests] = useState<string[]>(["history", "heritage"]);
  const [pace, setPace] = useState("balanced");
  const [stepFree, setStepFree] = useState(false);
  const [group, setGroup] = useState(2);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<Itinerary | null>(null);
  const [title, setTitle] = useState("");
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [mine, setMine] = useState<Itinerary[] | null>(null);

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
    include_slugs: include ? [include] : [],
  };

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setSaved(null);
    setShareUrl(null);
    try {
      setPlan(await api<Plan>("/planner/plan", { json: request }));
    } catch (err) {
      setError(err instanceof ApiError && err.notAvailable ? t("common.notAvailableYet") : errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    if (!plan) return;
    try {
      const body = { title: title || `${t("plan.title")} — ${days}`, request, plan };
      const it = saved
        ? await api<Itinerary>(`/itineraries/${saved.id}`, { method: "PUT", json: body })
        : await api<Itinerary>("/itineraries", { json: body });
      setSaved(it);
      setMine((m) => [it, ...(m ?? []).filter((x) => x.id !== it.id)]);
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function share() {
    if (!saved) return;
    try {
      const r = await api<{ url: string; token: string }>(`/itineraries/${saved.id}/share`, { method: "POST" });
      setShareUrl(r.url.startsWith("http") ? r.url : `${window.location.origin}/${locale}/plan/shared/${r.token}`);
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

  return (
    <div className="grid gap-10 lg:grid-cols-[360px_1fr]">
      <form onSubmit={create} className="no-print h-fit space-y-5 rounded-[var(--radius)] border border-line bg-surface p-6" aria-label={t("plan.title")}>
        <Input id="days" type="number" min={1} max={14} label={t("plan.days")} value={days} onChange={(e) => setDays(Math.max(1, Math.min(14, Number(e.target.value) || 1)))} required />
        <Select id="start" label={t("plan.start")} value={start} onChange={(e) => setStart(e.target.value)} options={[{ value: "", label: t("plan.anyStart") }, ...destinations.map((d) => ({ value: d.slug, label: d.name }))]} />
        <fieldset>
          <legend className="mb-2 text-sm font-medium">{t("plan.interests")}</legend>
          <div className="flex flex-wrap gap-2">
            {INTERESTS.map((i) => (
              <ToggleChip key={i} pressed={interests.includes(i)} onToggle={() => setInterests((xs) => (xs.includes(i) ? xs.filter((x) => x !== i) : [...xs, i]))}>
                {i}
              </ToggleChip>
            ))}
          </div>
        </fieldset>
        <Select
          id="pace"
          label={t("plan.pace")}
          value={pace}
          onChange={(e) => setPace(e.target.value)}
          options={[
            { value: "relaxed", label: t("plan.paceRelaxed") },
            { value: "balanced", label: t("plan.paceBalanced") },
            { value: "full", label: t("plan.paceFull") },
          ]}
        />
        <Input id="group" type="number" min={1} max={60} label={t("plan.groupSize")} value={group} onChange={(e) => setGroup(Math.max(1, Number(e.target.value) || 1))} />
        <Checkbox id="stepfree" label={t("plan.stepFree")} checked={stepFree} onChange={(e) => setStepFree(e.target.checked)} />
        <Button type="submit" disabled={busy || interests.length === 0} className="w-full">
          {busy ? t("plan.creating") : t("plan.create")}
        </Button>
      </form>

      <div aria-live="polite" className="space-y-6">
        {error && <Alert tone="danger">{error}</Alert>}
        {plan && (
          <>
            <Alert tone={plan.mode === "virtual" ? "caution" : "info"} title={t("plan.notice")}>
              {plan.notice}
            </Alert>
            {plan.mode === "virtual" && (
              <Card>
                <p>{t("plan.virtualMode")}</p>
                <ul className="mt-3 flex flex-wrap gap-2">
                  {plan.virtual_alternatives.map((v) => (
                    <li key={v.slug}>
                      <Link className="rounded-full border border-line px-3 py-1.5 text-sm underline-offset-4 hover:underline" href={`/${locale}/destinations/${v.slug}`}>
                        {v.name}
                      </Link>
                    </li>
                  ))}
                </ul>
              </Card>
            )}
            {plan.days.map((day) => (
              <section key={day.day} className="rounded-[var(--radius)] border border-line bg-surface p-6 print:break-inside-avoid">
                <h2 className="text-3xl">{t("plan.day", { n: day.day })}</h2>
                {day.stops.length === 0 ? (
                  <p className="mt-3 text-muted">{t("plan.restDay")}</p>
                ) : (
                  <ol className="mt-5 space-y-6">
                    {day.stops.map((s) => (
                      <li key={s.slug} className="border-l-2 border-sandstone pl-5">
                        {s.travel_from_previous && (
                          <p className="mb-2 text-sm text-muted">
                            {t("plan.travel")}:{" "}
                            {s.travel_from_previous.verified && s.travel_from_previous.distance_km != null
                              ? t("plan.travelVerified", { km: s.travel_from_previous.distance_km, duration: formatDuration(s.travel_from_previous.duration_minutes, t("common.unknown")) })
                              : s.travel_from_previous.distance_km != null
                                ? t("plan.travelEstimate", { km: s.travel_from_previous.distance_km })
                                : t("plan.travelUnknown")}
                          </p>
                        )}
                        <h3 className="text-2xl">
                          <Link href={`/${locale}/destinations/${s.slug}`} className="hover:underline">
                            {s.name}
                          </Link>
                        </h3>
                        <p className="text-sm text-muted">
                          {s.area} · {t("destinations.duration")}: {formatDuration(s.visit_duration_minutes, t("common.unknown"))} · {t("destinations.permit")}:{" "}
                          {s.permit_required === "yes" ? t("common.yes") : s.permit_required === "no" ? t("common.no") : t("common.unknown")}
                        </p>
                        {s.advisory_level && <Badge tone="caution" className="mt-2">{t(`advisory.level.${s.advisory_level}`)}</Badge>}
                        {s.reasons.length > 0 && (
                          <div className="mt-2">
                            <p className="text-xs font-semibold uppercase tracking-[0.15em] text-earth">{t("plan.why")}</p>
                            <ul className="mt-1 list-disc pl-5 text-sm">
                              {s.reasons.map((r) => (
                                <li key={r}>{r}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </li>
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

            <div className="no-print space-y-4 rounded-[var(--radius)] border border-line bg-surface p-6">
              <div className="flex flex-wrap gap-3">
                <Button variant="secondary" onClick={() => window.print()}>
                  {t("plan.print")}
                </Button>
                <SaveOffline item={{ key: `itinerary:${saved?.id ?? "draft"}:${locale}`, kind: "itinerary", title: title || t("plan.title"), href: saved ? `/${locale}/plan?itinerary=${saved.id}` : `/${locale}/plan`, locale, data: plan }} />
              </div>
              {me ? (
                <>
                  <div className="flex flex-wrap items-end gap-3">
                    <div className="min-w-[240px] flex-1">
                      <Input id="it-title" label={t("plan.titleLabel")} value={title} onChange={(e) => setTitle(e.target.value)} maxLength={120} />
                    </div>
                    <Button onClick={save}>{t("plan.save")}</Button>
                  </div>
                  {saved && (
                    <div className="flex flex-wrap gap-3">
                      <p role="status" className="w-full text-sm text-success">
                        {t("plan.saved")}
                      </p>
                      <a className="rounded-full border border-line px-4 py-2 text-sm" href={`/api/itineraries/${saved.id}/ics`}>
                        {t("plan.ics")}
                      </a>
                      <a className="rounded-full border border-line px-4 py-2 text-sm" href={`/api/itineraries/${saved.id}/pdf`}>
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
