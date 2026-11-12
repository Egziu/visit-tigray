"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { flushOutbox, getItem, saveItem, type OutboxItem, type SavedItem } from "@/lib/offline";
import { formatDateTime } from "@/lib/format";
import { buttonClass } from "@/components/ui";
import { useI18n } from "./providers";

export async function sendQueuedMemory(item: OutboxItem): Promise<void> {
  await api("/memories", { method: "POST", json: item.payload });
}

/** Registers /sw.js in production builds and flushes the outbox when connectivity returns. */
export function ServiceWorkerRegistration() {
  useEffect(() => {
    if ("serviceWorker" in navigator && process.env.NODE_ENV === "production") {
      navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => undefined);
    }
    const onOnline = () => void flushOutbox(sendQueuedMemory).catch(() => undefined);
    window.addEventListener("online", onOnline);
    if (navigator.onLine) onOnline();
    return () => window.removeEventListener("online", onOnline);
  }, []);
  return null;
}

export function useOnline(): boolean {
  const [online, setOnline] = useState(true);
  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);
  return online;
}

export function OfflineBanner() {
  const { t } = useI18n();
  const online = useOnline();
  if (online) return null;
  return (
    <div role="status" className="bg-caution px-5 py-2 text-center text-sm font-medium text-white">
      {t("offline.youAreOffline")}
    </div>
  );
}

/** "Save for offline" — stores the page data in IndexedDB and asks the SW to cache the page. */
export function SaveOffline({ item }: { item: Omit<SavedItem, "savedAt"> }) {
  const { t, locale } = useI18n();
  const [savedAt, setSavedAt] = useState<string | null>(null);
  useEffect(() => {
    getItem(item.key)
      .then((s) => setSavedAt(s?.savedAt ?? null))
      .catch(() => undefined);
  }, [item.key]);
  async function save() {
    const now = new Date().toISOString();
    await saveItem({ ...item, savedAt: now });
    navigator.serviceWorker?.controller?.postMessage({ type: "cache-urls", urls: [item.href] });
    setSavedAt(now);
  }
  return (
    <div className="no-print flex flex-wrap items-center gap-3">
      <button type="button" onClick={save} className={buttonClass("secondary", "sm")}>
        {savedAt ? "✓ " : ""}
        {t("destinations.saveOffline")}
      </button>
      {savedAt && (
        <span role="status" className="text-sm text-muted">
          {t("destinations.savedOffline")} · {formatDateTime(savedAt, locale)}
        </span>
      )}
    </div>
  );
}
