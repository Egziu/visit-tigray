"use client";

import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { cn } from "./index";

/* ------------------------------------------------------------------ Dialog
   Native <dialog> gives focus trapping, Escape handling and inert background for free. */

export function Dialog({
  open,
  onClose,
  title,
  children,
  closeLabel,
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  children: ReactNode;
  closeLabel: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onClose={onClose}
      className="m-auto w-[min(92vw,560px)] rounded-[var(--radius)] border border-line bg-surface p-0 text-ink shadow-2xl backdrop:bg-black/50"
    >
      <div className="flex items-start justify-between gap-4 border-b border-line px-6 py-4">
        <h2 id={titleId} className="text-2xl">
          {title}
        </h2>
        <button type="button" onClick={onClose} className="rounded-full px-3 py-1 text-sm hover:bg-surface-2" aria-label={closeLabel}>
          ✕
        </button>
      </div>
      <div className="px-6 py-5">{children}</div>
    </dialog>
  );
}

/* ------------------------------------------------------------------ Tabs (WAI-ARIA tabs pattern) */

export function Tabs({
  tabs,
  label,
  initial,
}: {
  tabs: { id: string; label: ReactNode; content: ReactNode }[];
  label: string;
  initial?: string;
}) {
  const [active, setActive] = useState(initial ?? tabs[0]?.id);
  const base = useId();
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  function onKey(e: KeyboardEvent, i: number) {
    let next = i;
    if (e.key === "ArrowRight") next = (i + 1) % tabs.length;
    else if (e.key === "ArrowLeft") next = (i - 1 + tabs.length) % tabs.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = tabs.length - 1;
    else return;
    e.preventDefault();
    setActive(tabs[next].id);
    refs.current[tabs[next].id]?.focus();
  }
  return (
    <div>
      <div role="tablist" aria-label={label} className="flex flex-wrap gap-1 border-b border-line">
        {tabs.map((t, i) => (
          <button
            key={t.id}
            ref={(el) => {
              refs.current[t.id] = el;
            }}
            role="tab"
            type="button"
            id={`${base}-tab-${t.id}`}
            aria-selected={active === t.id}
            aria-controls={`${base}-panel-${t.id}`}
            tabIndex={active === t.id ? 0 : -1}
            onClick={() => setActive(t.id)}
            onKeyDown={(e) => onKey(e, i)}
            className={cn(
              "-mb-px min-h-[44px] border-b-2 px-4 py-2 text-sm font-medium",
              active === t.id ? "border-forest text-ink" : "border-transparent text-muted hover:text-ink",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tabs.map((t) => (
        <div
          key={t.id}
          role="tabpanel"
          id={`${base}-panel-${t.id}`}
          aria-labelledby={`${base}-tab-${t.id}`}
          hidden={active !== t.id}
          className="pt-6"
          tabIndex={0}
        >
          {active === t.id && t.content}
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ Toggle chip */

export function ToggleChip({ pressed, onToggle, children }: { pressed: boolean; onToggle: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onToggle}
      className={cn(
        "min-h-[44px] rounded-full border px-4 py-2 text-sm transition-colors",
        pressed ? "border-forest bg-forest text-on-forest" : "border-line bg-surface hover:border-sandstone",
      )}
    >
      {children}
    </button>
  );
}
