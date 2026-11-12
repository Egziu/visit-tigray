"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Alert, Button, EmptyState, Loading } from "@/components/ui";
import { formatDateTime } from "@/lib/format";
import {
  clearAllOfflineData,
  flushOutbox,
  formatBytes,
  listItems,
  listOutbox,
  removeItem,
  storageEstimate,
  type OutboxItem,
  type SavedItem,
} from "@/lib/offline";
import type { Destination } from "@/lib/types";
import { DataSaverToggle } from "./header";
import { sendQueuedMemory, useOnline } from "./pwa";
import { useI18n } from "./providers";

export function OfflineLibrary() {
  const { t, locale } = useI18n();
  const online = useOnline();
  const [items, setItems] = useState<SavedItem[] | null>(null);
  const [outbox, setOutbox] = useState<OutboxItem[]>([]);
  const [estimate, setEstimate] = useState<{ used: number; quota: number } | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [open, setOpen] = useState<SavedItem | null>(null);

  const reload = useCallback(async () => {
    setItems(await listItems().catch(() => []));
    setOutbox(await listOutbox().catch(() => []));
    setEstimate(await storageEstimate().catch(() => null));
  }, []);
  useEffect(() => {
    void reload();
  }, [reload]);

  if (!items) return <Loading label={t("common.loading")} />;

  return (
    <div className="space-y-10">
      {!online && <Alert tone="caution">{t("offline.youAreOffline")}</Alert>}
      <div className="flex flex-wrap items-center gap-3">
        <DataSaverToggle />
        {estimate && <span className="text-sm text-muted">{t("offline.storage", { used: formatBytes(estimate.used), quota: formatBytes(estimate.quota) })}</span>}
        <Button
          variant="secondary"
          size="sm"
          onClick={async () => {
            await clearAllOfflineData();
            setMsg(t("offline.cleared"));
            setOpen(null);
            await reload();
          }}
        >
          {t("offline.clear")}
        </Button>
        {msg && (
          <span role="status" className="text-sm">
            {msg}
          </span>
        )}
      </div>

      {items.length === 0 ? (
        <EmptyState title={t("offline.none")} />
      ) : (
        <ul className="divide-y divide-line rounded-[var(--radius)] border border-line bg-surface">
          {items.map((it) => (
            <li key={it.key} className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
              <div>
                <button type="button" className="font-display text-2xl hover:underline" onClick={() => setOpen(it)}>
                  {it.title}
                </button>
                <p className="text-sm text-muted">
                  {it.kind} · {it.locale} · {t("offline.savedAt", { date: formatDateTime(it.savedAt, locale) })}
                </p>
              </div>
              <div className="flex gap-2">
                {online && (
                  <Link href={it.href} className="rounded-full border border-line px-3 py-1.5 text-sm">
                    {t("common.readMore")}
                  </Link>
                )}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={async () => {
                    await removeItem(it.key);
                    await reload();
                  }}
                >
                  {t("offline.remove")}
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {open && <SavedView item={open} />}

      <section>
        <h2 className="text-3xl">{t("offline.outbox")}</h2>
        {outbox.length === 0 ? (
          <p className="mt-2 text-muted">{t("offline.outboxNone")}</p>
        ) : (
          <>
            <ul className="mt-3 space-y-2">
              {outbox.map((o) => (
                <li key={o.id} className="rounded-lg border border-line bg-surface px-4 py-3 text-sm">
                  {String(o.payload.title ?? o.kind)} · {formatDateTime(o.createdAt, locale)}
                  {o.lastError && <span className="block text-danger">{o.lastError}</span>}
                </li>
              ))}
            </ul>
            <Button
              className="mt-3"
              size="sm"
              disabled={!online}
              onClick={async () => {
                await flushOutbox(sendQueuedMemory);
                await reload();
              }}
            >
              {t("offline.syncNow")}
            </Button>
          </>
        )}
      </section>
    </div>
  );
}

/** Minimal offline reader for saved destination/itinerary data (works with no network). */
function SavedView({ item }: { item: SavedItem }) {
  const { t, locale } = useI18n();
  if (item.kind === "destination") {
    const d = item.data as Destination;
    return (
      <article className="rounded-[var(--radius)] border border-line bg-surface p-7" aria-label={d.name}>
        <p className="text-xs uppercase tracking-[0.2em] text-earth">{t("offline.savedAt", { date: formatDateTime(item.savedAt, locale) })}</p>
        <h2 className="mt-2 text-4xl">{d.name}</h2>
        <p className="mt-3 text-lg text-muted">{d.summary}</p>
        <div className="prose-vt mt-4">{d.body}</div>
        {d.etiquette && (
          <>
            <h3 className="mt-6 text-2xl">{t("destinations.etiquette")}</h3>
            <p className="prose-vt">{d.etiquette}</p>
          </>
        )}
        {d.sources?.length > 0 && (
          <>
            <h3 className="mt-6 text-2xl">{t("destinations.sources")}</h3>
            <ul className="list-disc pl-5 text-sm">
              {d.sources.map((s, i) => (
                <li key={i}>{s.title}</li>
              ))}
            </ul>
          </>
        )}
      </article>
    );
  }
  const plan = item.data as { days?: { day: number; stops: { slug: string; name: string }[] }[]; notice?: string };
  return (
    <article className="rounded-[var(--radius)] border border-line bg-surface p-7">
      <h2 className="text-4xl">{item.title}</h2>
      {plan.notice && <p className="mt-2 text-sm text-muted">{plan.notice}</p>}
      {plan.days?.map((d) => (
        <div key={d.day} className="mt-4">
          <h3 className="text-2xl">{t("plan.day", { n: d.day })}</h3>
          <ul className="list-disc pl-5">
            {d.stops.map((s) => (
              <li key={s.slug}>{s.name}</li>
            ))}
          </ul>
        </div>
      ))}
    </article>
  );
}
