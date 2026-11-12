"use client";

import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { Alert, Button, ButtonLink, EmptyState, Loading, cn } from "@/components/ui";
import { api, ApiError, errorMessage } from "@/lib/api";
import { formatDate, formatEthiopian, formatTime } from "@/lib/format";
import type { Channel, Space, SpaceMessage } from "@/lib/types";
import { ReportButton } from "./journal";
import { useI18n, useSession } from "./providers";

export const EMOJIS = ["👍", "❤️", "🙏", "😂", "😮", "🎉", "🌄", "☕"] as const;
const GROUP_WINDOW_MS = 5 * 60_000;
const POLL_MS = 4000;
const READY_TIMEOUT_MS = 6_000;
const GUIDELINES_KEY = "vt_spaces_guidelines_v1";

/* ================================================================== data */

function useSpaces() {
  const { locale, t } = useI18n();
  const { me } = useSession();
  const [spaces, setSpaces] = useState<Space[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const reload = useCallback(() => {
    api<Space[]>(`/spaces?locale=${locale}`)
      .then((s) => {
        setSpaces(s);
        setError(null);
      })
      .catch((e) => {
        setSpaces([]);
        setError(e instanceof ApiError && e.notAvailable ? t("common.notAvailableYet") : errorMessage(e));
      });
  }, [locale, t]);
  useEffect(reload, [reload, me?.id]);
  return { spaces, error, reload };
}

/** Merge messages by id, keeping ascending order. */
function merge(list: SpaceMessage[], incoming: SpaceMessage[]): SpaceMessage[] {
  const byId = new Map(list.map((m) => [m.id, m]));
  for (const m of incoming) byId.set(m.id, m);
  return [...byId.values()].sort((a, b) => a.id - b.id);
}

/* ================================================================== layout */

function SpaceIcon({ space, active }: { space: Space; active?: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "flex h-12 w-12 items-center justify-center overflow-hidden rounded-2xl border text-xl transition-[border-radius]",
        active ? "rounded-xl border-forest bg-forest text-on-forest" : "border-line bg-surface hover:rounded-xl",
      )}
    >
      {space.icon && !space.icon.startsWith("/") ? space.icon : space.name.slice(0, 1)}
    </span>
  );
}

function GuidelinesBanner() {
  const { t } = useI18n();
  const [show, setShow] = useState(false);
  useEffect(() => {
    try {
      if (!localStorage.getItem(GUIDELINES_KEY)) queueMicrotask(() => setShow(true));
    } catch {
      /* storage blocked: show nothing */
    }
  }, []);
  if (!show) return null;
  return (
    <div role="note" className="mb-4 rounded-[var(--radius)] border border-line bg-surface-2/70 p-5">
      <p className="font-display text-2xl">{t("spaces.guidelinesTitle")}</p>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
        <li>{t("spaces.guideline1")}</li>
        <li>{t("spaces.guideline2")}</li>
        <li>{t("spaces.guideline3")}</li>
        <li>{t("spaces.guideline4")}</li>
      </ul>
      <Button
        size="sm"
        className="mt-3"
        onClick={() => {
          try {
            localStorage.setItem(GUIDELINES_KEY, "1");
          } catch {
            /* ignore */
          }
          setShow(false);
        }}
      >
        {t("spaces.guidelinesAccept")}
      </Button>
    </div>
  );
}

export function SpacesApp({ spaceSlug, channelSlug }: { spaceSlug?: string; channelSlug?: string }) {
  const { t, locale } = useI18n();
  const { spaces, error, reload } = useSpaces();
  const space = spaces?.find((s) => s.slug === spaceSlug) ?? null;
  const channel = space?.channels.find((c) => c.slug === channelSlug) ?? null;

  if (spaces === null) return <Loading label={t("common.loading")} />;
  if (error) return <Alert tone="caution">{error}</Alert>;
  if (spaces.length === 0) return <EmptyState title={t("spaces.emptyTitle")}>{t("spaces.empty")}</EmptyState>;

  return (
    <>
      <GuidelinesBanner />
      <div className="overflow-hidden rounded-[var(--radius)] border border-line bg-surface shadow-[var(--shadow)] lg:grid lg:h-[min(78vh,820px)] lg:grid-cols-[84px_260px_1fr]">
        {/* Rail */}
        <nav aria-label={t("spaces.railLabel")} className={cn("border-b border-line bg-surface-2/70 lg:border-b-0 lg:border-r", channel && "hidden lg:block")}>
          <ul className="flex gap-3 overflow-x-auto p-3 lg:flex-col lg:items-center lg:overflow-y-auto lg:py-5">
            <li className="hidden lg:block">
              <Link href={`/${locale}/spaces`} aria-label={t("spaces.home")} className="block">
                <span className="flex h-12 w-12 items-center justify-center overflow-hidden rounded-2xl border border-line bg-[#f8f2e9]">
                  <Image src="/brand/emblem-256.webp" alt="" width={48} height={48} unoptimized />
                </span>
              </Link>
            </li>
            {spaces.map((s) => {
              const first = s.channels[0];
              return (
                <li key={s.slug}>
                  <Link
                    href={first ? `/${locale}/spaces/${s.slug}/${first.slug}` : `/${locale}/spaces`}
                    aria-current={s.slug === spaceSlug ? "page" : undefined}
                    aria-label={s.name}
                    title={s.name}
                    className="block"
                  >
                    <SpaceIcon space={s} active={s.slug === spaceSlug} />
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* Channel list */}
        <div className={cn("border-b border-line lg:flex lg:flex-col lg:border-b-0 lg:border-r", channel && "hidden lg:flex")}>
          {space ? (
            <SpaceHeaderAndChannels space={space} activeChannel={channelSlug} onChanged={reload} />
          ) : (
            <SpaceDirectory spaces={spaces} />
          )}
        </div>

        {/* Chat */}
        <section aria-label={channel ? `#${channel.name}` : t("spaces.title")} className={cn("flex min-h-[70vh] flex-col lg:min-h-0", !channel && "hidden lg:flex")}>
          {space && channel ? (
            <ChannelView key={`${space.slug}/${channel.slug}`} space={space} channel={channel} onJoined={reload} />
          ) : (
            <div className="m-auto max-w-md p-10 text-center">
              <Image src="/brand/emblem-256.webp" alt="" width={120} height={120} unoptimized className="mx-auto rounded-2xl" />
              <p className="mt-4 font-display text-3xl">{t("spaces.pickTitle")}</p>
              <p className="mt-2 text-muted">{t("spaces.pickLead")}</p>
            </div>
          )}
        </section>
      </div>
    </>
  );
}

function SpaceDirectory({ spaces }: { spaces: Space[] }) {
  const { t, locale } = useI18n();
  return (
    <div className="p-4 lg:overflow-y-auto">
      <p className="px-1 text-xs font-semibold uppercase tracking-[0.18em] text-earth">{t("spaces.directory")}</p>
      <ul className="mt-3 space-y-3">
        {spaces.map((s) => (
          <li key={s.slug}>
            <Link href={s.channels[0] ? `/${locale}/spaces/${s.slug}/${s.channels[0].slug}` : `/${locale}/spaces`} className="flex gap-3 rounded-xl border border-line p-3 hover:border-sandstone">
              <SpaceIcon space={s} />
              <span>
                <span className="block font-medium">{s.name}</span>
                <span className="block text-sm text-muted">{s.description}</span>
                <span className="block text-xs text-muted">{t("spaces.members", { n: s.member_count })}</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

function SpaceHeaderAndChannels({ space, activeChannel, onChanged }: { space: Space; activeChannel?: string; onChanged: () => void }) {
  const { t, locale } = useI18n();
  const { me } = useSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function toggle() {
    setBusy(true);
    setError(null);
    try {
      await api(`/spaces/${space.slug}/${space.is_member ? "leave" : "join"}`, { method: "POST" });
      onChanged();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="border-b border-line p-4">
        <Link href={`/${locale}/spaces`} className="mb-2 inline-block text-sm text-muted underline lg:hidden">
          ← {t("spaces.allSpaces")}
        </Link>
        <h2 className="text-2xl">{space.name}</h2>
        <p className="mt-1 text-sm text-muted">{space.description}</p>
        <p className="mt-1 text-xs text-muted">
          {t("spaces.members", { n: space.member_count })}
          {space.my_role === "moderator" && <> · {t("spaces.youModerate")}</>}
        </p>
        {me && (
          <Button size="sm" variant={space.is_member ? "ghost" : "primary"} className="mt-3" onClick={toggle} disabled={busy}>
            {space.is_member ? t("spaces.leave") : t("spaces.join")}
          </Button>
        )}
        {error && <Alert tone="caution" className="mt-2">{error}</Alert>}
      </div>
      <nav aria-label={t("spaces.channelsLabel", { space: space.name })} className="flex-1 overflow-y-auto p-3">
        <ul className="space-y-1">
          {space.channels.map((c) => (
            <li key={c.slug}>
              <Link
                href={`/${locale}/spaces/${space.slug}/${c.slug}`}
                aria-current={c.slug === activeChannel ? "page" : undefined}
                className={cn("flex items-center gap-2 rounded-lg px-3 py-2 text-[0.95rem]", c.slug === activeChannel ? "bg-surface-2 font-medium" : "text-muted hover:bg-surface-2 hover:text-ink")}
              >
                <span aria-hidden="true" className="text-muted">
                  {c.kind === "announcements" ? "📣" : "#"}
                </span>
                {c.name}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </>
  );
}

/* ================================================================== channel view */

function dayKey(iso: string) {
  return iso.slice(0, 10);
}

function ChannelView({ space, channel, onJoined }: { space: Space; channel: Channel; onJoined: () => void }) {
  const { t, locale } = useI18n();
  const { me } = useSession();
  const base = `/spaces/${space.slug}/channels/${channel.slug}`;
  const [messages, setMessages] = useState<SpaceMessage[] | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState<"connecting" | "live" | "polling">("connecting");
  const [unseen, setUnseen] = useState(0);
  const [replyTo, setReplyTo] = useState<SpaceMessage | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const atBottom = useRef(true);
  const lastId = useRef(0);

  const applyIncoming = useCallback((incoming: SpaceMessage[]) => {
    if (!incoming.length) return;
    lastId.current = Math.max(lastId.current, ...incoming.map((m) => m.id));
    setMessages((cur) => merge(cur ?? [], incoming));
    if (!atBottom.current) setUnseen((n) => n + incoming.length);
  }, []);

  // Initial page
  useEffect(() => {
    let cancelled = false;
    api<{ items: SpaceMessage[]; has_more: boolean }>(`${base}/messages?limit=50`)
      .then((r) => {
        if (cancelled) return;
        lastId.current = r.items.reduce((m, x) => Math.max(m, x.id), 0);
        setMessages(r.items);
        setHasMore(r.has_more);
      })
      .catch((e) => {
        if (cancelled) return;
        setMessages([]);
        setError(e instanceof ApiError && e.notAvailable ? t("common.notAvailableYet") : errorMessage(e));
      });
    return () => {
      cancelled = true;
    };
  }, [base, t]);

  // Live updates: SSE first; polling fallback after repeated errors or when no `ready` event arrives.
  useEffect(() => {
    if (messages === null || error) return;
    let es: EventSource | null = null;
    let poll: ReturnType<typeof setInterval> | null = null;
    let failures = 0;
    let closed = false;
    const startPolling = () => {
      setLive("polling");
      poll = setInterval(async () => {
        try {
          const r = await api<{ items: SpaceMessage[] }>(`${base}/messages?after=${lastId.current}&limit=100`);
          applyIncoming(r.items);
        } catch {
          /* keep trying quietly */
        }
      }, POLL_MS);
    };
    const connect = () => {
      if (closed) return;
      if (typeof EventSource === "undefined") return startPolling();
      es = new EventSource(`/api${base}/stream?after=${lastId.current}`);
      // An open connection is not proof of delivery: a buffering/compressing proxy can hold events back.
      // Only the server's immediate `ready` event marks the stream live; otherwise fall back to polling.
      const watchdog = setTimeout(() => {
        if (closed) return;
        es?.close();
        startPolling();
      }, READY_TIMEOUT_MS);
      es.addEventListener("ready", () => {
        clearTimeout(watchdog);
        failures = 0;
        setLive("live");
      });
      es.addEventListener("message", (ev) => {
        try {
          applyIncoming([JSON.parse((ev as MessageEvent).data) as SpaceMessage]);
        } catch {
          /* ignore malformed */
        }
      });
      es.addEventListener("update", (ev) => {
        try {
          const m = JSON.parse((ev as MessageEvent).data) as SpaceMessage;
          setMessages((cur) => (cur ? merge(cur, [m]) : cur));
        } catch {
          /* ignore malformed */
        }
      });
      // The server ends each stream after ~55 s with `reconnect {after}`; resume from the newest id we hold.
      es.addEventListener("reconnect", (ev) => {
        try {
          const after = Number((JSON.parse((ev as MessageEvent).data) as { after?: number }).after);
          if (Number.isFinite(after)) lastId.current = Math.max(lastId.current, after);
        } catch {
          /* ignore malformed */
        }
        es?.close();
        setTimeout(connect, 250);
      });
      es.onerror = () => {
        clearTimeout(watchdog);
        es?.close();
        failures += 1;
        if (failures >= 3) startPolling();
        else setTimeout(connect, 1500 * failures);
      };
    };
    connect();
    return () => {
      closed = true;
      es?.close();
      if (poll) clearInterval(poll);
    };
    // messages === null only toggles once; re-running on every message would reconnect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [base, applyIncoming, messages === null, error]);

  // Keep pinned to the bottom when the reader is there.
  useLayoutEffect(() => {
    const el = listRef.current;
    if (el && atBottom.current) el.scrollTop = el.scrollHeight;
  }, [messages]);

  function onScroll() {
    const el = listRef.current;
    if (!el) return;
    atBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    if (atBottom.current) setUnseen(0);
  }

  async function loadOlder() {
    if (!messages?.length) return;
    const el = listRef.current;
    const prevHeight = el?.scrollHeight ?? 0;
    try {
      const r = await api<{ items: SpaceMessage[]; has_more: boolean }>(`${base}/messages?before=${messages[0].id}&limit=50`);
      setMessages((cur) => merge(cur ?? [], r.items));
      setHasMore(r.has_more);
      requestAnimationFrame(() => {
        if (el) el.scrollTop = el.scrollHeight - prevHeight;
      });
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  function jumpToLatest() {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
    setUnseen(0);
  }

  const rows = useMemo(() => {
    const out: ({ kind: "day"; key: string; iso: string } | { kind: "msg"; m: SpaceMessage; grouped: boolean })[] = [];
    let prev: SpaceMessage | null = null;
    for (const m of messages ?? []) {
      if (!prev || dayKey(prev.created_at) !== dayKey(m.created_at)) out.push({ kind: "day", key: `d-${m.id}`, iso: m.created_at });
      const grouped =
        !!prev && prev.author.handle === m.author.handle && dayKey(prev.created_at) === dayKey(m.created_at) && !m.reply_to && new Date(m.created_at).getTime() - new Date(prev.created_at).getTime() < GROUP_WINDOW_MS;
      out.push({ kind: "msg", m, grouped });
      prev = m;
    }
    return out;
  }, [messages]);

  return (
    <>
      <header className="flex items-center gap-3 border-b border-line px-4 py-3">
        <Link href={`/${locale}/spaces/${space.slug}`} className="rounded-full border border-line px-3 py-1 text-sm lg:hidden" aria-label={t("spaces.backToChannels")}>
          ←
        </Link>
        <div className="min-w-0">
          <h2 className="truncate text-xl">
            <span aria-hidden="true" className="text-muted">
              {channel.kind === "announcements" ? "📣 " : "# "}
            </span>
            {channel.name}
          </h2>
          {channel.topic && <p className="truncate text-sm text-muted">{channel.topic}</p>}
        </div>
        <span className="ml-auto text-xs text-muted" role="status">
          {live === "live" ? `● ${t("spaces.live")}` : live === "polling" ? t("spaces.polling") : t("spaces.connecting")}
        </span>
      </header>

      <div className="relative min-h-0 flex-1">
        <div ref={listRef} onScroll={onScroll} role="log" aria-live="polite" aria-relevant="additions" aria-label={t("spaces.messagesLabel", { channel: channel.name })} className="h-full max-h-[62vh] overflow-y-auto px-4 py-4 lg:max-h-none">
          {messages === null ? (
            <Loading label={t("common.loading")} />
          ) : (
            <>
              {hasMore && (
                <div className="mb-4 text-center">
                  <Button size="sm" variant="ghost" onClick={loadOlder}>
                    {t("spaces.loadOlder")}
                  </Button>
                </div>
              )}
              {messages.length === 0 && !error && <p className="py-10 text-center text-muted">{t("spaces.noMessages")}</p>}
              {rows.map((r) =>
                r.kind === "day" ? (
                  <div key={r.key} className="my-5 flex items-center gap-3 text-xs text-muted" role="separator" aria-label={`${formatDate(r.iso, locale)} · ${formatEthiopian(r.iso, locale)}`}>
                    <span className="h-px flex-1 bg-line" />
                    <span>
                      {formatDate(r.iso, locale)} · {formatEthiopian(r.iso, locale)}
                    </span>
                    <span className="h-px flex-1 bg-line" />
                  </div>
                ) : (
                  <MessageRow key={r.m.id} m={r.m} grouped={r.grouped} onReply={setReplyTo} onChanged={(m) => setMessages((cur) => (cur ? merge(cur, [m]) : cur))} canReact={!!me && space.is_member} />
                ),
              )}
            </>
          )}
          {error && <Alert tone="caution">{error}</Alert>}
        </div>
        {unseen > 0 && (
          <button type="button" onClick={jumpToLatest} className="absolute bottom-3 left-1/2 -translate-x-1/2 rounded-full bg-forest px-4 py-2 text-sm text-on-forest shadow-[var(--shadow)]">
            {t("spaces.newMessages", { n: unseen })} ↓
          </button>
        )}
      </div>

      <Composer space={space} channel={channel} base={base} replyTo={replyTo} onCancelReply={() => setReplyTo(null)} onSent={(m) => {
        setReplyTo(null);
        atBottom.current = true;
        applyIncoming([m]);
      }} onJoined={onJoined} />
    </>
  );
}

function MessageRow({ m, grouped, onReply, onChanged, canReact }: { m: SpaceMessage; grouped: boolean; onReply: (m: SpaceMessage) => void; onChanged: (m: SpaceMessage) => void; canReact: boolean }) {
  const { t, locale } = useI18n();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(m.body);
  const [picker, setPicker] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function react(emoji: string) {
    setPicker(false);
    try {
      onChanged(await api<SpaceMessage>(`/space-messages/${m.id}/reactions`, { json: { emoji } }));
    } catch (e) {
      setError(errorMessage(e));
    }
  }
  async function saveEdit() {
    try {
      onChanged(await api<SpaceMessage>(`/space-messages/${m.id}`, { method: "PATCH", json: { body: draft } }));
      setEditing(false);
    } catch (e) {
      setError(errorMessage(e));
    }
  }
  async function remove() {
    if (!window.confirm(t("spaces.deleteConfirm"))) return;
    try {
      await api(`/space-messages/${m.id}`, { method: "DELETE" });
      onChanged({ ...m, status: "removed", body: "", reactions: [] });
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  if (m.status === "removed") {
    return <p className="py-1 pl-14 text-sm italic text-muted">{t("spaces.removed")}</p>;
  }
  const author = typeof m.reply_to?.author === "string" ? m.reply_to.author : m.reply_to?.author.display_name;

  return (
    <article className={cn("group relative rounded-lg px-2 hover:bg-surface-2/50", grouped ? "py-0.5" : "mt-3 py-1.5")} aria-label={`${m.author.display_name}, ${formatTime(m.created_at, locale)}`}>
      {m.reply_to && (
        <p className="mb-1 ml-12 truncate text-xs text-muted">
          ↪ <span className="font-medium">{author}</span>: {m.reply_to.excerpt}
        </p>
      )}
      <div className="flex gap-3">
        {grouped ? (
          <span className="w-9 shrink-0 pt-0.5 text-right text-[0.65rem] text-muted opacity-0 group-hover:opacity-100">{formatTime(m.created_at, locale)}</span>
        ) : (
          <span aria-hidden="true" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-forest/10 font-display text-lg text-forest">
            {m.author.display_name.slice(0, 1)}
          </span>
        )}
        <div className="min-w-0 flex-1">
          {!grouped && (
            <p className="text-sm">
              <Link href={`/${locale}/creators/${m.author.handle}`} className="font-semibold hover:underline">
                {m.author.display_name}
              </Link>
              {m.author.role === "moderator" && <span className="ml-2 rounded-full border border-forest/40 px-2 text-[0.65rem] uppercase tracking-wider text-forest">{t("spaces.moderator")}</span>}
              <span className="ml-2 text-xs text-muted">{formatTime(m.created_at, locale)}</span>
            </p>
          )}
          {editing ? (
            <div className="mt-1 space-y-2">
              <label htmlFor={`edit-${m.id}`} className="sr-only">
                {t("spaces.edit")}
              </label>
              <textarea id={`edit-${m.id}`} value={draft} onChange={(e) => setDraft(e.target.value)} maxLength={2000} className="w-full rounded-lg border border-line bg-surface px-3 py-2" />
              <div className="flex gap-2">
                <Button size="sm" onClick={saveEdit} disabled={!draft.trim()}>
                  {t("common.save")}
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
                  {t("common.cancel")}
                </Button>
              </div>
            </div>
          ) : (
            <p className="whitespace-pre-line break-words">
              {m.body}
              {m.edited_at && <span className="ml-1 text-xs text-muted">({t("spaces.edited")})</span>}
            </p>
          )}
          {m.status === "held" && <p className="mt-1 text-xs text-caution">{t("spaces.held")}</p>}
          {m.reactions.length > 0 && (
            <div className="mt-1 flex flex-wrap gap-1.5">
              {m.reactions.map((r) => (
                <button
                  key={r.emoji}
                  type="button"
                  aria-pressed={r.mine}
                  disabled={!canReact}
                  onClick={() => react(r.emoji)}
                  aria-label={t("spaces.reactionLabel", { emoji: r.emoji, n: r.count })}
                  className={cn("rounded-full border px-2 py-0.5 text-sm", r.mine ? "border-forest bg-forest/10" : "border-line")}
                >
                  {r.emoji} {r.count}
                </button>
              ))}
            </div>
          )}
          {error && <p className="text-xs text-danger">{error}</p>}
        </div>
      </div>
      {/* Hover / focus actions */}
      <div className="absolute -top-3 right-2 hidden gap-1 rounded-full border border-line bg-surface px-1 py-0.5 shadow-sm group-focus-within:flex group-hover:flex">
        {canReact && (
          <button type="button" className="rounded-full px-2 py-0.5 text-sm hover:bg-surface-2" aria-expanded={picker} aria-label={t("spaces.addReaction")} onClick={() => setPicker((p) => !p)}>
            ☺
          </button>
        )}
        {canReact && (
          <button type="button" className="rounded-full px-2 py-0.5 text-sm hover:bg-surface-2" onClick={() => onReply(m)}>
            {t("spaces.reply")}
          </button>
        )}
        {m.can_edit && (
          <button type="button" className="rounded-full px-2 py-0.5 text-sm hover:bg-surface-2" onClick={() => setEditing(true)}>
            {t("spaces.edit")}
          </button>
        )}
        {m.can_delete && (
          <button type="button" className="rounded-full px-2 py-0.5 text-sm hover:bg-surface-2" onClick={remove}>
            {t("spaces.delete")}
          </button>
        )}
        <ReportButton path={`/space-messages/${m.id}/report`} className="min-h-0 px-2 py-0.5" />
      </div>
      {picker && (
        <div role="group" aria-label={t("spaces.addReaction")} className="absolute right-2 top-6 z-10 flex gap-1 rounded-full border border-line bg-surface px-2 py-1 shadow-[var(--shadow)]">
          {EMOJIS.map((e) => (
            <button key={e} type="button" className="rounded-full px-1.5 text-lg hover:bg-surface-2" onClick={() => react(e)} aria-label={e}>
              {e}
            </button>
          ))}
        </div>
      )}
    </article>
  );
}

function Composer({ space, channel, base, replyTo, onCancelReply, onSent, onJoined }: { space: Space; channel: Channel; base: string; replyTo: SpaceMessage | null; onCancelReply: () => void; onSent: (m: SpaceMessage) => void; onJoined: () => void }) {
  const { t, locale } = useI18n();
  const { me } = useSession();
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (cooldown <= 0) return;
    const h = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(h);
  }, [cooldown]);
  useEffect(() => {
    if (replyTo) inputRef.current?.focus();
  }, [replyTo]);

  if (!me) {
    return (
      <div className="border-t border-line p-4 text-center text-sm">
        <Link href={`/${locale}/account`} className="underline">
          {t("common.signIn")}
        </Link>{" "}
        — {t("spaces.signInToChat")}
      </div>
    );
  }
  if (!space.is_member) {
    return (
      <div className="flex flex-wrap items-center justify-center gap-3 border-t border-line p-4 text-sm">
        <span>{t("spaces.joinToChat", { space: space.name })}</span>
        <Button
          size="sm"
          onClick={async () => {
            try {
              await api(`/spaces/${space.slug}/join`, { method: "POST" });
              onJoined();
            } catch (e) {
              setError(errorMessage(e));
            }
          }}
        >
          {t("spaces.join")}
        </Button>
        {error && <p className="w-full text-center text-danger">{error}</p>}
      </div>
    );
  }
  if (!channel.can_post) {
    return <p className="border-t border-line p-4 text-center text-sm text-muted">{t("spaces.readOnly")}</p>;
  }

  async function send() {
    const text = body.trim();
    if (!text || busy || cooldown > 0) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const m = await api<SpaceMessage>(`${base}/messages`, { json: { body: text, reply_to: replyTo?.id } });
      setBody("");
      onSent(m);
      if (m.status === "held") setNotice(t("spaces.heldNotice"));
      if (channel.slow_mode_seconds > 0) setCooldown(channel.slow_mode_seconds);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  function onKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      void send();
    }
    if (e.key === "Escape" && replyTo) onCancelReply();
  }

  return (
    <div className="border-t border-line p-3">
      {replyTo && (
        <p className="mb-2 flex items-center gap-2 rounded-lg bg-surface-2 px-3 py-1.5 text-xs">
          ↪ {t("spaces.replyingTo", { name: replyTo.author.display_name })}
          <button type="button" className="ml-auto underline" onClick={onCancelReply}>
            {t("common.cancel")}
          </button>
        </p>
      )}
      <div className="flex items-end gap-2">
        <label htmlFor="composer" className="sr-only">
          {t("spaces.composerLabel", { channel: channel.name })}
        </label>
        <textarea
          ref={inputRef}
          id="composer"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          onKeyDown={onKey}
          rows={1}
          maxLength={2000}
          placeholder={t("spaces.placeholder", { channel: channel.name })}
          className="max-h-40 min-h-[44px] flex-1 resize-y rounded-xl border border-line bg-bg px-3.5 py-2.5"
        />
        <Button onClick={send} disabled={!body.trim() || busy || cooldown > 0}>
          {cooldown > 0 ? `${cooldown}s` : t("spaces.send")}
        </Button>
      </div>
      <p className="mt-1.5 text-[0.7rem] text-muted">
        {t("spaces.composerHint")}
        {channel.slow_mode_seconds > 0 && <> · {t("spaces.slowMode", { n: channel.slow_mode_seconds })}</>}
      </p>
      {notice && (
        <p role="status" className="mt-1 text-xs text-caution">
          {notice}
        </p>
      )}
      {error && <p className="mt-1 text-xs text-danger">{error}</p>}
    </div>
  );
}

export function SpacesSignedOutNote() {
  const { t, locale } = useI18n();
  const { me } = useSession();
  if (me) return null;
  return (
    <p className="mb-4 text-sm text-muted">
      <ButtonLink href={`/${locale}/account`} size="sm" variant="secondary">
        {t("common.signIn")}
      </ButtonLink>{" "}
      {t("spaces.signedOutLead")}
    </p>
  );
}
