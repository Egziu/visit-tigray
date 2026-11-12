"use client";

import { Fragment, useEffect, useId, useRef, useState } from "react";
import { Alert, Badge, Button, cn } from "@/components/ui";
import { api, ApiError, errorMessage } from "@/lib/api";
import type { Citation, TieAnswer } from "@/lib/types";
import { useOnline } from "./pwa";
import { useI18n } from "./providers";

interface Persona {
  key: string;
  name: string;
  description: string;
}
interface Status {
  mode: string;
  permitted_modes: string[];
  provider: { name: string; local: boolean; model?: string | null; available: boolean };
}
type Turn = { role: "user"; text: string } | { role: "guide"; answer: TieAnswer; feedback?: "up" | "down" };

const CONF_TONE = { grounded: "success", partial: "caution", insufficient_evidence: "neutral", refused: "danger" } as const;

/** Render "[n]" markers as links to the matching citation; everything else stays plain text (no HTML). */
function AnswerText({ text, citations, anchorBase }: { text: string; citations: Citation[]; anchorBase: string }) {
  const known = new Set(citations.map((c) => c.n));
  const parts = text.split(/(\[\d+\])/g);
  return (
    <p className="whitespace-pre-line">
      {parts.map((p, i) => {
        const m = /^\[(\d+)\]$/.exec(p);
        if (m && known.has(Number(m[1]))) {
          return (
            <a key={i} href={`#${anchorBase}-c${m[1]}`} className="mx-0.5 align-super text-xs font-semibold text-earth underline">
              [{m[1]}]
            </a>
          );
        }
        return <Fragment key={i}>{p}</Fragment>;
      })}
    </p>
  );
}

export function GuideChat({ destinationSlug }: { destinationSlug?: string }) {
  const { t, locale } = useI18n();
  const online = useOnline();
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [persona, setPersona] = useState("cultural_storyteller");
  const [status, setStatus] = useState<Status | null>(null);
  const [unavailable, setUnavailable] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const base = useId().replace(/:/g, "");
  const endRef = useRef<HTMLDivElement>(null);

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
  }, [locale, t]);

  useEffect(() => endRef.current?.scrollIntoView({ block: "nearest" }), [turns]);

  async function ask(q: string) {
    if (!q.trim()) return;
    setBusy(true);
    setError(null);
    setTurns((tt) => [...tt, { role: "user", text: q }]);
    setQuestion("");
    try {
      const answer = await api<TieAnswer>("/tie/ask", {
        json: { question: q, locale, persona, conversation_id: conversationId, destination_slug: destinationSlug },
      });
      setConversationId(answer.conversation_id);
      setTurns((tt) => [...tt, { role: "guide", answer }]);
    } catch (e) {
      setError(e instanceof ApiError && e.notAvailable ? t("common.notAvailableYet") : errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

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

  const disabled = busy || !online || !!unavailable;

  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_320px]">
      <section aria-label={t("guide.title")} className="flex min-h-[480px] flex-col rounded-[var(--radius)] border border-line bg-surface">
        <div className="flex flex-wrap items-center gap-2 border-b border-line px-5 py-3 text-sm text-muted">
          {status && <span>{t("guide.status", { mode: status.mode })}</span>}
          {status && (
            <Badge tone={status.provider.local ? "success" : "caution"}>
              {status.provider.local ? "local" : "external"} · {status.provider.model ?? status.provider.name}
            </Badge>
          )}
          {turns.length > 0 && (
            <button
              type="button"
              className="ml-auto rounded-full px-3 py-1 text-sm underline"
              onClick={() => {
                setTurns([]);
                setConversationId(undefined);
              }}
            >
              {t("guide.newConversation")}
            </button>
          )}
        </div>
        <div className="flex-1 space-y-6 overflow-y-auto px-5 py-6" aria-live="polite">
          {unavailable && <Alert tone="caution">{unavailable}</Alert>}
          {!online && <Alert tone="caution">{t("offline.youAreOffline")}</Alert>}
          {turns.map((turn, i) =>
            turn.role === "user" ? (
              <div key={i} className="ml-auto max-w-[85%] rounded-2xl rounded-br-sm bg-forest px-4 py-3 text-on-forest">
                <p className="sr-only">{t("guide.you")}:</p>
                {turn.text}
              </div>
            ) : (
              <div key={i} className="max-w-[92%] space-y-3">
                <p className="sr-only">{t("guide.guideName")}:</p>
                <div className="rounded-2xl rounded-bl-sm border border-line bg-bg px-4 py-3">
                  <AnswerText text={turn.answer.answer} citations={turn.answer.citations} anchorBase={`${base}-${i}`} />
                </div>
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <Badge tone={CONF_TONE[turn.answer.confidence]}>{t(`guide.confidence.${turn.answer.confidence}`)}</Badge>
                  <span className="text-muted">
                    {turn.answer.mode_used === "retrieval_only" || turn.answer.provider.name === "retrieval"
                      ? t("guide.retrieval")
                      : turn.answer.provider.local
                        ? t("guide.local", { model: turn.answer.provider.model ?? turn.answer.provider.name })
                        : t("guide.nonLocal", { model: turn.answer.provider.model ?? turn.answer.provider.name })}
                    {" · "}
                    {turn.answer.latency_ms} ms
                  </span>
                </div>
                {turn.answer.warnings.length > 0 && (
                  <Alert tone="caution" title={t("guide.warnings")}>
                    <ul className="list-disc pl-5">
                      {turn.answer.warnings.map((w, j) => (
                        <li key={j}>{w}</li>
                      ))}
                    </ul>
                  </Alert>
                )}
                {turn.answer.citations.length > 0 && (
                  <details open className="rounded-lg border border-line bg-surface-2/60 px-4 py-3 text-sm">
                    <summary className="cursor-pointer font-medium">{t("guide.citations")}</summary>
                    <ol className="mt-3 space-y-3">
                      {turn.answer.citations.map((c) => (
                        <li key={c.n} id={`${base}-${i}-c${c.n}`} className="target:rounded target:bg-gold/20">
                          <p className="font-medium">
                            [{c.n}]{" "}
                            {c.url ? (
                              <a href={c.url} target="_blank" rel="noopener noreferrer" className="underline">
                                {c.document_title}
                              </a>
                            ) : (
                              c.document_title
                            )}
                          </p>
                          <p className="text-muted">{[c.author, c.publisher, c.published_on, c.language].filter(Boolean).join(" · ")}</p>
                          <blockquote className="mt-1 border-l-2 border-sandstone pl-3 italic">{c.excerpt}</blockquote>
                        </li>
                      ))}
                    </ol>
                  </details>
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
                <div className="flex items-center gap-2 text-sm">
                  {turn.feedback ? (
                    <span role="status" className="text-muted">
                      {t("guide.thanks")}
                    </span>
                  ) : (
                    <>
                      <button type="button" className="rounded-full border border-line px-3 py-1" onClick={() => feedback(i, "up")}>
                        👍 <span className="sr-only sm:not-sr-only">{t("guide.helpful")}</span>
                      </button>
                      <button type="button" className="rounded-full border border-line px-3 py-1" onClick={() => feedback(i, "down")}>
                        👎 <span className="sr-only sm:not-sr-only">{t("guide.notHelpful")}</span>
                      </button>
                    </>
                  )}
                </div>
              </div>
            ),
          )}
          {busy && <p className="text-muted">{t("guide.asking")}</p>}
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
              id="q-input"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void ask(question);
                }
              }}
              maxLength={1200}
              rows={2}
              placeholder={t("guide.placeholder")}
              className="min-h-[52px] flex-1 resize-y rounded-lg border border-line bg-bg px-3.5 py-2.5"
            />
            <Button type="submit" disabled={disabled || !question.trim()}>
              {busy ? t("guide.asking") : t("guide.ask")}
            </Button>
          </div>
          <p className="mt-3 text-xs text-muted">{t("guide.disclaimer")}</p>
        </form>
      </section>

      <aside className="space-y-4">
        <fieldset className="rounded-[var(--radius)] border border-line bg-surface p-5">
          <legend className="px-1 text-sm font-semibold">{t("guide.persona")}</legend>
          {personas.length === 0 ? (
            <p className="text-sm text-muted">{t("common.notAvailableYet")}</p>
          ) : (
            <div className="mt-2 space-y-2">
              {personas.map((p) => (
                <label key={p.key} className={cn("flex cursor-pointer gap-3 rounded-lg border p-3", persona === p.key ? "border-forest bg-surface-2" : "border-line")}>
                  <input type="radio" name="persona" value={p.key} checked={persona === p.key} onChange={() => setPersona(p.key)} className="mt-1 accent-[var(--color-forest)]" />
                  <span>
                    <span className="block text-sm font-medium">{p.name}</span>
                    <span className="block text-xs text-muted">{p.description}</span>
                  </span>
                </label>
              ))}
            </div>
          )}
        </fieldset>
      </aside>
    </div>
  );
}
