"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Alert, Badge, Button, Checkbox, EmptyState, Input, Loading, Select, Textarea } from "@/components/ui";
import { api, ApiError, errorMessage } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { queue } from "@/lib/offline";
import type { Destination, MediaItem, Memory } from "@/lib/types";
import { useOnline } from "./pwa";
import { useI18n, useSession } from "./providers";

function NotYet({ e }: { e: unknown }) {
  const { t } = useI18n();
  return <Alert tone="caution">{e instanceof ApiError && e.notAvailable ? t("common.notAvailableYet") : errorMessage(e)}</Alert>;
}

export function MemoryCard({ m }: { m: Memory }) {
  const { t, locale } = useI18n();
  const img = m.media[0];
  return (
    <article className="lift relative flex flex-col overflow-hidden rounded-[var(--radius)] border border-line bg-surface">
      {img && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={img.urls.md ?? img.urls.sm} alt={img.alt_text_i18n?.[locale] ?? img.alt_text_i18n?.en ?? ""} loading="lazy" className="saver-hide aspect-[4/3] w-full object-cover" />
      )}
      <div className="flex flex-1 flex-col p-6">
        <p className="text-xs uppercase tracking-[0.18em] text-earth">
          {[m.destination?.name, formatDate(m.published_at, locale)].filter(Boolean).join(" · ")}
        </p>
        <h3 className="mt-2 text-2xl">
          <Link href={`/${locale}/memories/${m.id}`} className="after:absolute after:inset-0 hover:underline">
            {m.title}
          </Link>
        </h3>
        <p className="mt-2 line-clamp-4 text-muted">{m.excerpt}</p>
        <p className="mt-auto pt-4 text-sm">{t("memories.by", { name: m.author.display_name })}</p>
        {m.featured && <Badge tone="earth" className="absolute right-3 top-3 bg-surface">{t("memories.featured")}</Badge>}
      </div>
    </article>
  );
}

export function MemoryFeed({ creator }: { creator?: string }) {
  const { t, locale } = useI18n();
  const [items, setItems] = useState<Memory[] | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const load = useCallback(
    async (c?: string | null) => {
      try {
        const qs = new URLSearchParams({ locale });
        if (c) qs.set("cursor", c);
        if (creator) qs.set("creator", creator);
        const r = await api<{ items: Memory[]; next_cursor: string | null }>(`/memories?${qs}`);
        setItems((prev) => (c ? [...(prev ?? []), ...r.items] : r.items));
        setCursor(r.next_cursor);
      } catch (e) {
        setError(e);
      }
    },
    [locale, creator],
  );
  useEffect(() => {
    void load();
  }, [load]);
  if (error) return <NotYet e={error} />;
  if (!items) return <Loading label={t("common.loading")} />;
  if (items.length === 0) return <EmptyState title={t("memories.none")} />;
  return (
    <>
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((m) => (
          <MemoryCard key={m.id} m={m} />
        ))}
      </div>
      {cursor && (
        <div className="mt-8 text-center">
          <Button variant="secondary" onClick={() => load(cursor)}>
            {t("memories.loadMore")}
          </Button>
        </div>
      )}
    </>
  );
}

interface Comment {
  id: string;
  body: string;
  author: { display_name: string; handle?: string };
  created_at: string;
}

export function MemoryDetail({ id }: { id: string }) {
  const { t, locale } = useI18n();
  const { me } = useSession();
  const [m, setM] = useState<Memory | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [comment, setComment] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [reason, setReason] = useState("spam");
  const [detail, setDetail] = useState("");
  const [reporting, setReporting] = useState(false);

  useEffect(() => {
    api<Memory>(`/memories/${id}`).then(setM).catch(setError);
    api<Comment[] | { items: Comment[] }>(`/memories/${id}/comments`)
      .then((r) => setComments(Array.isArray(r) ? r : r.items))
      .catch(() => undefined);
  }, [id]);

  if (error) return <NotYet e={error} />;
  if (!m) return <Loading label={t("common.loading")} />;

  async function act(fn: () => Promise<unknown>, ok: string) {
    setStatus(null);
    try {
      await fn();
      setStatus(ok);
    } catch (e) {
      setStatus(errorMessage(e));
    }
  }

  return (
    <article lang={m.locale}>
      <p className="text-xs uppercase tracking-[0.2em] text-earth">
        {[m.destination?.name, formatDate(m.published_at, locale)].filter(Boolean).join(" · ")}
      </p>
      <h1 className="mt-3 text-5xl">{m.title}</h1>
      <p className="mt-3">
        <Link className="underline" href={`/${locale}/creators/${m.author.handle}`}>
          {t("memories.by", { name: m.author.display_name })}
        </Link>
      </p>
      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        {m.media.map((img: MediaItem) => (
          <figure key={img.id}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={img.urls.lg ?? img.urls.md} alt={img.alt_text_i18n?.[locale] ?? img.alt_text_i18n?.en ?? ""} className="saver-hide w-full rounded-[var(--radius)]" />
          </figure>
        ))}
      </div>
      <div className="prose-vt mt-8 text-lg">{m.body ?? m.excerpt}</div>

      <div className="mt-8 flex flex-wrap gap-3">
        {me && (
          <Button variant="secondary" size="sm" onClick={() => act(() => api(`/memories/${id}/save`, { method: "POST" }), t("memories.storySaved"))}>
            {t("memories.saveStory")}
          </Button>
        )}
        <Button variant="ghost" size="sm" onClick={() => setReporting((r) => !r)} aria-expanded={reporting}>
          {t("memories.report")}
        </Button>
      </div>
      {reporting && (
        <form
          className="mt-4 max-w-lg space-y-3 rounded-[var(--radius)] border border-line bg-surface p-5"
          onSubmit={(e) => {
            e.preventDefault();
            void act(() => api(`/memories/${id}/report`, { json: { reason, detail } }), t("memories.reportSent")).then(() => setReporting(false));
          }}
        >
          <Select
            id="reason"
            label={t("memories.reportReason")}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            options={(["spam", "harassment", "copyright", "privacy", "misinformation", "other"] as const).map((r) => ({ value: r, label: t(`memories.reasons.${r}`) }))}
          />
          <Textarea id="detail" label={t("memories.reportDetail")} value={detail} onChange={(e) => setDetail(e.target.value)} maxLength={1000} />
          <Button type="submit" size="sm">
            {t("common.submit")}
          </Button>
        </form>
      )}
      {status && (
        <p role="status" className="mt-3 text-sm">
          {status}
        </p>
      )}

      <section className="mt-14" aria-labelledby="comments">
        <h2 id="comments" className="text-3xl">
          {t("memories.comments")}
        </h2>
        <ul className="mt-4 space-y-4">
          {comments.map((c) => (
            <li key={c.id} className="rounded-lg border border-line bg-surface p-4">
              <p className="text-sm font-medium">{c.author.display_name}</p>
              <p className="mt-1 whitespace-pre-line">{c.body}</p>
            </li>
          ))}
        </ul>
        {me ? (
          <form
            className="mt-6 max-w-xl space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              void act(() => api(`/memories/${id}/comments`, { json: { body: comment } }), t("memories.commentPending")).then(() => setComment(""));
            }}
          >
            <Textarea id="comment" label={t("memories.addComment")} value={comment} onChange={(e) => setComment(e.target.value)} maxLength={2000} required />
            <Button type="submit" size="sm" disabled={!comment.trim()}>
              {t("memories.postComment")}
            </Button>
          </form>
        ) : (
          <p className="mt-4 text-sm text-muted">
            <Link href={`/${locale}/account`} className="underline">
              {t("common.signIn")}
            </Link>
          </p>
        )}
      </section>
    </article>
  );
}

export function NewMemoryForm() {
  const { t, locale } = useI18n();
  const { me, loading } = useSession();
  const online = useOnline();
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [dest, setDest] = useState("");
  const [destinations, setDestinations] = useState<Pick<Destination, "slug" | "name">[]>([]);
  const [files, setFiles] = useState<FileList | null>(null);
  const [rights, setRights] = useState(false);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notes, setNotes] = useState<string[]>([]);
  const [done, setDone] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<{ items: Destination[] }>(`/destinations?locale=${locale}&limit=100`)
      .then((r) => setDestinations(r.items.map(({ slug, name }) => ({ slug, name }))))
      .catch(() => undefined);
  }, [locale]);

  if (loading) return <Loading label={t("common.loading")} />;
  if (!me)
    return (
      <Alert tone="info">
        <Link href={`/${locale}/account`} className="underline">
          {t("common.signIn")}
        </Link>{" "}
        — {t("common.signInRequired")}
      </Alert>
    );
  if (!me.email_verified) return <Alert tone="caution">{t("memories.verifyFirst")}</Alert>;
  if (done) return <Alert tone="success">{done}</Alert>;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setNotes([]);
    if (!consent) return setError(t("memories.consent"));
    if (files?.length && !rights) return setError(t("memories.rights"));
    setBusy(true);
    const payload = { title, body, destination_slug: dest || undefined, locale, consent_publish: true, media_ids: [] as string[] };
    try {
      if (!online) {
        if (files?.length) throw new Error(t("offline.youAreOffline"));
        await queue({ id: crypto.randomUUID(), kind: "memory", createdAt: new Date().toISOString(), payload, attempts: 0 });
        setDone(t("memories.queuedOffline"));
        return;
      }
      const n: string[] = [];
      for (const f of Array.from(files ?? []).slice(0, 6)) {
        const fd = new FormData();
        fd.append("file", f);
        fd.append("purpose", "community");
        fd.append("rights_confirmed", String(rights));
        const up = await api<{ id: string; had_gps_metadata: boolean; duplicates: unknown[] }>("/media", { method: "POST", body: fd });
        payload.media_ids.push(up.id);
        if (up.had_gps_metadata) n.push(t("memories.gpsRemoved"));
        if (up.duplicates?.length) n.push(t("memories.duplicateWarning"));
      }
      setNotes(n);
      await api("/memories", { json: payload });
      setDone(t("memories.submitted"));
    } catch (err) {
      setError(err instanceof ApiError && err.notAvailable ? t("common.notAvailableYet") : errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="max-w-2xl space-y-6">
      <Input id="m-title" label={t("memories.storyTitle")} value={title} onChange={(e) => setTitle(e.target.value)} required minLength={5} maxLength={140} />
      <Textarea id="m-body" label={t("memories.storyBody")} value={body} onChange={(e) => setBody(e.target.value)} required minLength={30} maxLength={20000} rows={10} />
      <Select id="m-dest" label={t("memories.destination")} value={dest} onChange={(e) => setDest(e.target.value)} options={[{ value: "", label: "—" }, ...destinations.map((d) => ({ value: d.slug, label: d.name }))]} />
      <div className="flex flex-col gap-1.5">
        <label htmlFor="m-files" className="text-sm font-medium">
          {t("memories.photos")}
        </label>
        <input id="m-files" type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={(e) => setFiles(e.target.files)} className="text-sm" />
      </div>
      <Checkbox id="m-rights" label={t("memories.rights")} checked={rights} onChange={(e) => setRights(e.target.checked)} />
      <Checkbox id="m-consent" label={t("memories.consent")} checked={consent} onChange={(e) => setConsent(e.target.checked)} required />
      {error && <Alert tone="danger">{error}</Alert>}
      {notes.map((n) => (
        <Alert key={n} tone="info">
          {n}
        </Alert>
      ))}
      <Button type="submit" disabled={busy}>
        {busy ? t("common.loading") : t("memories.submit")}
      </Button>
    </form>
  );
}

export function CreatorProfile({ handle }: { handle: string }) {
  const { t } = useI18n();
  const { me } = useSession();
  const [p, setP] = useState<{ handle: string; display_name: string; bio?: string; following?: boolean } | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => {
    api<typeof p>(`/creators/${encodeURIComponent(handle)}`).then(setP).catch(setError);
  }, [handle]);
  if (error) return <NotYet e={error} />;
  if (!p) return <Loading label={t("common.loading")} />;
  return (
    <div>
      <p className="text-xs uppercase tracking-[0.2em] text-earth">{t("memories.creator")}</p>
      <h1 className="mt-2 text-5xl">{p.display_name}</h1>
      <p className="text-muted">@{p.handle}</p>
      {p.bio && <p className="mt-4 max-w-2xl">{p.bio}</p>}
      {me && (
        <Button
          className="mt-6"
          variant="secondary"
          size="sm"
          onClick={async () => {
            try {
              await api(`/creators/${encodeURIComponent(handle)}/follow`, { method: "POST" });
              setP({ ...p, following: true });
            } catch (e) {
              setMsg(errorMessage(e));
            }
          }}
          aria-pressed={!!p.following}
        >
          {p.following ? t("memories.following") : t("memories.follow")}
        </Button>
      )}
      {msg && <p role="status">{msg}</p>}
      <div className="mt-10">
        <MemoryFeed creator={handle} />
      </div>
    </div>
  );
}
