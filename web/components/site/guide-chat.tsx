"use client";

import Image from "next/image";
import Link from "next/link";
import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { Alert, Badge, Button, cn } from "@/components/ui";
import { Dialog } from "@/components/ui/client";
import { api, ApiError, errorMessage } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { Citation, ConversationSummary, GuideAction, Suggestion, TieAnswer } from "@/lib/types";
import { useOnline } from "./pwa";
import { useI18n, useSession } from "./providers";

interface Persona {
  key: string;
  name: string;
  description: string;
}
interface Status {
  mode: string;
  permitted_modes: string[];
  generative?: boolean;
  notice?: string;
  provider: { name: string; local: boolean; model?: string | null } | null;
}
type GuideTurn = { role: "guide"; answer: TieAnswer; feedback?: "up" | "down"; restored?: boolean };
type Turn = { role: "user"; text: string } | GuideTurn;

const CONF_TONE = { grounded: "success", partial: "caution", insufficient_evidence: "neutral", refused: "danger" } as const;
const CONFIDENCES = ["grounded", "partial", "insufficient_evidence", "refused"] as const;

/** Render "[n]" markers as chips that open the Sources panel; everything else stays plain text (no HTML). */
function AnswerText({ text, citations, onCite }: { text: string; citations: Citation[]; onCite: (n: number) => void }) {
  const { t } = useI18n();
  const known = new Set(citations.map((c) => c.n));
  const parts = text.split(/(\[\d+\])/g);
  return (
    <p className="whitespace-pre-line leading-relaxed">
      {parts.map((p, i) => {
        const m = /^\[(\d+)\]$/.exec(p);
        if (m && known.has(Number(m[1]))) {
          const n = Number(m[1]);
          return (
            <button
              key={i}
              type="button"
              onClick={() => onCite(n)}
              aria-label={t("guide.openSource", { n })}
              className="mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded-full border border-earth/40 bg-earth/10 px-1.5 align-[0.15em] text-[0.7rem] font-semibold text-earth hover:bg-earth/20"
            >
              {n}
            </button>
          );
        }
        return <Fragment key={i}>{p}</Fragment>;
      })}
    </p>
  );
}

function actionHref(a: GuideAction, locale: string): string {
  if (a.type === "open_destination") return `/${locale}/destinations/${encodeURIComponent(a.slug)}`;
  const q = new URLSearchParams();
  if (a.params.days) q.set("days", String(a.params.days));
  if (a.params.interests?.length) q.set("interests", a.params.interests.join(","));
  if (a.params.start_slug) q.set("start", a.params.start_slug);
  const s = q.toString();
  return `/${locale}/plan${s ? `?${s}` : ""}`;
}

function SourcesPanel({ citations, focus, onClose }: { citations: Citation[]; focus: number | null; onClose?: () => void }) {
  const { t, locale } = useI18n();
  const refs = useRef<Record<number, HTMLLIElement | null>>({});
  useEffect(() => {
    if (focus !== null) refs.current[focus]?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [focus, citations]);
  return (
    <section aria-labelledby="sources-h" className="rounded-[var(--radius)] border border-line bg-surface">
      <div className="flex items-center gap-2 border-b border-line px-5 py-3">
        <h2 id="sources-h" className="text-lg">
          {t("guide.citations")}
        </h2>
        <span className="text-xs text-muted">{citations.length > 0 && t("guide.sourceCount", { n: citations.length })}</span>
        {onClose && (
          <button type="button" className="ml-auto text-sm underline" onClick={onClose}>
            {t("common.close")}
          </button>
        )}
      </div>
      {citations.length === 0 ? (
        <p className="px-5 py-6 text-sm text-muted">{t("guide.sourcesEmpty")}</p>
      ) : (
        <ol className="max-h-[60vh] space-y-3 overflow-y-auto p-4">
          {citations.map((c) => (
            <li
              key={c.n}
              ref={(el) => {
                refs.current[c.n] = el;
              }}
              className={cn("rounded-xl border p-3 text-sm transition-colors", focus === c.n ? "border-earth bg-earth/5" : "border-line")}
            >
              <p className="font-medium">
                <span className="mr-1.5 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-earth/10 px-1.5 text-[0.7rem] font-semibold text-earth">{c.n}</span>
                {c.url ? (
                  <a href={c.url} target="_blank" rel="noopener noreferrer" className="underline">
                    {c.document_title}
                  </a>
                ) : (
                  c.document_title
                )}
              </p>
              <p className="mt-0.5 text-xs text-muted">
                {[c.author, c.publisher, c.published_on, c.language].filter(Boolean).join(" · ")}
                {c.verified_at && <> · {t("guide.verifiedOn", { date: formatDate(c.verified_at, locale) })}</>}
              </p>
              <blockquote className="mt-2 border-l-2 border-terracotta pl-3 font-display italic">{c.excerpt}</blockquote>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function Searching() {
  const { t } = useI18n();
  return (
    <div role="status" className="flex items-center gap-3 text-sm text-muted">
      <span aria-hidden="true" className="flex gap-1">
        {[0, 1, 2].map((i) => (
          <span key={i} className="h-2 w-2 rounded-full bg-forest motion-safe:animate-pulse" style={{ animationDelay: `${i * 180}ms` }} />
        ))}
      </span>
      {t("guide.searching")}
    </div>
  );
}

function History({ activeId, onOpen, onNew, refreshKey }: { activeId?: string; onOpen: (id: string) => void; onNew: () => void; refreshKey: number }) {
  const { t, locale } = useI18n();
  const [items, setItems] = useState<ConversationSummary[] | null>(null);
  useEffect(() => {
    api<ConversationSummary[]>("/tie/conversations")
      .then(setItems)
      .catch(() => setItems([]));
  }, [refreshKey]);
  return (
    <nav aria-label={t("guide.history")} className="rounded-[var(--radius)] border border-line bg-surface p-3">
      <Button size="sm" className="w-full" onClick={onNew}>
        + {t("guide.newChat")}
      </Button>
      <p className="mt-4 px-2 text-xs font-semibold uppercase tracking-[0.18em] text-earth">{t("guide.history")}</p>
      {items === null ? (
        <p className="px-2 py-3 text-sm text-muted">{t("common.loading")}</p>
      ) : items.length === 0 ? (
        <p className="px-2 py-3 text-sm text-muted">{t("guide.historyEmpty")}</p>
      ) : (
        <ul className="mt-2 max-h-[52vh] space-y-1 overflow-y-auto">
          {items.map((c) => (
            <li key={c.id}>
              <button
                type="button"
                aria-current={c.id === activeId ? "true" : undefined}
                onClick={() => onOpen(c.id)}
                className={cn("w-full rounded-lg px-3 py-2 text-left text-sm", c.id === activeId ? "bg-surface-2 font-medium" : "hover:bg-surface-2")}
              >
                <span className="line-clamp-2">{c.title}</span>
                <span className="block text-xs text-muted">{formatDate(c.updated_at, locale)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </nav>
  );
}

export function GuideChat({ destinationSlug, compact = false }: { destinationSlug?: string; compact?: boolean }) {
  const { t, locale } = useI18n();
  const { me } = useSession();
  const online = useOnline();
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [persona, setPersona] = useState("cultural_storyteller");
  const [status, setStatus] = useState<Status | null>(null);
  const [unavailable, setUnavailable] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [sources, setSources] = useState<{ turn: number; focus: number | null } | null>(null);
  const [copied, setCopied] = useState<number | null>(null);
  const [historyKey, setHistoryKey] = useState(0);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    api<Persona[]>(`/tie/personas?locale=${locale}`)
      .then((p) => {
        setPersonas(p);
        if (p[0] && !p.some((x) => x.key === "cultural_storyteller")) setPersona(p[0].key);
      })
      .catch(() => undefined);
    api<Status>("/tie/status")
      .then(setStatus)
      .catch((e) => setUnavailable(e instanceof ApiError && e.notAvailable ? t("common.notAvailableYet") : t("guide.unavailable")));
    const q = new URLSearchParams({ locale });
    if (destinationSlug) q.set("destination", destinationSlug);
    api<Suggestion[]>(`/tie/suggestions?${q}`)
      .then(setSuggestions)
      .catch(() => setSuggestions([]));
  }, [locale, t, destinationSlug]);

  useEffect(() => {
    // Block body on purpose: modern scrollIntoView() returns a Promise, which React would treat as a cleanup.
    endRef.current?.scrollIntoView({ block: "nearest" });
  }, [turns, busy]);

  const ask = useCallback(
    async (q: string) => {
      if (!q.trim() || busy) return;
      setBusy(true);
      setError(null);
      setTurns((tt) => [...tt, { role: "user", text: q }]);
      setQuestion("");
      try {
        const answer = await api<TieAnswer>("/tie/ask", {
          json: { question: q, locale, persona, conversation_id: conversationId, destination_slug: destinationSlug },
        });
        const isNew = !conversationId;
        setConversationId(answer.conversation_id);
        setTurns((tt) => {
          const next = [...tt, { role: "guide", answer } as GuideTurn];
          if (answer.citations.length) setSources({ turn: next.length - 1, focus: null });
          return next;
        });
        if (isNew) setHistoryKey((k) => k + 1);
      } catch (e) {
        setError(e instanceof ApiError && e.notAvailable ? t("common.notAvailableYet") : errorMessage(e));
      } finally {
        setBusy(false);
      }
    },
    [busy, conversationId, destinationSlug, locale, persona, t],
  );

  async function feedback(i: number, rating: "up" | "down") {
    const turn = turns[i];
    if (turn.role !== "guide") return;
    try {
      await api("/tie/feedback", { json: { message_id: turn.answer.message_id, rating } });
      setTurns((tt) => tt.map((x, j) => (j === i && x.role === "guide" ? { ...x, feedback: rating } : x)));
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function copy(i: number, text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(i);
      setTimeout(() => setCopied((c) => (c === i ? null : c)), 2000);
    } catch {
      setError(t("guide.copyFailed"));
    }
  }

  function newChat() {
    setTurns([]);
    setConversationId(undefined);
    setSources(null);
    setError(null);
    inputRef.current?.focus();
  }

  async function openConversation(id: string) {
    setError(null);
    try {
      const c = await api<{
        id: string;
        persona: string;
        messages: { id: string; role: string; content: string; citations?: Citation[] | null; confidence?: string | null }[];
      }>(`/tie/conversations/${id}`);
      setConversationId(c.id);
      if (c.persona) setPersona(c.persona);
      setSources(null);
      setTurns(
        c.messages.map((m): Turn =>
          m.role === "user"
            ? { role: "user", text: m.content }
            : {
                role: "guide",
                restored: true,
                answer: {
                  conversation_id: c.id,
                  message_id: m.id,
                  answer: m.content,
                  confidence: (CONFIDENCES as readonly string[]).includes(m.confidence ?? "") ? (m.confidence as TieAnswer["confidence"]) : "partial",
                  citations: m.citations ?? [],
                  warnings: [],
                  follow_up_questions: [],
                  mode_used: "",
                  provider: null,
                  latency_ms: 0,
                },
              },
        ),
      );
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  const disabled = busy || !online || !!unavailable;
  const activeSources = sources && turns[sources.turn]?.role === "guide" ? (turns[sources.turn] as GuideTurn).answer.citations : [];
  const modeLabel = !status
    ? "…"
    : status.mode === "retrieval_only" || !status.provider
      ? t("guide.modeRetrieval")
      : status.provider.local
        ? t("guide.modeLocal")
        : t("guide.modeExternal");
  const activePersona = personas.find((p) => p.key === persona);
  const showHistory = !!me && !compact;

  return (
    <div className={cn("grid gap-6", !compact && (showHistory ? "lg:grid-cols-[230px_minmax(0,1fr)_330px]" : "lg:grid-cols-[minmax(0,1fr)_330px]"))}>
      {showHistory && (
        <div className="order-2 lg:order-none">
          <History activeId={conversationId} onOpen={openConversation} onNew={newChat} refreshKey={historyKey} />
        </div>
      )}

      <section aria-label={t("guide.title")} className="flex min-h-[520px] flex-col overflow-hidden rounded-[var(--radius)] border border-line bg-surface shadow-[var(--shadow)]">
        <div className="flex flex-wrap items-center gap-2 border-b border-line bg-surface-2/50 px-5 py-2.5 text-xs text-muted">
          <span role="note">{t("guide.honest", { mode: modeLabel })}</span>
          {status?.provider && status.mode !== "retrieval_only" && (
            <Badge tone={status.provider.local ? "success" : "caution"}>{status.provider.model ?? status.provider.name}</Badge>
          )}
          {turns.length > 0 && !showHistory && (
            <button type="button" className="ml-auto rounded-full px-3 py-1 underline" onClick={newChat}>
              {t("guide.newChat")}
            </button>
          )}
        </div>

        {/* Personas */}
        {personas.length > 0 && (
          <div className="border-b border-line px-5 py-3">
            <div role="group" aria-label={t("guide.persona")} className="flex flex-wrap gap-2">
              {personas.map((p) => (
                <button
                  key={p.key}
                  type="button"
                  aria-pressed={persona === p.key}
                  title={p.description}
                  onClick={() => setPersona(p.key)}
                  className={cn("rounded-full border px-3 py-1.5 text-sm transition-colors", persona === p.key ? "border-forest bg-forest text-on-forest" : "border-line hover:border-sandstone")}
                >
                  {p.name}
                </button>
              ))}
            </div>
            {activePersona && <p className="mt-2 text-xs text-muted">{activePersona.description}</p>}
          </div>
        )}

        <div className="flex-1 space-y-6 overflow-y-auto px-5 py-6" aria-live="polite">
          {unavailable && <Alert tone="caution">{unavailable}</Alert>}
          {!online && <Alert tone="caution">{t("offline.youAreOffline")}</Alert>}

          {turns.length === 0 && !unavailable && (
            <div className="mx-auto max-w-xl py-4 text-center">
              <Image src="/brand/emblem-256.webp" alt="" width={72} height={72} unoptimized className="brand-badge mx-auto rounded-2xl" />
              <p className="mt-4 font-display text-3xl">{t("guide.welcome")}</p>
              <p className="mt-2 text-sm text-muted">{t("guide.welcomeLead")}</p>
              {suggestions.length > 0 && (
                <div className="mt-6">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-earth">{t("guide.starters")}</p>
                  <ul className="mt-3 grid gap-2 text-left sm:grid-cols-2">
                    {suggestions.slice(0, 6).map((s) => (
                      <li key={s.text}>
                        <button
                          type="button"
                          disabled={disabled}
                          onClick={() => ask(s.text)}
                          className="h-full w-full rounded-xl border border-line bg-bg px-4 py-3 text-sm transition-colors hover:border-sandstone disabled:opacity-60"
                        >
                          <span className="block text-[0.65rem] uppercase tracking-[0.15em] text-muted">{s.category}</span>
                          {s.text}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {turns.map((turn, i) =>
            turn.role === "user" ? (
              <div key={i} className="ml-auto max-w-[85%] rounded-2xl rounded-br-sm bg-forest px-4 py-3 text-on-forest">
                <p className="sr-only">{t("guide.you")}:</p>
                <p className="whitespace-pre-line">{turn.text}</p>
              </div>
            ) : (
              <article key={i} className="max-w-[94%] space-y-3" aria-label={t("guide.guideName")}>
                <div className="flex items-start gap-3">
                  <span aria-hidden="true" className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center overflow-hidden rounded-full border border-line bg-[#f8f2e9]">
                    <Image src="/brand/emblem-256.webp" alt="" width={32} height={32} unoptimized />
                  </span>
                  <div className="min-w-0 flex-1 rounded-2xl rounded-tl-sm border border-line bg-bg px-4 py-3">
                    <AnswerText text={turn.answer.answer} citations={turn.answer.citations} onCite={(n) => setSources({ turn: i, focus: n })} />
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2 pl-11 text-xs">
                  <Badge tone={CONF_TONE[turn.answer.confidence]}>{t(`guide.confidence.${turn.answer.confidence}`)}</Badge>
                  {turn.answer.citations.length > 0 && (
                    <button type="button" className="rounded-full border border-line px-2.5 py-0.5 hover:border-sandstone" onClick={() => setSources({ turn: i, focus: null })}>
                      {t("guide.sourceCount", { n: turn.answer.citations.length })}
                    </button>
                  )}
                  {!turn.restored && (
                    <span className="text-muted">
                      {!turn.answer.provider || turn.answer.mode_used === "retrieval_only"
                        ? t("guide.retrieval")
                        : turn.answer.provider.local
                          ? t("guide.local", { model: turn.answer.provider.model ?? turn.answer.provider.name })
                          : t("guide.nonLocal", { model: turn.answer.provider.model ?? turn.answer.provider.name })}
                      {" · "}
                      {turn.answer.latency_ms} ms
                    </span>
                  )}
                </div>
                <div className="space-y-3 pl-11">
                  {turn.answer.warnings.length > 0 && (
                    <Alert tone="caution" title={t("guide.warnings")}>
                      <ul className="list-disc pl-5">
                        {turn.answer.warnings.map((w, j) => (
                          <li key={j}>{w}</li>
                        ))}
                      </ul>
                    </Alert>
                  )}
                  {(turn.answer.actions?.length ?? 0) > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {turn.answer.actions!.map((a, j) => (
                        <Link key={j} href={actionHref(a, locale)} className="inline-flex items-center gap-1.5 rounded-full bg-forest px-3.5 py-1.5 text-sm text-on-forest hover:bg-forest-2">
                          {a.type === "open_planner" ? "🗺" : "→"} {a.label}
                        </Link>
                      ))}
                    </div>
                  )}
                  {turn.answer.follow_up_questions.length > 0 && (
                    <div>
                      <p className="text-xs uppercase tracking-[0.15em] text-muted">{t("guide.followUps")}</p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {turn.answer.follow_up_questions.map((f) => (
                          <button key={f} type="button" disabled={disabled} onClick={() => ask(f)} className="rounded-full border border-line px-3 py-1.5 text-sm hover:border-sandstone">
                            {f}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  <div className="flex flex-wrap items-center gap-2 text-sm">
                    <button type="button" className="rounded-full border border-line px-3 py-1" onClick={() => copy(i, turn.answer.answer)}>
                      {copied === i ? t("guide.copied") : t("guide.copy")}
                    </button>
                    {turn.feedback ? (
                      <span role="status" className="text-muted">
                        {t("guide.thanks")}
                      </span>
                    ) : (
                      <>
                        <button type="button" className="rounded-full border border-line px-3 py-1" onClick={() => feedback(i, "up")} aria-label={t("guide.helpful")}>
                          👍 <span className="sr-only sm:not-sr-only">{t("guide.helpful")}</span>
                        </button>
                        <button type="button" className="rounded-full border border-line px-3 py-1" onClick={() => feedback(i, "down")} aria-label={t("guide.notHelpful")}>
                          👎 <span className="sr-only sm:not-sr-only">{t("guide.notHelpful")}</span>
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </article>
            ),
          )}
          {busy && <Searching />}
          {error && <Alert tone="danger">{error}</Alert>}
          <div ref={endRef} />
        </div>

        <form
          className="border-t border-line p-4"
          onSubmit={(e) => {
            e.preventDefault();
            void ask(question);
          }}
        >
          <label htmlFor="q-input" className="sr-only">
            {t("guide.question")}
          </label>
          <div className="flex gap-3">
            <textarea
              ref={inputRef}
              id="q-input"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  void ask(question);
                }
              }}
              maxLength={1200}
              rows={2}
              placeholder={t("guide.placeholder")}
              className="min-h-[52px] flex-1 resize-y rounded-xl border border-line bg-bg px-3.5 py-2.5"
            />
            <Button type="submit" disabled={disabled || !question.trim()}>
              {busy ? t("guide.asking") : t("guide.ask")}
            </Button>
          </div>
          <p className="mt-3 text-xs text-muted">{t("guide.disclaimer")}</p>
        </form>
      </section>

      {!compact && (
        <aside className="space-y-4 lg:sticky lg:top-24 lg:self-start">
          <SourcesPanel citations={activeSources} focus={sources?.focus ?? null} />
        </aside>
      )}
      {compact && sources && activeSources.length > 0 && <SourcesPanel citations={activeSources} focus={sources.focus} onClose={() => setSources(null)} />}
    </div>
  );
}

/** Small "ask about this place" drawer for destination pages. */
export function GuideDrawer({ destinationSlug, destinationName }: { destinationSlug: string; destinationName: string }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant="secondary" onClick={() => setOpen(true)}>
        ✦ {t("guide.askAbout", { name: destinationName })}
      </Button>
      <Dialog open={open} onClose={() => setOpen(false)} title={t("guide.askAbout", { name: destinationName })} closeLabel={t("common.close")}>
        {open && <GuideChat destinationSlug={destinationSlug} compact />}
      </Dialog>
    </>
  );
}
