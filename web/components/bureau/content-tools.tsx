"use client";

import Link from "next/link";
import { useState } from "react";
import { Badge, Button, ButtonLink, Card, Checkbox, EmptyState, Input, Loading, Select, Table, Textarea } from "@/components/ui";
import { Tabs } from "@/components/ui/client";
import { useI18n, useSession } from "@/components/site/providers";
import { api } from "@/lib/api";
import { formatDate, formatDateTime } from "@/lib/format";
import type { MsgKey } from "@/lib/i18n";
import { BureauTitle } from "./shell";
import { LoadError, useAction, useLoad } from "./hooks";

/* ================================================================ types */

interface Translation {
  name: string;
  eyebrow: string;
  summary: string;
  body: string;
  etiquette: string;
  accessibility_notes: string;
  status: string;
}
interface Working {
  category_id: string | null;
  interests: string[];
  area: string;
  lat: number | null;
  lng: number | null;
  location_sensitivity: "public" | "coarse" | "hidden";
  visit_duration_minutes: number | null;
  accessibility: { step_free?: string; terrain?: string; facilities?: string; notes?: string };
  permit_required: string;
  permit_authority: string | null;
  sources: { title: string; author?: string | null; publisher?: string | null; year?: string | null; url?: string | null }[];
  translations: Record<string, Translation>;
}
interface StaffDestination {
  id: string;
  slug: string;
  status: string;
  category: string | null;
  publish_at: string | null;
  published_at: string | null;
  verified_at: string | null;
  review_due: string | null;
  is_synthetic: boolean;
  updated_at: string;
  is_live: boolean;
  has_unpublished_changes: boolean;
  working: Working;
}

const STATUS_TONE: Record<string, "neutral" | "info" | "caution" | "success" | "danger"> = {
  draft: "neutral",
  in_review: "info",
  scheduled: "caution",
  published: "success",
  archived: "danger",
};

/* ================================================================ dashboard */

export function Dashboard() {
  const { t, locale } = useI18n();
  const { me, has } = useSession();
  const canContent = has("destinations.read_draft");
  const dest = useLoad<StaffDestination[]>(canContent ? "/bureau/destinations" : null);
  const fresh = useLoad<unknown[]>(canContent ? "/bureau/content/freshness" : null);
  const missing = useLoad<unknown[]>(canContent ? "/bureau/translations/missing" : null);
  const adv = useLoad<{ status: string }[]>(has("advisories.manage") ? "/bureau/advisories" : null);
  const media = useLoad<unknown[]>(has("media.manage") ? "/bureau/media?status=clean" : null);
  const chain = useLoad<{ valid: boolean; checked: number; broken_at_seq?: number }>(has("audit.view") ? "/bureau/audit/verify" : null);
  const count = (s: string) => dest.data?.filter((d) => d.status === s).length ?? 0;
  const tiles: { label: MsgKey; value: string | number | null; href?: string; show: boolean }[] = [
    { label: "bureau.dashboard.drafts", value: dest.data ? count("draft") : null, href: "/destinations", show: canContent },
    { label: "bureau.dashboard.inReview", value: dest.data ? count("in_review") : null, href: "/destinations", show: canContent },
    { label: "bureau.dashboard.published", value: dest.data ? dest.data.filter((d) => d.is_live).length : null, href: "/destinations", show: canContent },
    { label: "bureau.dashboard.freshness", value: fresh.data?.length ?? null, href: "/freshness", show: canContent },
    { label: "bureau.dashboard.translations", value: missing.data?.length ?? null, href: "/translations", show: canContent },
    { label: "bureau.dashboard.advisories", value: adv.data ? adv.data.filter((a) => a.status === "published").length : null, href: "/advisories", show: has("advisories.manage") },
    { label: "bureau.dashboard.media", value: media.data?.length ?? null, href: "/media", show: has("media.manage") },
    {
      label: "bureau.dashboard.auditChain",
      value: chain.data ? (chain.data.valid ? t("bureau.dashboard.valid") : t("bureau.dashboard.broken", { seq: chain.data.broken_at_seq ?? "?" })) : null,
      href: "/audit",
      show: has("audit.view"),
    },
  ];
  return (
    <>
      <BureauTitle title={t("bureau.dashboard.welcome", { name: me?.display_name ?? "" })} lead={t("bureau.dashboard.lead")} />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {tiles
          .filter((x) => x.show)
          .map((x) => (
            <Link key={x.label} href={`/${locale}/bureau${x.href ?? ""}`} className="lift rounded-[var(--radius)] border border-line bg-surface p-5">
              <p className="text-sm text-muted">{t(x.label)}</p>
              <p className="mt-2 font-display text-4xl">{x.value === null ? "—" : x.value}</p>
            </Link>
          ))}
      </div>
      <LoadError error={dest.error} />
      <section className="mt-10">
        <h2 className="text-2xl">{t("bureau.dashboard.quick")}</h2>
        <div className="mt-4 flex flex-wrap gap-3">
          {has("destinations.edit") && (
            <ButtonLink href={`/${locale}/bureau/destinations?new=1`} size="sm">
              {t("bureau.dashboard.newDestination")}
            </ButtonLink>
          )}
          {has("advisories.manage") && (
            <ButtonLink href={`/${locale}/bureau/advisories`} variant="secondary" size="sm">
              {t("bureau.dashboard.newAdvisory")}
            </ButtonLink>
          )}
        </div>
      </section>
    </>
  );
}

/* ================================================================ destinations list */

export function DestinationsList({ startNew }: { startNew?: boolean }) {
  const { t, locale } = useI18n();
  const { has } = useSession();
  const { data, error, loading, reload } = useLoad<StaffDestination[]>("/bureau/destinations");
  const [showNew, setShowNew] = useState(!!startNew);
  const [slug, setSlug] = useState("");
  const [name, setName] = useState("");
  const [summary, setSummary] = useState("");
  const [area, setArea] = useState("");
  const action = useAction();
  return (
    <>
      <BureauTitle
        title={t("bureau.nav.destinations")}
        actions={
          has("destinations.edit") && (
            <Button onClick={() => setShowNew((s) => !s)} aria-expanded={showNew}>
              {t("bureau.dest.new")}
            </Button>
          )
        }
      />
      {showNew && (
        <Card className="mb-8 max-w-2xl">
          <form
            className="space-y-4"
            onSubmit={async (e) => {
              e.preventDefault();
              const ok = await action.run(() => api("/bureau/destinations", { json: { slug, area, en: { name, summary } } }), t("bureau.dest.saved"));
              if (ok) {
                setShowNew(false);
                setSlug("");
                setName("");
                setSummary("");
                await reload();
              }
            }}
          >
            <Input id="n-slug" label={t("bureau.dest.slug")} value={slug} onChange={(e) => setSlug(e.target.value.toLowerCase())} pattern="[a-z0-9][a-z0-9-]{1,98}" required />
            <Input id="n-name" label={t("bureau.dest.name")} value={name} onChange={(e) => setName(e.target.value)} required maxLength={160} />
            <Textarea id="n-summary" label={t("bureau.dest.summary")} value={summary} onChange={(e) => setSummary(e.target.value)} maxLength={1200} />
            <Input id="n-area" label={t("bureau.dest.area")} value={area} onChange={(e) => setArea(e.target.value)} maxLength={120} />
            <Button type="submit" disabled={action.busy}>
              {t("bureau.dest.create")}
            </Button>
          </form>
        </Card>
      )}
      {action.view}
      <LoadError error={error} />
      {loading && !data ? (
        <Loading label={t("common.loading")} />
      ) : data && data.length === 0 ? (
        <EmptyState title={t("bureau.dest.none")} />
      ) : (
        data && (
          <Table caption={t("bureau.nav.destinations")}>
            <thead>
              <tr>
                <th>{t("bureau.dest.slug")}</th>
                <th>{t("bureau.dest.name")}</th>
                <th>{t("bureau.dest.status")}</th>
                <th>{t("common.lastVerified", { date: "" }).replace(/\s+$/, "")}</th>
                <th>
                  <span className="sr-only">{t("bureau.dest.edit")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {data.map((d) => (
                <tr key={d.id}>
                  <td className="font-mono text-xs">{d.slug}</td>
                  <td>{d.working.translations.en?.name ?? "—"}</td>
                  <td>
                    <div className="flex flex-wrap gap-1">
                      <Badge tone={STATUS_TONE[d.status] ?? "neutral"}>{d.status}</Badge>
                      {d.is_live && <Badge tone="success">{t("bureau.dest.live")}</Badge>}
                      {d.is_live && d.has_unpublished_changes && <Badge tone="caution">{t("bureau.dest.unpublished")}</Badge>}
                      {d.is_synthetic && <Badge tone="caution">{t("common.synthetic")}</Badge>}
                    </div>
                  </td>
                  <td>{d.verified_at ? formatDate(d.verified_at, locale) : t("common.notVerified")}</td>
                  <td>
                    <Link className="underline" href={`/${locale}/bureau/destinations/${d.id}`}>
                      {t("bureau.dest.edit")}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        )
      )}
    </>
  );
}

/* ================================================================ destination editor */

export function DestinationEditor({ id }: { id: string }) {
  const { t, locale } = useI18n();
  const { has } = useSession();
  const { data: d, error, reload, setData } = useLoad<StaffDestination>(`/bureau/destinations/${id}`);
  if (error) return <LoadError error={error} />;
  if (!d) return <Loading label={t("common.loading")} />;
  const update = (next: StaffDestination) => setData(next);
  const tabs = [
    { id: "content", label: t("bureau.dest.tabs.content"), content: <ContentTab d={d} onSaved={update} /> },
    { id: "details", label: t("bureau.dest.tabs.details"), content: <DetailsTab d={d} onSaved={update} /> },
    ...(has("geo.manage") ? [{ id: "geo", label: t("bureau.dest.tabs.geo"), content: <GeoTab d={d} onSaved={update} /> }] : []),
    { id: "sources", label: t("bureau.dest.tabs.sources"), content: <SourcesTab d={d} onSaved={update} /> },
    ...(has("media.manage") ? [{ id: "media", label: t("bureau.dest.tabs.media"), content: <MediaTab d={d} /> }] : []),
    { id: "revisions", label: t("bureau.dest.tabs.revisions"), content: <RevisionsTab d={d} onChange={reload} /> },
  ];
  return (
    <>
      <BureauTitle
        title={d.working.translations.en?.name ?? d.slug}
        lead={
          <span className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs">{d.slug}</span>
            <Badge tone={STATUS_TONE[d.status] ?? "neutral"}>{d.status}</Badge>
            {d.is_live && (
              <Link className="text-sm underline" href={`/${locale}/destinations/${d.slug}`}>
                {t("bureau.dest.live")} ↗
              </Link>
            )}
          </span>
        }
      />
      <WorkflowBar d={d} onChange={update} />
      <div className="mt-8">
        <Tabs label={t("bureau.dest.edit")} tabs={tabs} />
      </div>
    </>
  );
}

function WorkflowBar({ d, onChange }: { d: StaffDestination; onChange: (d: StaffDestination) => void }) {
  const { t } = useI18n();
  const { has } = useSession();
  const [note, setNote] = useState("");
  const [when, setWhen] = useState("");
  const a = useAction();
  const post = (path: string, body?: unknown) => async () => onChange(await api<StaffDestination>(`/bureau/destinations/${d.id}/${path}`, { method: "POST", json: body ?? {} }));
  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        {has("destinations.edit") && d.status !== "in_review" && d.status !== "archived" && (
          <Button variant="secondary" size="sm" onClick={() => a.run(post("submit"), t("bureau.dest.saved"))}>
            {t("bureau.dest.submit")}
          </Button>
        )}
        {has("destinations.publish") && d.status !== "archived" && (
          <>
            <div className="min-w-[220px]">
              <Input id="pub-note" label={t("bureau.dest.note")} value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} />
            </div>
            <Button size="sm" onClick={() => a.run(post("publish", { note }), t("bureau.dest.saved"))}>
              {t("bureau.dest.publish")}
            </Button>
            <div className="min-w-[220px]">
              <Input id="pub-at" type="datetime-local" label={t("bureau.dest.scheduleAt")} value={when} onChange={(e) => setWhen(e.target.value)} />
            </div>
            <Button variant="secondary" size="sm" disabled={!when} onClick={() => a.run(post("publish", { note, publish_at: new Date(when).toISOString() }), t("bureau.dest.saved"))}>
              {t("bureau.dest.schedule")}
            </Button>
            <Button
              variant="danger"
              size="sm"
              onClick={() => {
                if (window.confirm(t("bureau.dest.archiveConfirm"))) void a.run(post("archive"), t("bureau.dest.saved"));
              }}
            >
              {t("bureau.dest.archive")}
            </Button>
          </>
        )}
      </div>
      {a.view}
    </Card>
  );
}

function ContentTab({ d, onSaved }: { d: StaffDestination; onSaved: (d: StaffDestination) => void }) {
  const { t } = useI18n();
  const { has } = useSession();
  const [loc, setLoc] = useState("en");
  const current = d.working.translations[loc];
  const [form, setForm] = useState<Translation>(current ?? { name: "", eyebrow: "", summary: "", body: "", etiquette: "", accessibility_notes: "", status: "draft" });
  const [machine, setMachine] = useState(current?.status === "machine");
  const [alias, setAlias] = useState("");
  const a = useAction();
  // Reset the form when the language or the saved destination changes (render-time adjustment).
  const [prev, setPrev] = useState({ loc, d });
  if (prev.loc !== loc || prev.d !== d) {
    const c = d.working.translations[loc];
    setPrev({ loc, d });
    setForm(c ?? { name: "", eyebrow: "", summary: "", body: "", etiquette: "", accessibility_notes: "", status: "draft" });
    setMachine(c?.status === "machine");
  }
  const set = (k: keyof Translation) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setForm({ ...form, [k]: e.target.value });
  return (
    <div className="grid gap-8 xl:grid-cols-[1fr_280px]">
      <form
        className="space-y-4"
        lang={loc}
        onSubmit={(e) => {
          e.preventDefault();
          const { status: _s, ...body } = form;
          void _s;
          void a.run(async () => onSaved(await api<StaffDestination>(`/bureau/destinations/${d.id}/translations/${loc}`, { method: "PUT", json: { ...body, machine_generated: machine } })), t("bureau.dest.saved"));
        }}
      >
        <Select id="loc" label={t("bureau.dest.locale")} value={loc} onChange={(e) => setLoc(e.target.value)} options={[{ value: "en", label: "English" }, { value: "ti", label: "ትግርኛ" }, { value: "am", label: "አማርኛ" }]} />
        {current && <Badge tone={current.status === "reviewed" ? "success" : current.status === "machine" ? "earth" : "neutral"}>{current.status}</Badge>}
        <Input id="t-name" label={t("bureau.dest.name")} value={form.name} onChange={set("name")} required maxLength={160} />
        <Input id="t-eyebrow" label={t("bureau.dest.eyebrow")} value={form.eyebrow} onChange={set("eyebrow")} maxLength={160} />
        <Textarea id="t-summary" label={t("bureau.dest.summary")} value={form.summary} onChange={set("summary")} maxLength={1200} />
        <Textarea id="t-body" label={t("bureau.dest.body")} value={form.body} onChange={set("body")} rows={10} maxLength={30000} />
        <Textarea id="t-etiquette" label={t("bureau.dest.etiquette")} value={form.etiquette} onChange={set("etiquette")} maxLength={5000} />
        <Textarea id="t-access" label={t("bureau.dest.accessNotes")} value={form.accessibility_notes} onChange={set("accessibility_notes")} maxLength={5000} />
        <Checkbox id="t-machine" label={t("bureau.dest.machine")} checked={machine} onChange={(e) => setMachine(e.target.checked)} />
        <div className="flex flex-wrap gap-3">
          <Button type="submit" disabled={a.busy || !(has("translations.edit") || has("destinations.edit"))}>
            {t("bureau.dest.saveTranslation")}
          </Button>
          {has("translations.approve") && current && current.status !== "reviewed" && (
            <Button
              variant="secondary"
              onClick={() => a.run(async () => onSaved(await api<StaffDestination>(`/bureau/destinations/${d.id}/translations/${loc}/approve`, { method: "POST" })), t("bureau.dest.saved"))}
            >
              {t("bureau.dest.approve")}
            </Button>
          )}
        </div>
        {a.view}
      </form>
      {has("destinations.edit") && (
        <form
          className="h-fit space-y-3 rounded-lg border border-line p-4"
          onSubmit={(e) => {
            e.preventDefault();
            void a.run(() => api(`/bureau/destinations/${d.id}/aliases`, { json: { name: alias, locale: loc } }).then(() => setAlias("")), t("bureau.dest.saved"));
          }}
        >
          <Input id="alias" label={t("bureau.dest.alias")} value={alias} onChange={(e) => setAlias(e.target.value)} required maxLength={160} />
          <Button type="submit" size="sm" variant="secondary">
            {t("bureau.dest.addAlias")}
          </Button>
        </form>
      )}
    </div>
  );
}

function DetailsTab({ d, onSaved }: { d: StaffDestination; onSaved: (d: StaffDestination) => void }) {
  const { t } = useI18n();
  const w = d.working;
  const [interests, setInterests] = useState(w.interests.join(", "));
  const [area, setArea] = useState(w.area);
  const [duration, setDuration] = useState(w.visit_duration_minutes?.toString() ?? "");
  const [permit, setPermit] = useState(w.permit_required);
  const [authority, setAuthority] = useState(w.permit_authority ?? "");
  const [stepFree, setStepFree] = useState(w.accessibility?.step_free ?? "unknown");
  const [terrain, setTerrain] = useState(w.accessibility?.terrain ?? "unknown");
  const [facilities, setFacilities] = useState(w.accessibility?.facilities ?? "unknown");
  const [verified, setVerified] = useState(false);
  const [reviewDue, setReviewDue] = useState(d.review_due ?? "");
  const a = useAction();
  const tri = [
    { value: "unknown", label: t("common.unknown") },
    { value: "yes", label: t("common.yes") },
    { value: "no", label: t("common.no") },
  ];
  return (
    <form
      className="grid max-w-3xl gap-4 sm:grid-cols-2"
      onSubmit={(e) => {
        e.preventDefault();
        const body: Record<string, unknown> = {
          interests: interests.split(",").map((x) => x.trim()).filter(Boolean),
          area,
          permit_required: permit,
          permit_authority: authority || null,
          accessibility: { step_free: stepFree, terrain: terrain || "unknown", facilities: facilities || "unknown" },
          verified,
          review_due: reviewDue || null,
        };
        if (duration) body.visit_duration_minutes = Number(duration);
        else body.clear_duration = true;
        void a.run(async () => onSaved(await api<StaffDestination>(`/bureau/destinations/${d.id}`, { method: "PATCH", json: body })), t("bureau.dest.saved"));
      }}
    >
      <Input id="d-interests" label={t("bureau.dest.interests")} value={interests} onChange={(e) => setInterests(e.target.value)} />
      <Input id="d-area" label={t("bureau.dest.area")} value={area} onChange={(e) => setArea(e.target.value)} />
      <Input id="d-duration" type="number" min={5} max={1440} label={t("bureau.dest.duration")} hint={t("bureau.dest.clearDuration")} value={duration} onChange={(e) => setDuration(e.target.value)} />
      <Select id="d-permit" label={t("bureau.dest.permit")} value={permit} onChange={(e) => setPermit(e.target.value)} options={tri} />
      <Input id="d-auth" label={t("bureau.dest.permitAuthority")} value={authority} onChange={(e) => setAuthority(e.target.value)} />
      <Select id="d-step" label={t("bureau.dest.stepFree")} value={stepFree} onChange={(e) => setStepFree(e.target.value)} options={tri} />
      <Input id="d-terrain" label={t("bureau.dest.terrain")} value={terrain} onChange={(e) => setTerrain(e.target.value)} />
      <Input id="d-fac" label={t("bureau.dest.facilities")} value={facilities} onChange={(e) => setFacilities(e.target.value)} />
      <Input id="d-review" type="date" label={t("bureau.dest.reviewDue")} value={reviewDue} onChange={(e) => setReviewDue(e.target.value)} />
      <div className="sm:col-span-2">
        <Checkbox id="d-verified" label={t("bureau.dest.markVerified")} checked={verified} onChange={(e) => setVerified(e.target.checked)} />
      </div>
      <div className="sm:col-span-2">
        <Button type="submit" disabled={a.busy}>
          {t("bureau.dest.saveDetails")}
        </Button>
        {a.view}
      </div>
    </form>
  );
}

function GeoTab({ d, onSaved }: { d: StaffDestination; onSaved: (d: StaffDestination) => void }) {
  const { t } = useI18n();
  const [lat, setLat] = useState(d.working.lat?.toString() ?? "");
  const [lng, setLng] = useState(d.working.lng?.toString() ?? "");
  const [sens, setSens] = useState<string>(d.working.location_sensitivity);
  const a = useAction();
  return (
    <form
      className="grid max-w-2xl gap-4 sm:grid-cols-3"
      onSubmit={(e) => {
        e.preventDefault();
        void a.run(
          async () =>
            onSaved(await api<StaffDestination>(`/bureau/destinations/${d.id}/geo`, { method: "PUT", json: { lat: lat ? Number(lat) : null, lng: lng ? Number(lng) : null, sensitivity: sens } })),
          t("bureau.dest.saved"),
        );
      }}
    >
      <Input id="g-lat" type="number" step="any" min={-90} max={90} label={t("bureau.dest.lat")} value={lat} onChange={(e) => setLat(e.target.value)} />
      <Input id="g-lng" type="number" step="any" min={-180} max={180} label={t("bureau.dest.lng")} value={lng} onChange={(e) => setLng(e.target.value)} />
      <Select
        id="g-sens"
        label={t("bureau.dest.sensitivity")}
        value={sens}
        onChange={(e) => setSens(e.target.value)}
        options={(["public", "coarse", "hidden"] as const).map((s) => ({ value: s, label: t(`bureau.dest.sens.${s}`) }))}
      />
      <div className="sm:col-span-3">
        <Button type="submit">{t("bureau.dest.saveGeo")}</Button>
        {a.view}
      </div>
    </form>
  );
}

function SourcesTab({ d, onSaved }: { d: StaffDestination; onSaved: (d: StaffDestination) => void }) {
  const { t } = useI18n();
  const [rows, setRows] = useState(d.working.sources.map((s) => ({ title: s.title, author: s.author ?? "", publisher: s.publisher ?? "", year: s.year ?? "", url: s.url ?? "" })));
  const a = useAction();
  const blank = { title: "", author: "", publisher: "", year: "", url: "" };
  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        const sources = rows.filter((r) => r.title.trim()).map((r) => ({ title: r.title, author: r.author || null, publisher: r.publisher || null, year: r.year || null, url: r.url || null }));
        void a.run(async () => onSaved(await api<StaffDestination>(`/bureau/destinations/${d.id}`, { method: "PATCH", json: { sources } })), t("bureau.dest.saved"));
      }}
    >
      {rows.map((r, i) => (
        <fieldset key={i} className="grid gap-3 rounded-lg border border-line p-4 md:grid-cols-[2fr_1fr_1fr_80px_2fr_auto] md:items-end">
          <legend className="sr-only">{`${t("bureau.dest.addSource")} ${i + 1}`}</legend>
          <Input id={`s-title-${i}`} label={t("bureau.dest.sourceTitle")} value={r.title} onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, title: e.target.value } : x)))} required />
          <Input id={`s-author-${i}`} label={t("bureau.dest.sourceAuthor")} value={r.author} onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, author: e.target.value } : x)))} />
          <Input id={`s-pub-${i}`} label={t("bureau.dest.sourcePublisher")} value={r.publisher} onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, publisher: e.target.value } : x)))} />
          <Input id={`s-year-${i}`} label={t("bureau.dest.sourceYear")} value={r.year} onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, year: e.target.value } : x)))} />
          <Input id={`s-url-${i}`} type="url" label={t("bureau.dest.sourceUrl")} value={r.url} onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, url: e.target.value } : x)))} />
          <Button variant="ghost" size="sm" onClick={() => setRows(rows.filter((_, j) => j !== i))}>
            {t("bureau.dest.remove")}
          </Button>
        </fieldset>
      ))}
      <div className="flex gap-3">
        <Button variant="secondary" onClick={() => setRows([...rows, blank])}>
          {t("bureau.dest.addSource")}
        </Button>
        <Button type="submit">{t("bureau.dest.saveSources")}</Button>
      </div>
      {a.view}
    </form>
  );
}

function MediaTab({ d }: { d: StaffDestination }) {
  const { t } = useI18n();
  const [mediaId, setMediaId] = useState("");
  const [hero, setHero] = useState(false);
  const a = useAction();
  return (
    <form
      className="max-w-xl space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        void a.run(() => api(`/bureau/destinations/${d.id}/media`, { json: { media_id: mediaId, is_hero: hero } }), t("bureau.dest.saved"));
      }}
    >
      <p className="text-sm text-muted">{t("bureau.dest.attachMedia")}</p>
      <Input id="m-id" label={t("bureau.dest.mediaId")} value={mediaId} onChange={(e) => setMediaId(e.target.value.trim())} required pattern="[0-9a-f-]{36}" />
      <Checkbox id="m-hero" label={t("bureau.dest.hero")} checked={hero} onChange={(e) => setHero(e.target.checked)} />
      <Button type="submit">{t("bureau.dest.attach")}</Button>
      {a.view}
    </form>
  );
}

function RevisionsTab({ d, onChange }: { d: StaffDestination; onChange: () => void }) {
  const { t, locale } = useI18n();
  const { has } = useSession();
  const { data, error, reload } = useLoad<{ number: number; note: string; created_at: string }[]>(`/bureau/destinations/${d.id}/revisions`);
  const [diff, setDiff] = useState<string[] | null>(null);
  const a = useAction();
  if (error) return <LoadError error={error} />;
  if (!data) return <Loading label={t("common.loading")} />;
  if (data.length === 0) return <EmptyState title={t("common.empty")} />;
  return (
    <div className="space-y-6">
      <Table caption={t("bureau.dest.tabs.revisions")}>
        <thead>
          <tr>
            <th>#</th>
            <th>{t("bureau.dest.note")}</th>
            <th>{t("bureau.audit.when")}</th>
            <th>
              <span className="sr-only">{t("bureau.dest.compare")}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {data.map((r, i) => (
            <tr key={r.number}>
              <td>{r.number}</td>
              <td>{r.note || "—"}</td>
              <td>{formatDateTime(r.created_at, locale)}</td>
              <td className="space-x-3 whitespace-nowrap">
                {data[i + 1] && (
                  <button type="button" className="underline" onClick={() => api<{ diff: string[] }>(`/bureau/destinations/${d.id}/revisions/diff?a=${data[i + 1].number}&b=${r.number}`).then((x) => setDiff(x.diff))}>
                    {t("bureau.dest.compare")}
                  </button>
                )}
                {has("destinations.publish") && i > 0 && (
                  <button
                    type="button"
                    className="underline"
                    onClick={() =>
                      a
                        .run(() => api(`/bureau/destinations/${d.id}/rollback/${r.number}`, { method: "POST" }), t("bureau.dest.saved"))
                        .then(() => {
                          void reload();
                          onChange();
                        })
                    }
                  >
                    {t("bureau.dest.rollback")}
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </Table>
      {a.view}
      {diff && (
        <pre className="max-h-[480px] overflow-auto rounded-lg border border-line bg-surface p-4 text-xs" aria-label={t("bureau.dest.compare")}>
          {diff.map((line, i) => (
            <span key={i} className={line.startsWith("+") ? "block text-success" : line.startsWith("-") ? "block text-danger" : "block text-muted"}>
              {line}
            </span>
          ))}
        </pre>
      )}
    </div>
  );
}

/* ================================================================ translations & freshness */

export function TranslationQueue() {
  const { t, locale } = useI18n();
  const { data, error } = useLoad<{ destination_id: string; slug: string; missing: string[]; unreviewed: string[] }[]>("/bureau/translations/missing");
  return (
    <>
      <BureauTitle title={t("bureau.translations.title")} />
      <LoadError error={error} />
      {!data ? (
        !error && <Loading label={t("common.loading")} />
      ) : data.length === 0 ? (
        <EmptyState title={t("bureau.translations.none")} />
      ) : (
        <Table caption={t("bureau.translations.title")}>
          <thead>
            <tr>
              <th>{t("bureau.dest.slug")}</th>
              <th>{t("bureau.translations.missing")}</th>
              <th>{t("bureau.translations.unreviewed")}</th>
            </tr>
          </thead>
          <tbody>
            {data.map((r) => (
              <tr key={r.destination_id}>
                <td>
                  <Link className="underline" href={`/${locale}/bureau/destinations/${r.destination_id}`}>
                    {r.slug}
                  </Link>
                </td>
                <td>{r.missing.join(", ") || "—"}</td>
                <td>{r.unreviewed.join(", ") || "—"}</td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </>
  );
}

export function FreshnessReport() {
  const { t, locale } = useI18n();
  const { data, error } = useLoad<{ id: string; slug: string; reasons: string[] }[]>("/bureau/content/freshness");
  return (
    <>
      <BureauTitle title={t("bureau.freshness.title")} lead={t("bureau.freshness.lead")} />
      <LoadError error={error} />
      {!data ? (
        !error && <Loading label={t("common.loading")} />
      ) : data.length === 0 ? (
        <EmptyState title={t("bureau.freshness.none")} />
      ) : (
        <ul className="space-y-3">
          {data.map((r) => (
            <li key={r.id} className="flex flex-wrap items-center gap-3 rounded-lg border border-line bg-surface px-4 py-3">
              <Link className="font-mono text-sm underline" href={`/${locale}/bureau/destinations/${r.id}`}>
                {r.slug}
              </Link>
              {r.reasons.map((x) => (
                <Badge key={x} tone="caution">
                  {x.replace(/_/g, " ")}
                </Badge>
              ))}
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

/* ================================================================ advisories */

interface StaffAdvisory {
  id: string;
  level: string;
  title: string;
  status: string;
  region_wide: boolean;
  issuing_authority: string;
  effective_from: string;
}

export function AdvisoriesAdmin() {
  const { t, locale } = useI18n();
  const { data, error, reload } = useLoad<StaffAdvisory[]>("/bureau/advisories");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [level, setLevel] = useState("info");
  const [regionWide, setRegionWide] = useState(false);
  const [destIds, setDestIds] = useState("");
  const [authority, setAuthority] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const a = useAction();
  const levels = ["info", "caution", "avoid_nonessential", "travel_not_advised"] as const;
  return (
    <>
      <BureauTitle title={t("bureau.advisories.title")} />
      <Card className="mb-8 max-w-3xl">
        <h2 className="text-2xl">{t("bureau.advisories.new")}</h2>
        <form
          className="mt-4 grid gap-4 sm:grid-cols-2"
          onSubmit={async (e) => {
            e.preventDefault();
            const ok = await a.run(
              () =>
                api("/bureau/advisories", {
                  json: {
                    title_i18n: { en: title },
                    body_i18n: { en: body },
                    level,
                    region_wide: regionWide,
                    destination_ids: destIds.split(",").map((x) => x.trim()).filter(Boolean),
                    issuing_authority: authority,
                    source_url: sourceUrl || null,
                  },
                }),
              t("bureau.dest.saved"),
            );
            if (ok) {
              setTitle("");
              setBody("");
              await reload();
            }
          }}
        >
          <Input id="a-title" label={t("bureau.advisories.titleEn")} value={title} onChange={(e) => setTitle(e.target.value)} required className="sm:col-span-2" />
          <div className="sm:col-span-2">
            <Textarea id="a-body" label={t("bureau.advisories.bodyEn")} value={body} onChange={(e) => setBody(e.target.value)} required />
          </div>
          <Select id="a-level" label={t("bureau.advisories.level")} value={level} onChange={(e) => setLevel(e.target.value)} options={levels.map((l) => ({ value: l, label: t(`advisory.level.${l}`) }))} />
          <Input id="a-auth" label={t("bureau.advisories.authority")} value={authority} onChange={(e) => setAuthority(e.target.value)} required minLength={2} />
          <Input id="a-dest" label={t("bureau.advisories.destinations")} value={destIds} onChange={(e) => setDestIds(e.target.value)} disabled={regionWide} />
          <Input id="a-src" type="url" label={t("bureau.advisories.sourceUrl")} value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} />
          <Checkbox id="a-region" label={t("bureau.advisories.regionWide")} checked={regionWide} onChange={(e) => setRegionWide(e.target.checked)} />
          <div className="sm:col-span-2">
            <Button type="submit" disabled={a.busy}>
              {t("bureau.advisories.create")}
            </Button>
          </div>
        </form>
        {a.view}
      </Card>
      <LoadError error={error} />
      {data && (
        <Table caption={t("bureau.advisories.title")}>
          <thead>
            <tr>
              <th>{t("bureau.advisories.titleEn")}</th>
              <th>{t("bureau.advisories.level")}</th>
              <th>{t("bureau.dest.status")}</th>
              <th>{t("bureau.audit.when")}</th>
              <th>
                <span className="sr-only">{t("bureau.advisories.publish")}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {data.map((x) => (
              <tr key={x.id}>
                <td>{x.title}</td>
                <td>{t(`advisory.level.${x.level as (typeof levels)[number]}`)}</td>
                <td>
                  <Badge tone={x.status === "published" ? "success" : "neutral"}>{x.status}</Badge>
                </td>
                <td>{formatDate(x.effective_from, locale)}</td>
                <td className="space-x-3 whitespace-nowrap">
                  {x.status !== "published" && (
                    <button type="button" className="underline" onClick={() => a.run(() => api(`/bureau/advisories/${x.id}/publish`, { method: "POST" }), t("bureau.dest.saved")).then(reload)}>
                      {t("bureau.advisories.publish")}
                    </button>
                  )}
                  {x.status === "published" && (
                    <button type="button" className="underline" onClick={() => a.run(() => api(`/bureau/advisories/${x.id}/withdraw`, { method: "POST" }), t("bureau.dest.saved")).then(reload)}>
                      {t("bureau.advisories.withdraw")}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </>
  );
}

/* ================================================================ events */

export function EventsAdmin() {
  const { t } = useI18n();
  const [slug, setSlug] = useState("");
  const [title, setTitle] = useState("");
  const [desc, setDesc] = useState("");
  const [starts, setStarts] = useState("");
  const [ends, setEnds] = useState("");
  const [ethMonth, setEthMonth] = useState("");
  const [ethDay, setEthDay] = useState("");
  const [publish, setPublish] = useState(false);
  const [verified, setVerified] = useState(false);
  const a = useAction();
  return (
    <>
      <BureauTitle title={t("bureau.events.title")} />
      <Card className="max-w-3xl">
        <h2 className="text-2xl">{t("bureau.events.new")}</h2>
        <form
          className="mt-4 grid gap-4 sm:grid-cols-2"
          onSubmit={async (e) => {
            e.preventDefault();
            const ok = await a.run(
              () =>
                api("/bureau/events", {
                  json: {
                    slug,
                    title_i18n: { en: title },
                    description_i18n: desc ? { en: desc } : {},
                    starts_on: starts || null,
                    ends_on: ends || null,
                    ethiopian_month: ethMonth ? Number(ethMonth) : null,
                    ethiopian_day: ethDay ? Number(ethDay) : null,
                    publish,
                    verified,
                  },
                }),
              t("bureau.events.created"),
            );
            if (ok) {
              setSlug("");
              setTitle("");
              setDesc("");
            }
          }}
        >
          <Input id="e-slug" label={t("bureau.dest.slug")} value={slug} onChange={(e) => setSlug(e.target.value.toLowerCase())} pattern="[a-z0-9][a-z0-9-]{1,98}" required />
          <Input id="e-title" label={t("bureau.events.titleEn")} value={title} onChange={(e) => setTitle(e.target.value)} required />
          <div className="sm:col-span-2">
            <Textarea id="e-desc" label={t("bureau.events.descEn")} value={desc} onChange={(e) => setDesc(e.target.value)} />
          </div>
          <Input id="e-start" type="date" label={t("bureau.events.starts")} value={starts} onChange={(e) => setStarts(e.target.value)} />
          <Input id="e-end" type="date" label={t("bureau.events.ends")} value={ends} onChange={(e) => setEnds(e.target.value)} />
          <Input id="e-em" type="number" min={1} max={13} label={t("bureau.events.ethMonth")} value={ethMonth} onChange={(e) => setEthMonth(e.target.value)} />
          <Input id="e-ed" type="number" min={1} max={30} label={t("bureau.events.ethDay")} value={ethDay} onChange={(e) => setEthDay(e.target.value)} />
          <Checkbox id="e-pub" label={t("bureau.events.publish")} checked={publish} onChange={(e) => setPublish(e.target.checked)} />
          <Checkbox id="e-ver" label={t("bureau.events.verified")} checked={verified} onChange={(e) => setVerified(e.target.checked)} />
          <div className="sm:col-span-2">
            <Button type="submit" disabled={a.busy}>
              {t("bureau.events.create")}
            </Button>
          </div>
        </form>
        {a.view}
      </Card>
    </>
  );
}

/* ================================================================ media review */

interface StaffMedia {
  id: string;
  status: string;
  scan_status: string;
  purpose: string;
  had_gps_metadata: boolean;
  license: string | null;
  credit: string | null;
  alt_text_i18n: Record<string, string>;
  is_illustrative: boolean;
  is_reconstruction: boolean;
  is_ai_generated: boolean;
  custodial_approval_ref: string | null;
  signed_preview: string;
}

export function MediaReview() {
  const { t } = useI18n();
  const [status, setStatus] = useState("clean");
  const { data, error, reload } = useLoad<StaffMedia[]>(`/bureau/media${status ? `?status=${status}` : ""}`);
  return (
    <>
      <BureauTitle
        title={t("bureau.media.title")}
        actions={
          <Select
            id="m-status"
            label={t("bureau.dest.status")}
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            options={["clean", "quarantine", "approved", "rejected", ""].map((s) => ({ value: s, label: s || "all" }))}
          />
        }
      />
      <LoadError error={error} />
      {!data ? (
        !error && <Loading label={t("common.loading")} />
      ) : data.length === 0 ? (
        <EmptyState title={t("bureau.media.none")} />
      ) : (
        <div className="grid gap-6 xl:grid-cols-2">
          {data.map((m) => (
            <MediaCard key={m.id} m={m} onChange={reload} />
          ))}
        </div>
      )}
    </>
  );
}

function MediaCard({ m, onChange }: { m: StaffMedia; onChange: () => void }) {
  const { t } = useI18n();
  const [license, setLicense] = useState(m.license ?? "");
  const [credit, setCredit] = useState(m.credit ?? "");
  const [alt, setAlt] = useState(m.alt_text_i18n?.en ?? "");
  const [ill, setIll] = useState(m.is_illustrative);
  const [rec, setRec] = useState(m.is_reconstruction);
  const [ai, setAi] = useState(m.is_ai_generated);
  const [custodial, setCustodial] = useState(m.custodial_approval_ref ?? "");
  const a = useAction();
  return (
    <Card className="grid gap-4 sm:grid-cols-[180px_1fr]">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={m.signed_preview} alt={alt || "preview"} className="w-full rounded-lg border border-line" />
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          void a.run(
            () =>
              api(`/bureau/media/${m.id}/rights`, {
                method: "PUT",
                json: { license, credit, alt_text_i18n: alt ? { en: alt } : {}, is_illustrative: ill, is_reconstruction: rec, is_ai_generated: ai, custodial_approval_ref: custodial || null },
              }),
            t("bureau.dest.saved"),
          );
        }}
      >
        <div className="flex flex-wrap gap-2 text-xs">
          <Badge>{m.status}</Badge>
          <Badge tone={m.scan_status === "clean" ? "success" : "caution"}>{t("bureau.media.scan", { status: m.scan_status })}</Badge>
          {m.had_gps_metadata && <Badge tone="info">{t("bureau.media.gps")}</Badge>}
          <span className="font-mono text-muted">{m.id}</span>
        </div>
        <Input id={`lic-${m.id}`} label={t("bureau.media.license")} value={license} onChange={(e) => setLicense(e.target.value)} required />
        <Input id={`cr-${m.id}`} label={t("bureau.media.credit")} value={credit} onChange={(e) => setCredit(e.target.value)} required />
        <Input id={`alt-${m.id}`} label={t("bureau.media.alt")} value={alt} onChange={(e) => setAlt(e.target.value)} />
        <Input id={`cu-${m.id}`} label={t("bureau.media.custodial")} value={custodial} onChange={(e) => setCustodial(e.target.value)} />
        <div className="flex flex-wrap gap-4">
          <Checkbox id={`ill-${m.id}`} label={t("bureau.media.illustrative")} checked={ill} onChange={(e) => setIll(e.target.checked)} />
          <Checkbox id={`rec-${m.id}`} label={t("bureau.media.reconstruction")} checked={rec} onChange={(e) => setRec(e.target.checked)} />
          <Checkbox id={`ai-${m.id}`} label={t("bureau.media.aiGenerated")} checked={ai} onChange={(e) => setAi(e.target.checked)} />
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="submit" size="sm" variant="secondary">
            {t("bureau.media.saveRights")}
          </Button>
          <Button size="sm" onClick={() => a.run(() => api(`/bureau/media/${m.id}/approve`, { method: "POST" }), t("bureau.dest.saved")).then(onChange)}>
            {t("bureau.media.approve")}
          </Button>
          <Button size="sm" variant="danger" onClick={() => a.run(() => api(`/bureau/media/${m.id}/reject`, { method: "POST" }), t("bureau.dest.saved")).then(onChange)}>
            {t("bureau.media.reject")}
          </Button>
        </div>
        {a.view}
      </form>
    </Card>
  );
}
