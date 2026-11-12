"use client";

import { useState } from "react";
import { Alert, Badge, Button, Card, Checkbox, EmptyState, Input, Loading, Select, Table, Textarea } from "@/components/ui";
import { useI18n, useSession } from "@/components/site/providers";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { BureauTitle } from "./shell";
import { LoadError, useAction, useLoad } from "./hooks";

/* ================================================================ moderation */

interface ModItem {
  kind: string;
  id: string;
  title?: string;
  body: string;
  author?: { display_name: string; handle?: string };
  reports?: { reason: string; detail?: string }[];
  ai_flags?: { label: string; score?: number }[] | string[];
  created_at: string;
}

export function ModerationQueue() {
  const { t, locale } = useI18n();
  const { data, error, reload } = useLoad<{ items: ModItem[] } | ModItem[]>("/bureau/moderation/queue");
  const items = data ? (Array.isArray(data) ? data : data.items) : null;
  return (
    <>
      <BureauTitle title={t("bureau.moderation.title")} />
      <LoadError error={error} />
      {!items ? (
        !error && <Loading label={t("common.loading")} />
      ) : items.length === 0 ? (
        <EmptyState title={t("bureau.moderation.none")} />
      ) : (
        <ul className="space-y-5">
          {items.map((m) => (
            <ModCard key={`${m.kind}-${m.id}`} m={m} locale={locale} onDone={reload} />
          ))}
        </ul>
      )}
    </>
  );
}

function ModCard({ m, locale, onDone }: { m: ModItem; locale: string; onDone: () => void }) {
  const { t } = useI18n();
  const [note, setNote] = useState("");
  const a = useAction();
  const decide = (decision: string) => a.run(() => api(`/bureau/moderation/${m.kind}/${m.id}/decision`, { json: { decision, note } }), t("bureau.dest.saved")).then((ok) => ok && onDone());
  return (
    <li className="rounded-[var(--radius)] border border-line bg-surface p-6">
      <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
        <Badge>{m.kind}</Badge>
        {m.author && <span>{m.author.display_name}</span>}
        <span>{formatDateTime(m.created_at, locale)}</span>
      </div>
      {m.title && <h2 className="mt-2 text-2xl">{m.title}</h2>}
      <p className="mt-2 whitespace-pre-line">{m.body}</p>
      {m.reports && m.reports.length > 0 && (
        <div className="mt-3">
          <p className="text-sm font-semibold">{t("bureau.moderation.reports")}</p>
          <ul className="list-disc pl-5 text-sm">
            {m.reports.map((r, i) => (
              <li key={i}>
                {r.reason}
                {r.detail ? ` — ${r.detail}` : ""}
              </li>
            ))}
          </ul>
        </div>
      )}
      {m.ai_flags && m.ai_flags.length > 0 && (
        <div className="mt-3">
          <p className="text-sm font-semibold">{t("bureau.moderation.flags")}</p>
          <div className="mt-1 flex flex-wrap gap-2">
            {m.ai_flags.map((f, i) => (
              <Badge key={i} tone="caution">
                {typeof f === "string" ? f : `${f.label}${f.score !== undefined ? ` ${f.score.toFixed(2)}` : ""}`}
              </Badge>
            ))}
          </div>
        </div>
      )}
      <div className="mt-4 grid gap-3 md:grid-cols-[1fr_auto] md:items-end">
        <Input id={`note-${m.id}`} label={t("bureau.moderation.note")} value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} />
        <div className="flex flex-wrap gap-2">
          <Button size="sm" onClick={() => decide("approve")}>
            {t("bureau.moderation.approve")}
          </Button>
          <Button size="sm" variant="secondary" onClick={() => decide("reject")}>
            {t("bureau.moderation.reject")}
          </Button>
          <Button size="sm" variant="danger" onClick={() => decide("remove")}>
            {t("bureau.moderation.remove")}
          </Button>
        </div>
      </div>
      {a.view}
    </li>
  );
}

/* ================================================================ knowledge vault */

interface KDoc {
  id: string;
  title: string;
  author?: string | null;
  publisher?: string | null;
  status: string;
  language?: string | null;
  access_classification?: string;
  created_at?: string;
}

export function KnowledgeVault() {
  const { t, locale } = useI18n();
  const { has } = useSession();
  const { data, error, reload } = useLoad<{ items: KDoc[] } | KDoc[]>("/bureau/knowledge/documents");
  const items = data ? (Array.isArray(data) ? data : data.items) : null;
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [author, setAuthor] = useState("");
  const [publisher, setPublisher] = useState("");
  const [published, setPublished] = useState("");
  const [language, setLanguage] = useState("en");
  const [rights, setRights] = useState("");
  const [classification, setClassification] = useState("public");
  const a = useAction();
  return (
    <>
      <BureauTitle title={t("bureau.knowledge.title")} lead={t("bureau.knowledge.lead")} />
      {has("knowledge.upload") && (
        <Card className="mb-8 max-w-3xl">
          <h2 className="text-2xl">{t("bureau.knowledge.upload")}</h2>
          <form
            className="mt-4 grid gap-4 sm:grid-cols-2"
            onSubmit={async (e) => {
              e.preventDefault();
              if (!file) return;
              const fd = new FormData();
              fd.append("file", file);
              fd.append("title", title);
              fd.append("author", author);
              fd.append("publisher", publisher);
              if (published) fd.append("published_on", published);
              fd.append("original_language", language);
              fd.append("rights_status", rights);
              fd.append("access_classification", classification);
              const ok = await a.run(() => api("/bureau/knowledge/documents", { method: "POST", body: fd }), t("bureau.dest.saved"));
              if (ok) await reload();
            }}
          >
            <div className="flex flex-col gap-1.5 sm:col-span-2">
              <label htmlFor="k-file" className="text-sm font-medium">
                {t("bureau.knowledge.file")}
              </label>
              <input id="k-file" type="file" accept=".pdf,.txt,.md,application/pdf,text/plain,text/markdown" onChange={(e) => setFile(e.target.files?.[0] ?? null)} required className="text-sm" />
            </div>
            <Input id="k-title" label={t("bureau.knowledge.docTitle")} value={title} onChange={(e) => setTitle(e.target.value)} required />
            <Input id="k-author" label={t("bureau.knowledge.author")} value={author} onChange={(e) => setAuthor(e.target.value)} />
            <Input id="k-pub" label={t("bureau.knowledge.publisher")} value={publisher} onChange={(e) => setPublisher(e.target.value)} />
            <Input id="k-date" type="date" label={t("bureau.knowledge.published")} value={published} onChange={(e) => setPublished(e.target.value)} />
            <Select id="k-lang" label={t("bureau.knowledge.language")} value={language} onChange={(e) => setLanguage(e.target.value)} options={["en", "ti", "am", "gez", "other"].map((x) => ({ value: x, label: x }))} />
            <Input id="k-rights" label={t("bureau.knowledge.rights")} value={rights} onChange={(e) => setRights(e.target.value)} required />
            <Select
              id="k-class"
              label={t("bureau.knowledge.classification")}
              value={classification}
              onChange={(e) => setClassification(e.target.value)}
              options={["public", "internal", "restricted", "sacred"].map((x) => ({ value: x, label: x }))}
            />
            <div className="sm:col-span-2">
              <Button type="submit" disabled={a.busy || !file}>
                {t("bureau.knowledge.uploadBtn")}
              </Button>
            </div>
          </form>
          {a.view}
        </Card>
      )}
      <LoadError error={error} />
      {items &&
        (items.length === 0 ? (
          <EmptyState title={t("bureau.knowledge.none")} />
        ) : (
          <Table caption={t("bureau.knowledge.title")}>
            <thead>
              <tr>
                <th>{t("bureau.knowledge.docTitle")}</th>
                <th>{t("bureau.knowledge.status")}</th>
                <th>{t("bureau.knowledge.classification")}</th>
                <th>{t("bureau.audit.when")}</th>
                <th>
                  <span className="sr-only">{t("bureau.knowledge.review")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((d) => (
                <tr key={d.id}>
                  <td>
                    {d.title}
                    <span className="block text-xs text-muted">{[d.author, d.publisher, d.language].filter(Boolean).join(" · ")}</span>
                  </td>
                  <td>
                    <Badge>{d.status}</Badge>
                  </td>
                  <td>{d.access_classification ?? "—"}</td>
                  <td>{d.created_at ? formatDateTime(d.created_at, locale) : "—"}</td>
                  <td className="space-x-2 whitespace-nowrap">
                    {has("knowledge.review") && (
                      <button type="button" className="underline" onClick={() => a.run(() => api(`/bureau/knowledge/documents/${d.id}/review`, { method: "POST" }), t("bureau.dest.saved")).then(reload)}>
                        {t("bureau.knowledge.review")}
                      </button>
                    )}
                    {has("knowledge.publish") && (
                      <>
                        <button type="button" className="underline" onClick={() => a.run(() => api(`/bureau/knowledge/documents/${d.id}/approve`, { method: "POST" }), t("bureau.dest.saved")).then(reload)}>
                          {t("bureau.knowledge.approve")}
                        </button>
                        <button type="button" className="underline" onClick={() => a.run(() => api(`/bureau/knowledge/documents/${d.id}/publish`, { method: "POST" }), t("bureau.dest.saved")).then(reload)}>
                          {t("bureau.knowledge.publish")}
                        </button>
                      </>
                    )}
                    {(has("knowledge.review") || has("knowledge.publish")) && (
                      <button type="button" className="text-danger underline" onClick={() => a.run(() => api(`/bureau/knowledge/documents/${d.id}/reject`, { method: "POST" }), t("bureau.dest.saved")).then(reload)}>
                        {t("bureau.knowledge.reject")}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        ))}
    </>
  );
}

/* ================================================================ AI policy */

const ALL_MODES = ["fully_local", "local_first_cloud_fallback", "cloud_assisted", "retrieval_only", "deterministic", "offline"] as const;

export function AiPolicy() {
  const { t } = useI18n();
  const policy = useLoad<{ mode: string; permitted_modes: string[] }>("/bureau/ai/policy");
  const models = useLoad<{ items: Record<string, unknown>[] } | Record<string, unknown>[]>("/bureau/ai/models");
  const modelItems = models.data ? (Array.isArray(models.data) ? models.data : models.data.items) : null;
  const [mode, setMode] = useState<string | null>(null);
  const [permitted, setPermitted] = useState<string[] | null>(null);
  const a = useAction();
  const curMode = mode ?? policy.data?.mode ?? "fully_local";
  const curPermitted = permitted ?? policy.data?.permitted_modes ?? [];
  return (
    <>
      <BureauTitle title={t("bureau.ai.title")} />
      <LoadError error={policy.error} />
      {policy.data && (
        <Card className="max-w-2xl space-y-4">
          <fieldset>
            <legend className="text-sm font-semibold">{t("bureau.ai.permitted")}</legend>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {ALL_MODES.map((m) => (
                <Checkbox
                  key={m}
                  id={`pm-${m}`}
                  label={t(`bureau.ai.modes.${m}`)}
                  checked={curPermitted.includes(m)}
                  onChange={(e) => setPermitted(e.target.checked ? [...curPermitted, m] : curPermitted.filter((x) => x !== m))}
                />
              ))}
            </div>
          </fieldset>
          <Select id="mode" label={t("bureau.ai.mode")} value={curMode} onChange={(e) => setMode(e.target.value)} options={curPermitted.map((m) => ({ value: m, label: t(`bureau.ai.modes.${m as (typeof ALL_MODES)[number]}`) }))} />
          <Button onClick={() => a.run(() => api("/bureau/ai/policy", { method: "PUT", json: { mode: curMode, permitted_modes: curPermitted } }), t("bureau.dest.saved"))}>{t("bureau.ai.save")}</Button>
          {a.view}
        </Card>
      )}
      <section className="mt-10">
        <h2 className="text-2xl">{t("bureau.ai.models")}</h2>
        <LoadError error={models.error} />
        {modelItems &&
          (modelItems.length === 0 ? (
            <p className="mt-2 text-muted">{t("bureau.ai.noModels")}</p>
          ) : (
            <Table caption={t("bureau.ai.models")} className="mt-4">
              <thead>
                <tr>
                  {Object.keys(modelItems[0]).slice(0, 7).map((k) => (
                    <th key={k}>{k}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {modelItems.map((m, i) => (
                  <tr key={i}>
                    {Object.keys(modelItems[0]).slice(0, 7).map((k) => (
                      <td key={k}>{typeof m[k] === "object" ? JSON.stringify(m[k]) : String(m[k] ?? "—")}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </Table>
          ))}
      </section>
    </>
  );
}

/* ================================================================ analytics */

function defaultRange() {
  const now = new Date();
  const monthAgo = new Date(now.getTime() - 30 * 86400000);
  return { from: monthAgo.toISOString().slice(0, 10), to: now.toISOString().slice(0, 10) };
}

export function Analytics() {
  const { t } = useI18n();
  const [initial] = useState(defaultRange);
  const [from, setFrom] = useState(initial.from);
  const [to, setTo] = useState(initial.to);
  const [query, setQuery] = useState(`from=${initial.from}&to=${initial.to}`);
  const { data, error } = useLoad<Record<string, unknown> & { notice?: string; kind?: string }>(`/bureau/analytics/summary?${query}`);
  return (
    <>
      <BureauTitle title={t("bureau.analytics.title")} lead={t("bureau.analytics.lead")} />
      <form
        className="mb-8 flex flex-wrap items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          setQuery(`from=${from}&to=${to}`);
        }}
      >
        <Input id="an-from" type="date" label={t("bureau.analytics.from")} value={from} onChange={(e) => setFrom(e.target.value)} />
        <Input id="an-to" type="date" label={t("bureau.analytics.to")} value={to} onChange={(e) => setTo(e.target.value)} />
        <Button type="submit">{t("bureau.analytics.load")}</Button>
        {(["csv", "xlsx", "pdf"] as const).map((f) => (
          <a key={f} className="inline-flex min-h-[44px] items-center rounded-full border border-line px-4 text-sm" href={`/api/bureau/analytics/export?format=${f}&${query}`}>
            {t("bureau.analytics.export", { format: f.toUpperCase() })}
          </a>
        ))}
      </form>
      <LoadError error={error} />
      {data && (
        <div className="space-y-6">
          {data.notice && <Alert tone="info">{data.notice}</Alert>}
          <MetricTables data={data} />
        </div>
      )}
    </>
  );
}

/** Generic, honest rendering of whatever series the API returns (no invented numbers). */
function MetricTables({ data }: { data: Record<string, unknown> }) {
  const entries = Object.entries(data).filter(([k]) => !["notice", "kind", "generated_at", "filters"].includes(k));
  return (
    <div className="grid gap-6 xl:grid-cols-2">
      {entries.map(([k, v]) => {
        if (Array.isArray(v) && v.length > 0 && typeof v[0] === "object") {
          const cols = Object.keys(v[0] as object);
          const max = Math.max(...v.map((row) => Number((row as Record<string, unknown>)[cols[cols.length - 1]]) || 0), 1);
          return (
            <Card key={k}>
              <h2 className="text-xl">{k.replace(/_/g, " ")}</h2>
              <Table caption={k} className="mt-3">
                <thead>
                  <tr>
                    {cols.map((c) => (
                      <th key={c}>{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {v.map((row, i) => (
                    <tr key={i}>
                      {cols.map((c, j) => {
                        const val = (row as Record<string, unknown>)[c];
                        return (
                          <td key={c}>
                            {String(val ?? "—")}
                            {j === cols.length - 1 && typeof val === "number" && (
                              <span aria-hidden="true" className="ml-2 inline-block h-2 rounded bg-sandstone align-middle" style={{ width: `${Math.max(2, (val / max) * 120)}px` }} />
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </Table>
            </Card>
          );
        }
        if (typeof v === "number" || typeof v === "string") {
          return (
            <Card key={k}>
              <p className="text-sm text-muted">{k.replace(/_/g, " ")}</p>
              <p className="font-display text-4xl">{String(v)}</p>
            </Card>
          );
        }
        if (v && typeof v === "object" && !Array.isArray(v)) {
          return (
            <Card key={k}>
              <h2 className="text-xl">{k.replace(/_/g, " ")}</h2>
              <dl className="mt-3 grid grid-cols-2 gap-2 text-sm">
                {Object.entries(v as Record<string, unknown>).map(([a, b]) => (
                  <div key={a}>
                    <dt className="text-muted">{a}</dt>
                    <dd className="font-medium">{typeof b === "object" ? JSON.stringify(b) : String(b)}</dd>
                  </div>
                ))}
              </dl>
            </Card>
          );
        }
        return null;
      })}
    </div>
  );
}

/* ================================================================ assistant */

export function BureauAssistant() {
  const { t } = useI18n();
  const [q, setQ] = useState("");
  const [answer, setAnswer] = useState<{ answer?: string; draft?: string; findings?: unknown; notice?: string } | null>(null);
  const a = useAction();
  return (
    <>
      <BureauTitle title={t("bureau.assistant.title")} lead={t("bureau.assistant.lead")} />
      <form
        className="max-w-3xl space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          void a.run(async () => setAnswer(await api("/bureau/assistant/ask", { json: { question: q } })), "✓");
        }}
      >
        <Textarea id="as-q" label={t("bureau.assistant.title")} placeholder={t("bureau.assistant.placeholder")} value={q} onChange={(e) => setQ(e.target.value)} required maxLength={2000} />
        <Button type="submit" disabled={a.busy}>
          {a.busy ? t("guide.asking") : t("bureau.assistant.ask")}
        </Button>
      </form>
      {a.view}
      {answer && (
        <Card className="mt-6 max-w-3xl space-y-3">
          {answer.notice && <Alert tone="info">{answer.notice}</Alert>}
          <p className="whitespace-pre-line">{answer.answer ?? answer.draft}</p>
          {answer.findings !== undefined && <pre className="overflow-auto rounded bg-surface-2 p-3 text-xs">{JSON.stringify(answer.findings, null, 2)}</pre>}
        </Card>
      )}
    </>
  );
}

/* ================================================================ users & roles */

interface StaffUser {
  id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  mfa_enabled: boolean;
  roles: string[];
}

export function UsersAndRoles() {
  const { t } = useI18n();
  const { has } = useSession();
  const users = useLoad<StaffUser[]>(has("users.manage") ? "/bureau/users" : null);
  const roles = useLoad<{ roles: { key: string; name: string; is_system: boolean; permissions: string[] }[]; permissions: { key: string; description: string }[] }>(has("roles.manage") ? "/bureau/roles" : null);
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [inviteRoles, setInviteRoles] = useState<string[]>([]);
  const [roleKey, setRoleKey] = useState("");
  const [roleName, setRoleName] = useState("");
  const [rolePerms, setRolePerms] = useState<string[]>([]);
  const a = useAction();
  const roleKeys = roles.data?.roles.map((r) => r.key) ?? [];
  return (
    <>
      <BureauTitle title={t("bureau.users.title")} />
      {has("users.manage") && (
        <>
          <Card className="mb-8 max-w-3xl">
            <h2 className="text-2xl">{t("bureau.users.invite")}</h2>
            <form
              className="mt-4 grid gap-4 sm:grid-cols-2"
              onSubmit={async (e) => {
                e.preventDefault();
                const ok = await a.run(() => api("/bureau/users", { json: { email, display_name: name, roles: inviteRoles } }), t("bureau.users.invited"));
                if (ok) {
                  setEmail("");
                  setName("");
                  setInviteRoles([]);
                  await users.reload();
                }
              }}
            >
              <Input id="u-email" type="email" label={t("bureau.users.email")} value={email} onChange={(e) => setEmail(e.target.value)} required />
              <Input id="u-name" label={t("bureau.users.name")} value={name} onChange={(e) => setName(e.target.value)} required minLength={2} />
              <RolePicker id="u-roles" all={roleKeys} value={inviteRoles} onChange={setInviteRoles} />
              <div className="sm:col-span-2">
                <Button type="submit" disabled={a.busy}>
                  {t("bureau.users.inviteBtn")}
                </Button>
              </div>
            </form>
          </Card>
          <LoadError error={users.error} />
          {users.data && (
            <Table caption={t("bureau.users.title")}>
              <thead>
                <tr>
                  <th>{t("bureau.users.email")}</th>
                  <th>{t("bureau.users.name")}</th>
                  <th>{t("bureau.users.mfa")}</th>
                  <th>{t("bureau.users.roles")}</th>
                </tr>
              </thead>
              <tbody>
                {users.data.map((u) => (
                  <UserRow key={u.id} u={u} allRoles={roleKeys} onSaved={users.reload} />
                ))}
              </tbody>
            </Table>
          )}
        </>
      )}
      {a.view}
      {has("roles.manage") && roles.data && (
        <section className="mt-12">
          <h2 className="text-3xl">{t("bureau.users.rolesTitle")}</h2>
          <Card className="mt-4 max-w-3xl">
            <h3 className="text-xl">{t("bureau.users.newRole")}</h3>
            <form
              className="mt-3 space-y-4"
              onSubmit={async (e) => {
                e.preventDefault();
                const ok = await a.run(() => api("/bureau/roles", { json: { key: roleKey, name: roleName, permissions: rolePerms } }), t("bureau.dest.saved"));
                if (ok) {
                  setRoleKey("");
                  setRoleName("");
                  setRolePerms([]);
                  await roles.reload();
                }
              }}
            >
              <div className="grid gap-4 sm:grid-cols-2">
                <Input id="r-key" label={t("bureau.users.key")} value={roleKey} onChange={(e) => setRoleKey(e.target.value)} pattern="[a-z][a-z0-9_]{2,59}" required />
                <Input id="r-name" label={t("bureau.users.name")} value={roleName} onChange={(e) => setRoleName(e.target.value)} required />
              </div>
              <fieldset>
                <legend className="text-sm font-semibold">{t("bureau.users.permissions")}</legend>
                <div className="mt-2 grid max-h-64 gap-2 overflow-y-auto sm:grid-cols-2">
                  {roles.data.permissions.map((p) => (
                    <Checkbox
                      key={p.key}
                      id={`rp-${p.key}`}
                      label={
                        <span>
                          <span className="font-mono text-xs">{p.key}</span>
                          <span className="block text-xs text-muted">{p.description}</span>
                        </span>
                      }
                      checked={rolePerms.includes(p.key)}
                      onChange={(e) => setRolePerms(e.target.checked ? [...rolePerms, p.key] : rolePerms.filter((x) => x !== p.key))}
                    />
                  ))}
                </div>
              </fieldset>
              <Button type="submit">{t("bureau.users.createRole")}</Button>
            </form>
          </Card>
          <ul className="mt-6 grid gap-3 lg:grid-cols-2">
            {roles.data.roles.map((r) => (
              <li key={r.key} className="rounded-lg border border-line bg-surface p-4">
                <p className="font-medium">
                  {r.name} <span className="font-mono text-xs text-muted">{r.key}</span>
                </p>
                <p className="mt-1 text-xs text-muted">{r.permissions.join(", ")}</p>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}

function RolePicker({ id, all, value, onChange }: { id: string; all: string[]; value: string[]; onChange: (v: string[]) => void }) {
  const { t } = useI18n();
  if (all.length === 0) {
    return <Input id={id} label={t("bureau.users.roles")} value={value.join(", ")} onChange={(e) => onChange(e.target.value.split(",").map((x) => x.trim()).filter(Boolean))} />;
  }
  return (
    <fieldset className="sm:col-span-2">
      <legend className="text-sm font-semibold">{t("bureau.users.roles")}</legend>
      <div className="mt-2 flex flex-wrap gap-3">
        {all.map((r) => (
          <Checkbox key={r} id={`${id}-${r}`} label={r} checked={value.includes(r)} onChange={(e) => onChange(e.target.checked ? [...value, r] : value.filter((x) => x !== r))} />
        ))}
      </div>
    </fieldset>
  );
}

function UserRow({ u, allRoles, onSaved }: { u: StaffUser; allRoles: string[]; onSaved: () => void }) {
  const { t } = useI18n();
  const [roles, setRoles] = useState(u.roles.join(", "));
  const a = useAction();
  return (
    <tr>
      <td>{u.email}</td>
      <td>{u.display_name}</td>
      <td>{u.mfa_enabled ? "✓" : "—"}</td>
      <td>
        <form
          className="flex flex-wrap items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            void a
              .run(() => api(`/bureau/users/${u.id}/roles`, { method: "PUT", json: { roles: roles.split(",").map((x) => x.trim()).filter(Boolean) } }), t("bureau.dest.saved"))
              .then((ok) => ok && onSaved());
          }}
        >
          <label htmlFor={`roles-${u.id}`} className="sr-only">
            {t("bureau.users.roles")}
          </label>
          <input id={`roles-${u.id}`} list="role-keys" value={roles} onChange={(e) => setRoles(e.target.value)} className="min-h-[36px] w-64 rounded border border-line bg-bg px-2 text-sm" />
          <datalist id="role-keys">
            {allRoles.map((r) => (
              <option key={r} value={r} />
            ))}
          </datalist>
          <Button type="submit" size="sm" variant="secondary">
            {t("bureau.users.saveRoles")}
          </Button>
        </form>
        {a.view}
      </td>
    </tr>
  );
}

/* ================================================================ audit */

interface AuditItem {
  seq: number;
  occurred_at: string;
  actor: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  outcome: string;
}

export function AuditLog() {
  const { t, locale } = useI18n();
  const [before, setBefore] = useState<number | null>(null);
  const [pages, setPages] = useState<AuditItem[]>([]);
  const { data, error } = useLoad<{ items: AuditItem[]; next_before_seq: number | null }>(`/bureau/audit?limit=50${before ? `&before_seq=${before}` : ""}`);
  const [verify, setVerify] = useState<{ valid: boolean; checked: number; broken_at_seq?: number } | null>(null);
  const items = [...pages, ...(data?.items ?? [])];
  return (
    <>
      <BureauTitle
        title={t("bureau.audit.title")}
        actions={
          <Button variant="secondary" onClick={() => api<typeof verify>("/bureau/audit/verify").then(setVerify)}>
            {t("bureau.audit.verify")}
          </Button>
        }
      />
      {verify && (
        <Alert tone={verify.valid ? "success" : "danger"} className="mb-6">
          {verify.valid ? t("bureau.audit.valid", { count: verify.checked }) : t("bureau.audit.invalid", { seq: verify.broken_at_seq ?? "?" })}
        </Alert>
      )}
      <LoadError error={error} />
      {!data && !error ? (
        <Loading label={t("common.loading")} />
      ) : (
        <Table caption={t("bureau.audit.title")}>
          <thead>
            <tr>
              <th>#</th>
              <th>{t("bureau.audit.when")}</th>
              <th>{t("bureau.audit.actor")}</th>
              <th>{t("bureau.audit.action")}</th>
              <th>{t("bureau.audit.resource")}</th>
              <th>{t("bureau.audit.outcome")}</th>
            </tr>
          </thead>
          <tbody>
            {items.map((e) => (
              <tr key={e.seq}>
                <td>{e.seq}</td>
                <td className="whitespace-nowrap">{formatDateTime(e.occurred_at, locale)}</td>
                <td>{e.actor}</td>
                <td className="font-mono text-xs">{e.action}</td>
                <td className="font-mono text-xs">
                  {e.resource_type}
                  {e.resource_id ? `:${e.resource_id.slice(0, 12)}` : ""}
                </td>
                <td>
                  <Badge tone={e.outcome === "success" ? "success" : "danger"}>{e.outcome}</Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
      {data?.next_before_seq && (
        <Button
          className="mt-4"
          variant="secondary"
          onClick={() => {
            setPages(items);
            setBefore(data.next_before_seq);
          }}
        >
          {t("bureau.audit.more")}
        </Button>
      )}
    </>
  );
}

/* ================================================================ feature flags */

export function FeatureFlags() {
  const { t } = useI18n();
  const { data, error, reload } = useLoad<{ feature_flags: Record<string, boolean> }>("/config/public");
  const [flags, setFlags] = useState<Record<string, boolean> | null>(null);
  const [justification, setJustification] = useState("");
  const a = useAction();
  const cur = flags ?? data?.feature_flags ?? null;
  return (
    <>
      <BureauTitle title={t("bureau.settings.title")} lead={t("bureau.settings.lead")} />
      <LoadError error={error} />
      {cur && (
        <Card className="max-w-2xl space-y-4">
          {Object.entries(cur).map(([k, v]) => (
            <Checkbox key={k} id={`flag-${k}`} label={<span className="font-mono text-sm">{k}</span>} checked={v} onChange={(e) => setFlags({ ...cur, [k]: e.target.checked })} />
          ))}
          <Textarea id="just" label={t("bureau.settings.justification")} value={justification} onChange={(e) => setJustification(e.target.value)} maxLength={2000} />
          <Button
            onClick={() =>
              a.run(() => api("/bureau/settings/feature-flags", { method: "PUT", json: { flags: cur, justification } }), t("bureau.dest.saved")).then((ok) => {
                if (ok) {
                  setFlags(null);
                  void reload();
                }
              })
            }
          >
            {t("bureau.settings.save")}
          </Button>
          {a.view}
        </Card>
      )}
    </>
  );
}
