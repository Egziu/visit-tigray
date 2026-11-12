"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Alert, Badge, Button, Checkbox, EmptyState, Input, Loading, Select, Textarea } from "@/components/ui";
import { api, ApiError, errorMessage } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { Competition, Provider } from "@/lib/types";
import { useLoad } from "@/components/bureau/hooks";
import { useI18n, useSession } from "./providers";

function useApi<T>(path: string | null) {
  const { data, error } = useLoad<T>(path);
  return { data, error };
}

function ErrorState({ e }: { e: unknown }) {
  const { t } = useI18n();
  return <Alert tone="caution">{e instanceof ApiError && e.notAvailable ? t("common.notAvailableYet") : errorMessage(e)}</Alert>;
}

/* ================================================================ awards */

export function CompetitionList() {
  const { t, locale } = useI18n();
  const { data, error } = useApi<Competition[]>(`/competitions?locale=${locale}`);
  if (error) return <ErrorState e={error} />;
  if (!data) return <Loading label={t("common.loading")} />;
  if (data.length === 0) return <EmptyState title={t("awards.none")}>{t("awards.notOpen")}</EmptyState>;
  return (
    <ul className="grid gap-6 md:grid-cols-2">
      {data.map((c) => (
        <li key={c.slug} className="rounded-[var(--radius)] border border-line bg-surface p-7">
          <div className="flex flex-wrap gap-2">
            <Badge tone={c.is_live ? "success" : "caution"}>{t("awards.status", { status: c.status })}</Badge>
          </div>
          <h2 className="mt-3 text-3xl">
            <Link href={`/${locale}/awards/${c.slug}`} className="hover:underline">
              {c.title}
            </Link>
          </h2>
          {!c.is_live && <p className="mt-3 text-sm text-muted">{t("awards.notOpen")}</p>}
        </li>
      ))}
    </ul>
  );
}

export function CompetitionDetail({ slug }: { slug: string }) {
  const { t, locale } = useI18n();
  const { me } = useSession();
  const { data: c, error } = useApi<Competition>(`/competitions/${encodeURIComponent(slug)}?locale=${locale}`);
  const [results, setResults] = useState<{ winners?: { category: string; title: string; author: string }[] } | null>(null);
  const [category, setCategory] = useState("");
  const [memoryId, setMemoryId] = useState("");
  const [statement, setStatement] = useState("");
  const [rights, setRights] = useState(false);
  const [msg, setMsg] = useState<{ tone: "success" | "danger"; text: string } | null>(null);
  useEffect(() => {
    api<typeof results>(`/competitions/${encodeURIComponent(slug)}/results`).then(setResults).catch(() => setResults(null));
  }, [slug]);
  if (error) return <ErrorState e={error} />;
  if (!c) return <Loading label={t("common.loading")} />;
  return (
    <div className="space-y-8">
      <div>
        <Badge tone={c.is_live ? "success" : "caution"}>{t("awards.status", { status: c.status })}</Badge>
        <h1 className="mt-3 text-5xl">{c.title}</h1>
        {c.description && <p className="mt-4 max-w-3xl text-lg text-muted">{c.description}</p>}
      </div>
      {!c.is_live && <Alert tone="caution">{t("awards.notOpen")}</Alert>}
      <section>
        <h2 className="text-3xl">{t("awards.prize")}</h2>
        <p className="mt-2 text-muted">{c.prize_description || t("awards.prizeTbc")}</p>
      </section>
      {c.categories.length > 0 && (
        <section>
          <h2 className="text-3xl">{t("awards.categories")}</h2>
          <ul className="mt-3 grid gap-3 sm:grid-cols-2">
            {c.categories.map((cat) => (
              <li key={cat.key} className="rounded-lg border border-line bg-surface p-4">
                <p className="font-medium">{cat.name}</p>
                {cat.description && <p className="text-sm text-muted">{cat.description}</p>}
              </li>
            ))}
          </ul>
        </section>
      )}
      {c.rules_url && (
        <a href={c.rules_url} className="underline" target="_blank" rel="noopener noreferrer">
          {t("awards.rules")}
        </a>
      )}
      {(c.opens_at || c.closes_at) && (
        <p className="text-sm text-muted">
          {formatDate(c.opens_at, locale)} – {formatDate(c.closes_at, locale)}
        </p>
      )}
      {c.is_live && me && (
        <form
          className="max-w-xl space-y-4 rounded-[var(--radius)] border border-line bg-surface p-6"
          onSubmit={async (e) => {
            e.preventDefault();
            setMsg(null);
            try {
              await api(`/competitions/${encodeURIComponent(slug)}/entries`, { json: { category_key: category, memory_id: memoryId, statement, rights_confirmed: rights } });
              setMsg({ tone: "success", text: t("awards.entered") });
            } catch (err) {
              setMsg({ tone: "danger", text: errorMessage(err) });
            }
          }}
        >
          <h2 className="text-2xl">{t("awards.enter")}</h2>
          <Select id="cat" label={t("awards.categories")} value={category} onChange={(e) => setCategory(e.target.value)} required options={[{ value: "", label: "—" }, ...c.categories.map((x) => ({ value: x.key, label: x.name }))]} />
          <Input id="mem" label={t("awards.memoryId")} value={memoryId} onChange={(e) => setMemoryId(e.target.value)} required />
          <Textarea id="stmt" label={t("awards.statement")} value={statement} onChange={(e) => setStatement(e.target.value)} maxLength={2000} />
          <Checkbox id="rights" label={t("awards.rightsEntry")} checked={rights} onChange={(e) => setRights(e.target.checked)} required />
          <Button type="submit">{t("common.submit")}</Button>
          {msg && <Alert tone={msg.tone}>{msg.text}</Alert>}
        </form>
      )}
      <section>
        <h2 className="text-3xl">{t("awards.results")}</h2>
        {results?.winners?.length ? (
          <ul className="mt-3 space-y-2">
            {results.winners.map((w) => (
              <li key={`${w.category}-${w.title}`}>
                <strong>{w.category}</strong>: {w.title} — {w.author}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-muted">{t("awards.noResults")}</p>
        )}
      </section>
    </div>
  );
}

/* ================================================================ providers */

const VERIFY_TONE = { verified: "success", pending: "caution", expired: "danger", unverified: "neutral" } as const;

function VerificationBadge({ v }: { v: Provider["verification"] }) {
  const { t, locale } = useI18n();
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <Badge tone={VERIFY_TONE[v.status]}>{t(`providers.status.${v.status}`)}</Badge>
      {v.verified_at && <span className="text-muted">{t("providers.verifiedOn", { date: formatDate(v.verified_at, locale) })}</span>}
      {v.licence_authority && <span className="text-muted">{t("providers.authority", { authority: v.licence_authority })}</span>}
    </div>
  );
}

export function ProviderList() {
  const { t, locale } = useI18n();
  const [type, setType] = useState("");
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const qs = new URLSearchParams({ locale });
  if (type) qs.set("type", type);
  if (query) qs.set("q", query);
  const { data, error } = useApi<Provider[] | { items: Provider[] }>(`/providers?${qs}`);
  const items = data ? (Array.isArray(data) ? data : data.items) : null;
  const types = ["tour_operator", "guide", "accommodation", "restaurant", "transport", "museum", "cultural_institution", "handicraft", "community_tourism", "event_organizer"];
  return (
    <div className="space-y-6">
      <Alert tone="info">{t("providers.noBookings")}</Alert>
      <form
        role="search"
        className="grid gap-4 rounded-[var(--radius)] border border-line bg-surface p-5 md:grid-cols-[2fr_1fr_auto] md:items-end"
        onSubmit={(e) => {
          e.preventDefault();
          setQuery(q);
        }}
      >
        <Input id="pq" type="search" label={t("common.search")} value={q} onChange={(e) => setQ(e.target.value)} />
        <Select id="ptype" label={t("providers.type")} value={type} onChange={(e) => setType(e.target.value)} options={[{ value: "", label: t("providers.allTypes") }, ...types.map((x) => ({ value: x, label: x.replace(/_/g, " ") }))]} />
        <Button type="submit">{t("common.search")}</Button>
      </form>
      {error ? (
        <ErrorState e={error} />
      ) : !items ? (
        <Loading label={t("common.loading")} />
      ) : items.length === 0 ? (
        <EmptyState title={t("providers.none")} />
      ) : (
        <ul className="grid gap-5 md:grid-cols-2">
          {items.map((p) => (
            <li key={p.slug} className="rounded-[var(--radius)] border border-line bg-surface p-6">
              <p className="text-xs uppercase tracking-[0.18em] text-earth">
                {p.type.replace(/_/g, " ")} · {p.area}
              </p>
              <h2 className="mt-2 text-2xl">
                <Link href={`/${locale}/providers/${p.slug}`} className="hover:underline">
                  {p.name}
                </Link>
              </h2>
              <p className="mt-2 text-muted">{p.summary}</p>
              <div className="mt-4">
                <VerificationBadge v={p.verification} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function ProviderDetail({ slug }: { slug: string }) {
  const { t, locale } = useI18n();
  const { me, config } = useSession();
  const { data: p, error } = useApi<Provider>(`/providers/${encodeURIComponent(slug)}?locale=${locale}`);
  const [message, setMessage] = useState("");
  const [dates, setDates] = useState("");
  const [group, setGroup] = useState("");
  const [msg, setMsg] = useState<{ tone: "success" | "danger"; text: string } | null>(null);
  if (error) return <ErrorState e={error} />;
  if (!p) return <Loading label={t("common.loading")} />;
  const inquiries = config?.feature_flags?.provider_inquiries !== false;
  return (
    <div className="grid gap-10 lg:grid-cols-[1.5fr_1fr]">
      <div>
        <p className="text-xs uppercase tracking-[0.2em] text-earth">
          {p.type.replace(/_/g, " ")} · {p.area}
        </p>
        <h1 className="mt-2 text-5xl">{p.name}</h1>
        <div className="mt-4">
          <VerificationBadge v={p.verification} />
        </div>
        <p className="prose-vt mt-6 text-lg">{p.description ?? p.summary}</p>
        {p.contact && Object.keys(p.contact).length > 0 && (
          <dl className="mt-6 space-y-2">
            {Object.entries(p.contact).map(([k, v]) => (
              <div key={k}>
                <dt className="text-sm text-muted">{k}</dt>
                <dd>{v}</dd>
              </div>
            ))}
          </dl>
        )}
      </div>
      <aside className="space-y-4">
        {!config?.feature_flags?.bookings && <Alert tone="info">{t("providers.noBookings")}</Alert>}
        {inquiries && me ? (
          <form
            className="space-y-4 rounded-[var(--radius)] border border-line bg-surface p-6"
            onSubmit={async (e) => {
              e.preventDefault();
              setMsg(null);
              try {
                await api(`/providers/${encodeURIComponent(slug)}/inquiries`, {
                  json: { message, travel_dates: dates || undefined, group_size: group ? Number(group) : undefined },
                });
                setMsg({ tone: "success", text: t("providers.sent") });
                setMessage("");
              } catch (err) {
                setMsg({ tone: "danger", text: errorMessage(err) });
              }
            }}
          >
            <h2 className="text-2xl">{t("providers.inquiry")}</h2>
            <Textarea id="msg" label={t("providers.message")} value={message} onChange={(e) => setMessage(e.target.value)} required minLength={10} maxLength={3000} />
            <Input id="dates" label={t("providers.dates")} value={dates} onChange={(e) => setDates(e.target.value)} maxLength={100} />
            <Input id="grp" type="number" min={1} max={200} label={t("providers.group")} value={group} onChange={(e) => setGroup(e.target.value)} />
            <Button type="submit">{t("common.submit")}</Button>
            {msg && <Alert tone={msg.tone}>{msg.text}</Alert>}
          </form>
        ) : inquiries ? (
          <p className="text-sm">
            <Link href={`/${locale}/account`} className="underline">
              {t("common.signIn")}
            </Link>{" "}
            — {t("providers.inquiry")}
          </p>
        ) : null}
      </aside>
    </div>
  );
}
