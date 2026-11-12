"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { NotificationItem } from "@/lib/types";
import { useI18n, useSession } from "./providers";

const POLL_MS = 60_000;

/** Header bell: unread count + dropdown. Polls every 60 s while signed in and the tab is visible. */
export function NotificationBell() {
  const { t, locale } = useI18n();
  const { me } = useSession();
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [available, setAvailable] = useState(true);
  const boxRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try {
      const r = await api<{ items: NotificationItem[]; unread: number }>("/me/notifications");
      setItems(r.items);
      setUnread(r.unread);
    } catch {
      setAvailable(false);
    }
  }, []);

  useEffect(() => {
    if (!me) return;
    const first = setTimeout(load, 0);
    const id = setInterval(() => {
      if (document.visibilityState === "visible") void load();
    }, POLL_MS);
    return () => {
      clearTimeout(first);
      clearInterval(id);
    };
  }, [me, load]);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  if (!me || !available) return null;

  async function markAll() {
    await api("/me/notifications/read", { json: { ids: [] } }).catch(() => undefined);
    setUnread(0);
    setItems((xs) => xs.map((x) => ({ ...x, read: true })));
  }

  return (
    <div ref={boxRef} className="relative" onKeyDown={(e) => e.key === "Escape" && setOpen(false)}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls="notif-panel"
        aria-label={unread ? t("notif.labelUnread", { n: unread }) : t("notif.label")}
        onClick={() => setOpen((o) => !o)}
        className="relative inline-flex min-h-[40px] min-w-[40px] items-center justify-center rounded-full border border-line bg-surface"
      >
        <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.7">
          <path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
          <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
        </svg>
        {unread > 0 && (
          <span aria-hidden="true" className="absolute -right-1 -top-1 min-w-[20px] rounded-full bg-forest px-1.5 text-center text-[0.7rem] font-semibold leading-5 text-on-forest">
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>
      {open && (
        <div id="notif-panel" className="absolute right-0 top-full z-50 mt-2 w-[min(92vw,360px)] rounded-xl border border-line bg-surface shadow-[var(--shadow)]">
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <p className="font-display text-lg">{t("notif.title")}</p>
            {unread > 0 && (
              <button type="button" onClick={markAll} className="text-sm underline">
                {t("notif.markAll")}
              </button>
            )}
          </div>
          {items.length === 0 ? (
            <p className="px-4 py-6 text-sm text-muted">{t("notif.empty")}</p>
          ) : (
            <ul className="max-h-[60vh] divide-y divide-line overflow-y-auto">
              {items.map((n) => {
                const inner = (
                  <>
                    <p className={n.read ? "text-sm" : "text-sm font-semibold"}>{n.title}</p>
                    {n.body && <p className="mt-0.5 line-clamp-2 text-sm text-muted">{n.body}</p>}
                    <p className="mt-1 text-xs text-muted">{formatDateTime(n.created_at, locale)}</p>
                  </>
                );
                const href = n.link && n.link.startsWith("/") && !n.link.startsWith("//")
                  ? n.link.startsWith(`/${locale}/`) || n.link.startsWith("/api/") ? n.link : `/${locale}${n.link}`
                  : null;
                return (
                  <li key={n.id} className={n.read ? "" : "bg-surface-2/50"}>
                    {href ? (
                      <Link href={href} onClick={() => setOpen(false)} className="block px-4 py-3 hover:bg-surface-2">
                        {inner}
                      </Link>
                    ) : (
                      <div className="px-4 py-3">{inner}</div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
