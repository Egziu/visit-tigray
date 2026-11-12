"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Alert, Badge, Button, ButtonLink, Checkbox, EmptyState, Input, Loading, Select, Skeleton, Textarea, cn } from "@/components/ui";
import { Dialog } from "@/components/ui/client";
import { api, ApiError, errorMessage } from "@/lib/api";
import { formatDate, formatDateTime } from "@/lib/format";
import type { BlockType, Destination, JournalBlock, JournalComment, JournalPost, JournalSummary, MediaItem, Publication } from "@/lib/types";
import { MediaFigure } from "./content";
import { CardArt } from "./illustrations";
import { useI18n, useSession } from "./providers";

/* ================================================================== shared helpers */

type Feed = "latest" | "following" | "featured";
const REPORT_REASONS = ["spam", "harassment", "copyright", "privacy", "misinformation", "sacred_content", "impersonation", "other"] as const;

function useNotAvailable() {
  const { t } = useI18n();
  return useCallback((e: unknown) => (e instanceof ApiError && e.notAvailable ? t("common.notAvailableYet") : errorMessage(e)), [t]);
}

export async function uploadImage(file: File, rightsConfirmed: boolean): Promise<MediaItem> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("purpose", "community");
  fd.append("rights_confirmed", String(rightsConfirmed));
  return api<MediaItem>("/media", { method: "POST", body: fd });
}

/** Web Share API with a copy-link fallback. Returns the status message key used. */
export function ShareButton({ title, text, path, className }: { title: string; text?: string; path: string; className?: string }) {
  const { t } = useI18n();
  const [msg, setMsg] = useState<string | null>(null);
  async function share() {
    const url = `${window.location.origin}${path}`;
    try {
      if (navigator.share) {
        await navigator.share({ title, text, url });
        return;
      }
      await navigator.clipboard.writeText(url);
      setMsg(t("journal.linkCopied"));
    } catch {
      /* user dismissed the share sheet */
    }
  }
  return (
    <span className="inline-flex items-center gap-2">
      <button type="button" onClick={share} className={cn("inline-flex min-h-[40px] items-center gap-2 rounded-full border border-line px-4 py-1.5 text-sm hover:border-sandstone", className)}>
        <span aria-hidden="true">↗</span> {t("journal.share")}
      </button>
      {msg && (
        <span role="status" className="text-sm text-muted">
          {msg}
        </span>
      )}
    </span>
  );
}

export function ReportButton({ path, className }: { path: string; className?: string }) {
  const { t } = useI18n();
  const { me } = useSession();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState<string>("spam");
  const [detail, setDetail] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "done">("idle");
  const [error, setError] = useState<string | null>(null);
  const toMsg = useNotAvailable();
  if (!me) return null;
  return (
    <>
      <button type="button" onClick={() => setOpen(true)} className={cn("min-h-[40px] rounded-full px-3 py-1.5 text-sm text-muted underline-offset-4 hover:underline", className)}>
        {t("journal.report")}
      </button>
      <Dialog open={open} onClose={() => setOpen(false)} title={t("journal.reportTitle")} closeLabel={t("common.close")}>
        {state === "done" ? (
          <p role="status">{t("journal.reportThanks")}</p>
        ) : (
          <form
            className="space-y-4"
            onSubmit={async (e) => {
              e.preventDefault();
              setState("sending");
              setError(null);
              try {
                await api(path, { json: { reason, detail } });
                setState("done");
              } catch (err) {
                setError(toMsg(err));
                setState("idle");
              }
            }}
          >
            <Select id="report-reason" label={t("journal.reportReason")} value={reason} onChange={(e) => setReason(e.target.value)} options={REPORT_REASONS.map((r) => ({ value: r, label: t(`journal.reasons.${r}`) }))} />
            <Textarea id="report-detail" label={t("journal.reportDetail")} value={detail} onChange={(e) => setDetail(e.target.value)} maxLength={2000} />
            {error && <Alert tone="danger">{error}</Alert>}
            <Button type="submit" disabled={state === "sending"}>
              {t("journal.reportSend")}
            </Button>
          </form>
        )}
      </Dialog>
    </>
  );
}

function Cover({ media, seed, locale, className, priority }: { media: MediaItem | null; seed: string; locale: string; className?: string; priority?: boolean }) {
  if (media) {
    const alt = media.alt_text_i18n?.[locale] ?? media.alt_text_i18n?.en ?? "";
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img src={media.urls.lg ?? media.urls.md} alt={alt} width={media.width} height={media.height} loading={priority ? "eager" : "lazy"} className={cn("saver-hide h-full w-full object-cover", className)} />
    );
  }
  return <CardArt seed={seed} className={cn("h-full w-full", className)} />;
}

function Byline({ p, locale }: { p: JournalSummary; locale: string }) {
  const { t } = useI18n();
  return (
    <p className="text-sm text-muted">
      <Link href={`/${locale}/journal/p/${p.publication.handle}`} className="font-medium text-ink hover:underline">
        {p.publication.name}
      </Link>
      {" · "}
      {t("journal.by", { name: p.author.display_name })}
      {p.published_at && <> · {formatDate(p.published_at, locale)}</>}
      {" · "}
      {t("journal.readingTime", { n: Math.max(1, p.reading_minutes) })}
    </p>
  );
}

/* ================================================================== feed */

export function JournalCard({ p, large }: { p: JournalSummary; large?: boolean }) {
  const { locale, t } = useI18n();
  return (
    <article className={cn("lift group overflow-hidden rounded-[var(--radius)] border border-line bg-surface", large && "md:grid md:grid-cols-[1.25fr_1fr]")}>
      <div className={cn("overflow-hidden bg-surface-2", large ? "aspect-[16/10] md:aspect-auto md:min-h-[360px]" : "aspect-[16/9]")}>
        <Cover media={p.cover} seed={p.id} locale={locale} priority={large} />
      </div>
      <div className={cn("flex flex-col gap-3", large ? "p-7 md:p-10" : "p-5")}>
        <div className="flex flex-wrap gap-2">
          {p.destination && <Badge tone="forest">{p.destination.name}</Badge>}
          {p.tags.slice(0, 3).map((tag) => (
            <Badge key={tag}>#{tag}</Badge>
          ))}
        </div>
        <h3 className={cn(large ? "text-4xl sm:text-5xl" : "text-2xl")}>
          <Link href={`/${locale}/journal/${p.id}`} className="after:absolute after:inset-0 hover:underline focus-visible:underline [&]:relative">
            {p.title}
          </Link>
        </h3>
        {p.subtitle && <p className={cn("text-muted", large && "text-lg")}>{p.subtitle}</p>}
        {large && p.excerpt && <p className="line-clamp-3">{p.excerpt}</p>}
        <div className="mt-auto pt-2">
          <Byline p={p} locale={locale} />
          <p className="mt-1 text-xs text-muted" aria-label={`${t("journal.likes", { n: p.like_count })}, ${t("journal.commentsCount", { n: p.comment_count })}`}>
            <span aria-hidden="true">♥ {p.like_count} · 💬 {p.comment_count}</span>
          </p>
        </div>
      </div>
    </article>
  );
}

export function JournalFeed() {
  const { t, locale } = useI18n();
  const { me } = useSession();
  const toMsg = useNotAvailable();
  const [feed, setFeed] = useState<Feed>("latest");
  const [destination, setDestination] = useState("");
  const [tag, setTag] = useState("");
  const [tagInput, setTagInput] = useState("");
  const [items, setItems] = useState<JournalSummary[] | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [more, setMore] = useState(false);
  const [destinations, setDestinations] = useState<Pick<Destination, "slug" | "name">[]>([]);

  useEffect(() => {
    api<{ items: Destination[] }>(`/destinations?locale=${locale}&limit=100`)
      .then((r) => setDestinations(r.items.map(({ slug, name }) => ({ slug, name }))))
      .catch(() => undefined);
  }, [locale]);

  const query = useMemo(() => {
    const q = new URLSearchParams({ feed, locale });
    if (destination) q.set("destination", destination);
    if (tag) q.set("tag", tag);
    return q;
  }, [feed, locale, destination, tag]);

  useEffect(() => {
    if (feed === "following" && !me) return;
    let cancelled = false;
    api<{ items: JournalSummary[]; next_cursor: string | null }>(`/journal?${query}`)
      .then((r) => {
        if (cancelled) return;
        setItems(r.items);
        setCursor(r.next_cursor);
        setError(null);
      })
      .catch((e) => {
        if (cancelled) return;
        setItems([]);
        setError(toMsg(e));
      });
    return () => {
      cancelled = true;
    };
  }, [query, feed, me, toMsg]);

  async function loadMore() {
    if (!cursor) return;
    setMore(true);
    try {
      const q = new URLSearchParams(query);
      q.set("cursor", cursor);
      const r = await api<{ items: JournalSummary[]; next_cursor: string | null }>(`/journal?${q}`);
      setItems((xs) => [...(xs ?? []), ...r.items]);
      setCursor(r.next_cursor);
    } catch (e) {
      setError(toMsg(e));
    } finally {
      setMore(false);
    }
  }

  const tabs: { id: Feed; label: string }[] = [
    { id: "latest", label: t("journal.feedLatest") },
    { id: "following", label: t("journal.feedFollowing") },
    { id: "featured", label: t("journal.feedFeatured") },
  ];
  const needsSignIn = feed === "following" && !me;

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-5 border-b border-line pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div role="group" aria-label={t("journal.feedLabel")} className="flex flex-wrap gap-2">
          {tabs.map((tb) => (
            <button
              key={tb.id}
              type="button"
              aria-pressed={feed === tb.id}
              onClick={() => {
                setFeed(tb.id);
                setItems(null);
              }}
              className={cn("min-h-[44px] rounded-full border px-5 py-2 text-sm", feed === tb.id ? "border-forest bg-forest text-on-forest" : "border-line bg-surface hover:border-sandstone")}
            >
              {tb.label}
            </button>
          ))}
        </div>
        <div className="grid gap-3 sm:grid-cols-[220px_220px_auto] sm:items-end">
          <Select
            id="j-dest"
            label={t("journal.filterDestination")}
            value={destination}
            onChange={(e) => {
              setDestination(e.target.value);
              setItems(null);
            }}
            options={[{ value: "", label: t("journal.anyDestination") }, ...destinations.map((d) => ({ value: d.slug, label: d.name }))]}
          />
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setTag(tagInput.trim().replace(/^#/, "").toLowerCase());
              setItems(null);
            }}
          >
            <Input id="j-tag" label={t("journal.filterTag")} placeholder={t("journal.tagPlaceholder")} value={tagInput} onChange={(e) => setTagInput(e.target.value)} maxLength={40} />
          </form>
          {me && (
            <ButtonLink href={`/${locale}/journal/new`} className="sm:mb-0">
              {t("journal.write")}
            </ButtonLink>
          )}
        </div>
      </div>

      {needsSignIn ? (
        <EmptyState title={t("journal.feedFollowing")} action={<ButtonLink href={`/${locale}/account`}>{t("common.signIn")}</ButtonLink>}>
          {t("journal.signInFollowing")}
        </EmptyState>
      ) : items === null ? (
        <div className="grid gap-6 md:grid-cols-2" aria-hidden="true">
          <Skeleton className="h-80 md:col-span-2" />
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
        </div>
      ) : error ? (
        <Alert tone="caution">{error}</Alert>
      ) : items.length === 0 ? (
        <EmptyState title={t("journal.emptyTitle")} action={me ? <ButtonLink href={`/${locale}/journal/new`}>{t("journal.write")}</ButtonLink> : undefined}>
          {feed === "following" ? t("journal.emptyFollowing") : t("journal.empty")}
        </EmptyState>
      ) : (
        <>
          <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
            {items.map((p, i) => (
              <div key={p.id} className={i === 0 ? "md:col-span-2 xl:col-span-3" : ""}>
                <JournalCard p={p} large={i === 0} />
              </div>
            ))}
          </div>
          {cursor && (
            <div className="text-center">
              <Button variant="secondary" onClick={loadMore} disabled={more}>
                {more ? t("common.loading") : t("journal.loadMore")}
              </Button>
            </div>
          )}
        </>
      )}
      <p className="text-sm text-muted">{t("journal.reviewNotice")}</p>
    </div>
  );
}

/* ================================================================== reader */

function Blocks({ blocks, locale }: { blocks: JournalBlock[]; locale: string }) {
  const firstParagraph = blocks.findIndex((b) => b.type === "paragraph");
  return (
    <div className="reader mx-auto">
      {blocks.map((b, i) => {
        switch (b.type) {
          case "heading":
            return <h2 key={i}>{b.text}</h2>;
          case "quote":
            return (
              <blockquote key={i}>
                <p className="m-0">{b.text}</p>
              </blockquote>
            );
          case "divider":
            return <hr key={i} />;
          case "image":
            return b.media ? (
              <figure key={i}>
                <MediaFigure m={b.media} locale={locale} size="lg" className="border-0 bg-transparent" />
                {b.caption && <figcaption>{b.caption}</figcaption>}
              </figure>
            ) : null;
          default: {
            const cls = i === firstParagraph ? "dropcap" : undefined;
            return (
              <p key={i} className={cls}>
                {b.text}
              </p>
            );
          }
        }
      })}
    </div>
  );
}

export function SubscribeCard({ handle, name, compact }: { handle: string; name: string; compact?: boolean }) {
  const { t, locale } = useI18n();
  const { me } = useSession();
  const [state, setState] = useState<{ subscribed: boolean; email_digest: boolean; subscriber_count: number } | null>(null);
  const [digest, setDigest] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const toMsg = useNotAvailable();

  useEffect(() => {
    api<Publication>(`/publications/${encodeURIComponent(handle)}?locale=${locale}`)
      .then((p) => {
        setState({ subscribed: p.is_subscribed, email_digest: p.email_digest, subscriber_count: p.subscriber_count });
        setDigest(p.is_subscribed ? p.email_digest : true);
      })
      .catch(() => setState(null));
  }, [handle, locale]);

  async function toggle(subscribe: boolean) {
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ subscribed: boolean; email_digest: boolean; subscriber_count: number }>(`/publications/${encodeURIComponent(handle)}/subscribe`, {
        json: { subscribe, email_digest: digest },
      });
      setState(r);
    } catch (e) {
      setError(toMsg(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={cn("rounded-[var(--radius)] border border-line bg-surface-2/60", compact ? "p-5" : "p-8 text-center")}>
      <div className={cn("sun-rule mb-5", compact ? "w-24" : "mx-auto w-40")} />
      <p className={cn("font-display", compact ? "text-2xl" : "text-3xl")}>{t("journal.subscribeCta", { name })}</p>
      <p className="mt-2 text-muted">{t("journal.subscribeLead")}</p>
      {state && <p className="mt-1 text-sm text-muted">{t("journal.subscribers", { n: state.subscriber_count })}</p>}
      <div className={cn("mt-5 flex flex-wrap items-center gap-4", !compact && "justify-center")}>
        {!me ? (
          <ButtonLink href={`/${locale}/account`}>{t("journal.signInToSubscribe")}</ButtonLink>
        ) : state?.subscribed ? (
          <Button variant="secondary" onClick={() => toggle(false)} disabled={busy}>
            {t("journal.unsubscribe")}
          </Button>
        ) : (
          <Button onClick={() => toggle(true)} disabled={busy}>
            {t("journal.subscribe")}
          </Button>
        )}
        {me && !state?.subscribed && <Checkbox id={`digest-${handle}`} label={t("journal.emailDigest")} checked={digest} onChange={(e) => setDigest(e.target.checked)} />}
      </div>
      {state?.subscribed && (
        <p role="status" className="mt-3 text-sm text-success">
          {t("journal.subscribed")}
        </p>
      )}
      {error && <Alert tone="caution" className="mt-4 text-left">{error}</Alert>}
    </div>
  );
}

export function JournalReader({ id }: { id: string }) {
  const { t, locale } = useI18n();
  const router = useRouter();
  const toMsg = useNotAvailable();
  const [post, setPost] = useState<JournalPost | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [liking, setLiking] = useState(false);

  useEffect(() => {
    api<JournalPost>(`/journal/${encodeURIComponent(id)}?locale=${locale}`)
      .then(setPost)
      .catch((e) => setError(e instanceof ApiError && e.status === 404 && !e.notAvailable ? t("journal.notFound") : toMsg(e)));
  }, [id, locale, t, toMsg]);

  async function like() {
    if (!post) return;
    setLiking(true);
    try {
      const r = await api<{ liked: boolean; like_count: number }>(`/journal/${post.id}/like`, { method: "POST" });
      setPost({ ...post, liked: r.liked, like_count: r.like_count });
    } catch (e) {
      setError(toMsg(e));
    } finally {
      setLiking(false);
    }
  }

  async function remove() {
    if (!post || !window.confirm(t("journal.deleteConfirm"))) return;
    try {
      await api(`/journal/${post.id}`, { method: "DELETE" });
      router.push(`/${locale}/journal`);
    } catch (e) {
      setError(toMsg(e));
    }
  }

  if (error && !post) return <Alert tone="caution">{error}</Alert>;
  if (!post) return <Loading label={t("common.loading")} />;

  return (
    <article className="pb-10">
      <header className="mx-auto max-w-3xl pt-12 text-center">
        <div className="flex flex-wrap justify-center gap-2">
          {post.destination && (
            <Link href={`/${locale}/destinations/${post.destination.slug}`}>
              <Badge tone="forest">{post.destination.name}</Badge>
            </Link>
          )}
          {post.tags.map((tag) => (
            <Badge key={tag}>#{tag}</Badge>
          ))}
          {post.status && post.status !== "published" && <Badge tone="caution">{t(post.status === "pending" ? "journal.statusPending" : "journal.statusOther", { status: post.status })}</Badge>}
        </div>
        <h1 className="reveal mt-6 text-5xl sm:text-6xl">{post.title}</h1>
        {post.subtitle && <p className="reveal reveal-delay mt-5 font-display text-2xl text-muted">{post.subtitle}</p>}
        <div className="mt-6 flex justify-center">
          <Byline p={post} locale={locale} />
        </div>
        <div className="sun-rule mx-auto mt-8 w-48" />
      </header>
      {post.cover && (
        <div className="mx-auto mt-10 max-w-5xl px-0 sm:px-4">
          <MediaFigure m={post.cover} locale={locale} size="lg" />
        </div>
      )}
      <div className="mx-auto mt-12 max-w-3xl px-1">
        <Blocks blocks={post.blocks} locale={locale} />
        <div className="mx-auto mt-10 flex max-w-[68ch] flex-wrap items-center gap-3 border-y border-line py-4">
          <button
            type="button"
            aria-pressed={post.liked}
            onClick={like}
            disabled={liking}
            className={cn("inline-flex min-h-[40px] items-center gap-2 rounded-full border px-4 py-1.5 text-sm", post.liked ? "border-forest bg-forest text-on-forest" : "border-line hover:border-sandstone")}
          >
            <span aria-hidden="true">{post.liked ? "♥" : "♡"}</span> {post.liked ? t("journal.liked") : t("journal.like")} · {post.like_count}
          </button>
          <a href="#comments" className="inline-flex min-h-[40px] items-center rounded-full border border-line px-4 py-1.5 text-sm">
            {t("journal.commentsCount", { n: post.comment_count })}
          </a>
          <ShareButton title={post.title} text={post.subtitle} path={`/${locale}/journal/${post.id}`} />
          <ReportButton path={`/journal/${post.id}/report`} className="ml-auto" />
        </div>
        {post.is_author && (
          <div className="mx-auto mt-4 flex max-w-[68ch] flex-wrap gap-3">
            <ButtonLink variant="secondary" size="sm" href={`/${locale}/journal/${post.id}/edit`}>
              {t("journal.edit")}
            </ButtonLink>
            <Button variant="ghost" size="sm" onClick={remove}>
              {t("journal.delete")}
            </Button>
          </div>
        )}
        {error && <Alert tone="caution" className="mx-auto mt-4 max-w-[68ch]">{error}</Alert>}
        <div className="mx-auto mt-12 max-w-[68ch]">
          <SubscribeCard handle={post.publication.handle} name={post.publication.name} />
        </div>
        <Comments postId={post.id} />
      </div>
    </article>
  );
}

/* ================================================================== comments (one level of replies) */

function Comments({ postId }: { postId: string }) {
  const { t, locale } = useI18n();
  const { me } = useSession();
  const toMsg = useNotAvailable();
  const [items, setItems] = useState<JournalComment[] | null>(null);
  const [body, setBody] = useState("");
  const [replyTo, setReplyTo] = useState<JournalComment | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const load = useCallback(() => {
    api<JournalComment[]>(`/journal/${postId}/comments`)
      .then(setItems)
      .catch((e) => {
        setItems([]);
        setError(toMsg(e));
      });
  }, [postId, toMsg]);
  useEffect(load, [load]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!body.trim()) return;
    setError(null);
    try {
      const r = await api<{ id: string; status: "visible" | "pending" }>(`/journal/${postId}/comments`, { json: { body, parent_id: replyTo?.id } });
      setBody("");
      setReplyTo(null);
      setNotice(r.status === "pending" ? t("journal.commentPending") : null);
      load();
    } catch (err) {
      setError(toMsg(err));
    }
  }

  async function remove(id: string) {
    try {
      await api(`/journal-comments/${id}`, { method: "DELETE" });
      load();
    } catch (err) {
      setError(toMsg(err));
    }
  }

  const roots = (items ?? []).filter((c) => !c.parent_id);
  const replies = (id: string) => (items ?? []).filter((c) => c.parent_id === id);
  const one = (c: JournalComment, child?: boolean): ReactNode => (
    <li key={c.id} className={cn("py-4", child && "ml-6 border-l-2 border-line pl-5")}>
      <p className="text-sm">
        <Link href={`/${locale}/creators/${c.author.handle}`} className="font-semibold hover:underline">
          {c.author.display_name}
        </Link>{" "}
        <span className="text-muted">· {formatDateTime(c.created_at, locale)}</span>
      </p>
      <p className="mt-1 whitespace-pre-line">{c.body}</p>
      <div className="mt-1 flex gap-3 text-sm">
        {me && !child && (
          <button
            type="button"
            className="text-muted underline-offset-4 hover:underline"
            onClick={() => {
              setReplyTo(c);
              inputRef.current?.focus();
            }}
          >
            {t("journal.reply")}
          </button>
        )}
        {c.can_delete && (
          <button type="button" className="text-muted underline-offset-4 hover:underline" onClick={() => remove(c.id)}>
            {t("journal.delete")}
          </button>
        )}
      </div>
      {!child && replies(c.id).length > 0 && <ul>{replies(c.id).map((r) => one(r, true))}</ul>}
    </li>
  );

  return (
    <section id="comments" aria-labelledby="comments-h" className="mx-auto mt-14 max-w-[68ch]">
      <h2 id="comments-h" className="text-3xl">
        {t("journal.commentsTitle")}
      </h2>
      {me ? (
        <form onSubmit={submit} className="mt-5 space-y-3">
          {replyTo && (
            <p className="text-sm text-muted">
              {t("journal.replyingTo", { name: replyTo.author.display_name })}{" "}
              <button type="button" className="underline" onClick={() => setReplyTo(null)}>
                {t("common.cancel")}
              </button>
            </p>
          )}
          <label htmlFor="comment-body" className="sr-only">
            {t("journal.commentPlaceholder")}
          </label>
          <textarea
            ref={inputRef}
            id="comment-body"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            maxLength={1500}
            rows={3}
            placeholder={t("journal.commentPlaceholder")}
            className="w-full rounded-lg border border-line bg-surface px-3.5 py-2.5"
          />
          <Button type="submit" size="sm" disabled={!body.trim()}>
            {t("journal.commentPost")}
          </Button>
        </form>
      ) : (
        <p className="mt-4 text-muted">
          <Link href={`/${locale}/account`} className="underline">
            {t("common.signIn")}
          </Link>{" "}
          — {t("journal.signInToComment")}
        </p>
      )}
      {notice && (
        <p role="status" className="mt-3 text-sm text-muted">
          {notice}
        </p>
      )}
      {error && <Alert tone="caution" className="mt-3">{error}</Alert>}
      {items === null ? <Loading label={t("common.loading")} /> : roots.length === 0 ? <p className="mt-6 text-muted">{t("journal.noComments")}</p> : <ul className="mt-4 divide-y divide-line">{roots.map((c) => one(c))}</ul>}
    </section>
  );
}

/* ================================================================== editor */

interface EditorBlock {
  key: string;
  type: BlockType;
  text: string;
  caption: string;
  media: MediaItem | null;
}
interface Draft {
  title: string;
  subtitle: string;
  blocks: EditorBlock[];
  cover: MediaItem | null;
  destination: string;
  tags: string;
  notify: boolean;
}

const newKey = () => Math.random().toString(36).slice(2, 10);
const blank = (type: BlockType): EditorBlock => ({ key: newKey(), type, text: "", caption: "", media: null });
const EMPTY_DRAFT: Draft = { title: "", subtitle: "", blocks: [blank("paragraph")], cover: null, destination: "", tags: "", notify: true };

function readDraft(key: string): Draft | null {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as Draft) : null;
  } catch {
    return null;
  }
}

export function JournalEditor({ id }: { id?: string }) {
  const { t, locale } = useI18n();
  const { me, loading } = useSession();
  const router = useRouter();
  const toMsg = useNotAvailable();
  const storageKey = `vt_journal_draft:${id ?? "new"}`;
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [restored, setRestored] = useState(false);
  const [preview, setPreview] = useState(false);
  const [rights, setRights] = useState(false);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [destinations, setDestinations] = useState<Pick<Destination, "slug" | "name">[]>([]);
  const ready = useRef(false);

  useEffect(() => {
    api<{ items: Destination[] }>(`/destinations?locale=${locale}&limit=100`)
      .then((r) => setDestinations(r.items.map(({ slug, name }) => ({ slug, name }))))
      .catch(() => undefined);
  }, [locale]);

  // Load: local draft first (autosave), otherwise the existing post when editing.
  useEffect(() => {
    const local = readDraft(storageKey);
    if (local) {
      queueMicrotask(() => {
        setDraft(local);
        setRestored(true);
        ready.current = true;
      });
      return;
    }
    if (!id) {
      ready.current = true;
      return;
    }
    api<JournalPost>(`/journal/${encodeURIComponent(id)}?locale=${locale}`)
      .then((p) => {
        setDraft({
          title: p.title,
          subtitle: p.subtitle,
          cover: p.cover,
          destination: p.destination?.slug ?? "",
          tags: p.tags.join(", "),
          notify: false,
          blocks: p.blocks.map((b) => ({ key: newKey(), type: b.type, text: b.text ?? "", caption: b.caption ?? "", media: b.media ?? null })),
        });
        ready.current = true;
      })
      .catch((e) => setError(toMsg(e)));
  }, [id, locale, storageKey, toMsg]);

  // Autosave (debounced) to this browser only.
  useEffect(() => {
    if (!ready.current) return;
    const h = setTimeout(() => {
      try {
        localStorage.setItem(storageKey, JSON.stringify(draft));
      } catch {
        /* storage full or blocked */
      }
    }, 600);
    return () => clearTimeout(h);
  }, [draft, storageKey]);

  const set = (patch: Partial<Draft>) => setDraft((d) => ({ ...d, ...patch }));
  const setBlock = (key: string, patch: Partial<EditorBlock>) => setDraft((d) => ({ ...d, blocks: d.blocks.map((b) => (b.key === key ? { ...b, ...patch } : b)) }));
  const move = (i: number, dir: -1 | 1) =>
    setDraft((d) => {
      const j = i + dir;
      if (j < 0 || j >= d.blocks.length) return d;
      const blocks = [...d.blocks];
      [blocks[i], blocks[j]] = [blocks[j], blocks[i]];
      return { ...d, blocks };
    });

  async function upload(file: File | undefined, target: "cover" | string) {
    if (!file) return;
    if (!rights) {
      setError(t("journal.rightsFirst"));
      return;
    }
    setUploading(target);
    setError(null);
    try {
      const m = await uploadImage(file, true);
      if (target === "cover") set({ cover: m });
      else setBlock(target, { media: m });
    } catch (e) {
      setError(toMsg(e));
    } finally {
      setUploading(null);
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!consent) {
      setError(t("journal.consentRequired"));
      return;
    }
    const blocks = draft.blocks
      .filter((b) => b.type === "divider" || (b.type === "image" ? !!b.media : b.text.trim()))
      .map((b) => ({ type: b.type, text: b.type === "image" || b.type === "divider" ? undefined : b.text, media_id: b.media?.id, caption: b.caption || undefined }));
    if (!draft.title.trim() || blocks.length === 0) {
      setError(t("journal.needContent"));
      return;
    }
    const body = {
      title: draft.title.trim(),
      subtitle: draft.subtitle.trim(),
      blocks,
      cover_media_id: draft.cover?.id,
      destination_slug: draft.destination || undefined,
      tags: draft.tags.split(",").map((x) => x.trim().replace(/^#/, "").toLowerCase()).filter(Boolean).slice(0, 8),
      locale,
      consent_publish: true,
      notify_subscribers: draft.notify,
    };
    setBusy(true);
    try {
      const r = id
        ? await api<{ id: string; message?: string }>(`/journal/${encodeURIComponent(id)}`, { method: "PUT", json: body })
        : await api<{ id: string; message?: string }>("/journal", { json: body });
      try {
        localStorage.removeItem(storageKey);
      } catch {
        /* ignore */
      }
      setDone(r.message ?? t("journal.submitted"));
      router.push(`/${locale}/journal/${r.id ?? id}`);
    } catch (err) {
      setError(toMsg(err));
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <Loading label={t("common.loading")} />;
  if (!me) {
    return (
      <EmptyState title={t("journal.write")} action={<ButtonLink href={`/${locale}/account`}>{t("common.signIn")}</ButtonLink>}>
        {t("journal.signInToWrite")}
      </EmptyState>
    );
  }

  const blockLabel = (b: BlockType) => t(`journal.block.${b}`);

  return (
    <form onSubmit={submit} className="mx-auto max-w-3xl space-y-8">
      <Alert tone="info">{t("journal.reviewNotice")}</Alert>
      {restored && (
        <Alert tone="info">
          {t("journal.draftRestored")}{" "}
          <button
            type="button"
            className="underline"
            onClick={() => {
              localStorage.removeItem(storageKey);
              setDraft(EMPTY_DRAFT);
              setRestored(false);
            }}
          >
            {t("journal.clearDraft")}
          </button>
        </Alert>
      )}
      <div className="flex flex-wrap gap-2" role="group" aria-label={t("journal.modeLabel")}>
        <button type="button" aria-pressed={!preview} onClick={() => setPreview(false)} className={cn("min-h-[44px] rounded-full border px-4 py-2 text-sm", !preview ? "border-forest bg-forest text-on-forest" : "border-line")}>
          {t("journal.editMode")}
        </button>
        <button type="button" aria-pressed={preview} onClick={() => setPreview(true)} className={cn("min-h-[44px] rounded-full border px-4 py-2 text-sm", preview ? "border-forest bg-forest text-on-forest" : "border-line")}>
          {t("journal.preview")}
        </button>
      </div>

      {preview ? (
        <div className="rounded-[var(--radius)] border border-line bg-surface px-5 py-10">
          <h1 className="text-center text-5xl">{draft.title || t("journal.fieldTitle")}</h1>
          {draft.subtitle && <p className="mt-4 text-center font-display text-2xl text-muted">{draft.subtitle}</p>}
          {draft.cover && <MediaFigure m={draft.cover} locale={locale} size="lg" className="mx-auto mt-8 max-w-3xl" />}
          <div className="mt-10">
            <Blocks blocks={draft.blocks.map((b) => ({ type: b.type, text: b.text, caption: b.caption, media: b.media }))} locale={locale} />
          </div>
        </div>
      ) : (
        <>
          <div className="space-y-4">
            <label htmlFor="j-title" className="sr-only">
              {t("journal.fieldTitle")}
            </label>
            <input
              id="j-title"
              value={draft.title}
              onChange={(e) => set({ title: e.target.value })}
              maxLength={160}
              placeholder={t("journal.fieldTitle")}
              className="w-full border-0 border-b border-line bg-transparent pb-3 font-display text-4xl outline-none focus:border-forest sm:text-5xl"
              required
            />
            <label htmlFor="j-subtitle" className="sr-only">
              {t("journal.fieldSubtitle")}
            </label>
            <input
              id="j-subtitle"
              value={draft.subtitle}
              onChange={(e) => set({ subtitle: e.target.value })}
              maxLength={240}
              placeholder={t("journal.fieldSubtitle")}
              className="w-full border-0 border-b border-line bg-transparent pb-3 font-display text-2xl text-muted outline-none focus:border-forest"
            />
          </div>

          <Checkbox id="j-rights" label={t("journal.rightsConfirm")} checked={rights} onChange={(e) => setRights(e.target.checked)} />

          <fieldset className="space-y-3 rounded-[var(--radius)] border border-line bg-surface p-5">
            <legend className="px-1 text-sm font-semibold">{t("journal.cover")}</legend>
            {draft.cover ? (
              <div className="space-y-2">
                <MediaFigure m={draft.cover} locale={locale} />
                <Button variant="ghost" size="sm" onClick={() => set({ cover: null })}>
                  {t("journal.remove")}
                </Button>
              </div>
            ) : (
              <label className="block text-sm">
                <span className="mb-1 block text-muted">{t("journal.coverUpload")}</span>
                <input type="file" accept="image/jpeg,image/png,image/webp" disabled={!rights || uploading === "cover"} onChange={(e) => upload(e.target.files?.[0], "cover")} />
              </label>
            )}
            {uploading === "cover" && <Loading label={t("journal.uploading")} />}
          </fieldset>

          <section aria-label={t("journal.blocks")} className="space-y-4">
            {draft.blocks.map((b, i) => (
              <div key={b.key} className="group rounded-[var(--radius)] border border-line bg-surface p-4">
                <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
                  <Badge>{blockLabel(b.type)}</Badge>
                  <span className="ml-auto flex gap-1">
                    <button type="button" className="rounded-full border border-line px-2.5 py-1" onClick={() => move(i, -1)} disabled={i === 0} aria-label={`${t("journal.moveUp")}: ${blockLabel(b.type)} ${i + 1}`}>
                      ↑
                    </button>
                    <button type="button" className="rounded-full border border-line px-2.5 py-1" onClick={() => move(i, 1)} disabled={i === draft.blocks.length - 1} aria-label={`${t("journal.moveDown")}: ${blockLabel(b.type)} ${i + 1}`}>
                      ↓
                    </button>
                    <button type="button" className="rounded-full border border-line px-2.5 py-1" onClick={() => setDraft((d) => ({ ...d, blocks: d.blocks.filter((x) => x.key !== b.key) }))} aria-label={`${t("journal.remove")}: ${blockLabel(b.type)} ${i + 1}`}>
                      ✕
                    </button>
                  </span>
                </div>
                {b.type === "divider" ? (
                  <div className="sun-rule my-3" />
                ) : b.type === "image" ? (
                  <div className="space-y-2">
                    {b.media ? (
                      <MediaFigure m={b.media} locale={locale} />
                    ) : (
                      <label className="block text-sm">
                        <span className="mb-1 block text-muted">{t("journal.imageUpload")}</span>
                        <input type="file" accept="image/jpeg,image/png,image/webp" disabled={!rights || uploading === b.key} onChange={(e) => upload(e.target.files?.[0], b.key)} />
                      </label>
                    )}
                    {uploading === b.key && <Loading label={t("journal.uploading")} />}
                    <Input id={`cap-${b.key}`} label={t("journal.caption")} value={b.caption} onChange={(e) => setBlock(b.key, { caption: e.target.value })} maxLength={240} />
                  </div>
                ) : (
                  <>
                    <label htmlFor={`blk-${b.key}`} className="sr-only">
                      {blockLabel(b.type)} {i + 1}
                    </label>
                    <textarea
                      id={`blk-${b.key}`}
                      value={b.text}
                      onChange={(e) => setBlock(b.key, { text: e.target.value })}
                      maxLength={b.type === "heading" ? 160 : 6000}
                      rows={b.type === "paragraph" ? 5 : 2}
                      className={cn(
                        "w-full resize-y rounded-lg border border-transparent bg-transparent px-1 py-1 focus:border-line",
                        b.type === "heading" && "font-display text-3xl",
                        b.type === "quote" && "border-l-[3px] border-l-terracotta pl-4 font-display text-2xl italic",
                        b.type === "paragraph" && "text-lg leading-8",
                      )}
                    />
                  </>
                )}
              </div>
            ))}
            <div className="flex flex-wrap gap-2" role="group" aria-label={t("journal.addBlock")}>
              {(["paragraph", "heading", "quote", "image", "divider"] as BlockType[]).map((type) => (
                <button key={type} type="button" onClick={() => setDraft((d) => ({ ...d, blocks: [...d.blocks, blank(type)] }))} className="min-h-[40px] rounded-full border border-dashed border-line px-4 py-1.5 text-sm hover:border-forest">
                  + {blockLabel(type)}
                </button>
              ))}
            </div>
          </section>

          <div className="grid gap-4 sm:grid-cols-2">
            <Select id="j-destination" label={t("journal.destination")} value={draft.destination} onChange={(e) => set({ destination: e.target.value })} options={[{ value: "", label: t("journal.anyDestination") }, ...destinations.map((d) => ({ value: d.slug, label: d.name }))]} />
            <Input id="j-tags" label={t("journal.tags")} hint={t("journal.tagsHint")} value={draft.tags} onChange={(e) => set({ tags: e.target.value })} maxLength={200} />
          </div>
        </>
      )}

      <div className="space-y-3 rounded-[var(--radius)] border border-line bg-surface-2/60 p-5">
        <Checkbox id="j-notify" label={t("journal.notify")} checked={draft.notify} onChange={(e) => set({ notify: e.target.checked })} />
        <Checkbox id="j-consent" label={t("journal.consent")} checked={consent} onChange={(e) => setConsent(e.target.checked)} />
      </div>
      {error && <Alert tone="danger">{error}</Alert>}
      {done && <Alert tone="success">{done}</Alert>}
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" size="lg" disabled={busy || !!uploading}>
          {busy ? t("journal.submitting") : t("journal.submit")}
        </Button>
        <span className="text-sm text-muted">{t("journal.autosaveNote")}</span>
      </div>
    </form>
  );
}

/* ================================================================== publication */

export function PublicationView({ handle }: { handle: string }) {
  const { t, locale } = useI18n();
  const toMsg = useNotAvailable();
  const [pub, setPub] = useState<Publication | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api<Publication>(`/publications/${encodeURIComponent(handle)}?locale=${locale}`)
      .then(setPub)
      .catch((e) => setError(e instanceof ApiError && e.status === 404 && !e.notAvailable ? t("journal.pubNotFound") : toMsg(e)));
  }, [handle, locale, t, toMsg]);
  if (error) return <Alert tone="caution">{error}</Alert>;
  if (!pub) return <Loading label={t("common.loading")} />;
  return (
    <div className="space-y-12">
      <header className="overflow-hidden rounded-[var(--radius)] border border-line bg-surface">
        <div className="aspect-[21/7] bg-surface-2">
          <Cover media={pub.cover} seed={pub.handle} locale={locale} />
        </div>
        <div className="p-8 text-center">
          <h1 className="text-5xl">{pub.name}</h1>
          {pub.tagline && <p className="mt-3 font-display text-2xl text-muted">{pub.tagline}</p>}
          <p className="mt-2 text-sm text-muted">
            {t("journal.by", { name: pub.author.display_name })} · {t("journal.subscribers", { n: pub.subscriber_count })}
          </p>
          {pub.about && <p className="mx-auto mt-5 max-w-2xl whitespace-pre-line">{pub.about}</p>}
        </div>
      </header>
      <SubscribeCard handle={pub.handle} name={pub.name} />
      {pub.posts.length === 0 ? (
        <EmptyState title={t("journal.emptyTitle")}>{t("journal.pubEmpty")}</EmptyState>
      ) : (
        <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
          {pub.posts.map((p) => (
            <JournalCard key={p.id} p={p} />
          ))}
        </div>
      )}
    </div>
  );
}

export function PublicationSettings() {
  const { t, locale } = useI18n();
  const { me } = useSession();
  const toMsg = useNotAvailable();
  const [handle, setHandle] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", tagline: "", about: "" });
  const [cover, setCover] = useState<MediaItem | null>(null);
  const [rights, setRights] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!me) return;
    api<{ handle: string }>("/me/profile")
      .then((p) => {
        setHandle(p.handle);
        return api<Publication>(`/publications/${encodeURIComponent(p.handle)}?locale=${locale}`);
      })
      .then((pub) => {
        setForm({ name: pub.name, tagline: pub.tagline, about: pub.about });
        setCover(pub.cover);
      })
      .catch(() => undefined);
  }, [me, locale]);

  if (!me) return null;
  return (
    <section className="rounded-[var(--radius)] border border-line bg-surface p-6" aria-labelledby="pub-settings">
      <h2 id="pub-settings" className="text-3xl">
        {t("journal.settingsTitle")}
      </h2>
      <p className="mt-2 text-sm text-muted">{t("journal.settingsLead")}</p>
      <form
        className="mt-5 space-y-4"
        onSubmit={async (e) => {
          e.preventDefault();
          setMsg(null);
          setError(null);
          try {
            await api("/me/publication", { method: "PUT", json: { ...form, cover_media_id: cover?.id } });
            setMsg(t("journal.settingsSaved"));
          } catch (err) {
            setError(toMsg(err));
          }
        }}
      >
        <Input id="pub-name" label={t("journal.pubName")} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} maxLength={120} required />
        <Input id="pub-tagline" label={t("journal.pubTagline")} value={form.tagline} onChange={(e) => setForm({ ...form, tagline: e.target.value })} maxLength={200} />
        <Textarea id="pub-about" label={t("journal.pubAbout")} value={form.about} onChange={(e) => setForm({ ...form, about: e.target.value })} maxLength={3000} />
        <Checkbox id="pub-rights" label={t("journal.rightsConfirm")} checked={rights} onChange={(e) => setRights(e.target.checked)} />
        <label className="block text-sm">
          <span className="mb-1 block text-muted">{t("journal.coverUpload")}</span>
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            disabled={!rights}
            onChange={async (e) => {
              const f = e.target.files?.[0];
              if (!f) return;
              try {
                setCover(await uploadImage(f, true));
              } catch (err) {
                setError(toMsg(err));
              }
            }}
          />
        </label>
        {cover && <MediaFigure m={cover} locale={locale} className="max-w-md" />}
        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit">{t("journal.settingsSave")}</Button>
          {handle && (
            <Link href={`/${locale}/journal/p/${handle}`} className="text-sm underline">
              {t("journal.viewPublication")}
            </Link>
          )}
        </div>
        {msg && <Alert tone="success">{msg}</Alert>}
        {error && <Alert tone="caution">{error}</Alert>}
      </form>
    </section>
  );
}
