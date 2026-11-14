import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

export function cn(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

/* ------------------------------------------------------------------ Button */

type Variant = "primary" | "secondary" | "ghost" | "danger" | "gold";
type Size = "sm" | "md" | "lg";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-forest text-on-forest hover:bg-forest-2",
  secondary: "border border-line bg-surface text-ink hover:border-sandstone",
  ghost: "text-ink hover:bg-surface-2",
  danger: "bg-danger text-white hover:opacity-90",
  gold: "bg-gold text-[#1c211d] hover:brightness-105",
};
const SIZES: Record<Size, string> = {
  sm: "px-3 py-1.5 text-sm",
  md: "px-5 py-2.5 text-[0.95rem]",
  lg: "px-7 py-3.5 text-base",
};

export function buttonClass(variant: Variant = "primary", size: Size = "md", extra?: string) {
  return cn(
    "inline-flex items-center justify-center gap-2 rounded-full font-medium tracking-wide transition-colors",
    "disabled:cursor-not-allowed disabled:opacity-55 min-h-[44px]",
    VARIANTS[variant],
    SIZES[size],
    extra,
  );
}

export function Button({
  variant = "primary",
  size = "md",
  className,
  type = "button",
  ...rest
}: ComponentProps<"button"> & { variant?: Variant; size?: Size }) {
  return <button type={type} className={buttonClass(variant, size, className)} {...rest} />;
}

export function ButtonLink({
  variant = "primary",
  size = "md",
  className,
  ...rest
}: ComponentProps<typeof Link> & { variant?: Variant; size?: Size }) {
  return <Link className={buttonClass(variant, size, className)} {...rest} />;
}

/* ------------------------------------------------------------------ Card / Badge */

export function Card({ className, ...rest }: ComponentProps<"div">) {
  return <div className={cn("rounded-[var(--radius)] border border-line bg-surface p-6 shadow-[var(--shadow)]", className)} {...rest} />;
}

type Tone = "neutral" | "info" | "caution" | "danger" | "success" | "earth" | "forest";
const TONES: Record<Tone, string> = {
  neutral: "border-line text-muted",
  info: "border-info/40 text-info",
  caution: "border-caution/50 text-caution",
  danger: "border-danger/50 text-danger",
  success: "border-success/50 text-success",
  earth: "border-earth/40 text-earth",
  forest: "border-forest/40 text-forest",
};

export function Badge({ tone = "neutral", className, children }: { tone?: Tone; className?: string; children: ReactNode }) {
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium uppercase tracking-[0.08em]", TONES[tone], className)}>
      {children}
    </span>
  );
}

/* ------------------------------------------------------------------ Alert */

export function Alert({
  tone = "info",
  title,
  children,
  className,
  role,
}: {
  tone?: "info" | "caution" | "danger" | "success";
  title?: ReactNode;
  children?: ReactNode;
  className?: string;
  role?: "alert" | "status";
}) {
  const border = { info: "border-info", caution: "border-caution", danger: "border-danger", success: "border-success" }[tone];
  return (
    <div role={role ?? (tone === "danger" ? "alert" : "status")} className={cn("rounded-lg border-l-4 bg-surface-2 px-4 py-3 text-[0.95rem]", border, className)}>
      {title && <p className="font-semibold">{title}</p>}
      {children && <div className={title ? "mt-1 text-muted" : ""}>{children}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------ Form fields */

interface FieldBase {
  label: ReactNode;
  hint?: ReactNode;
  error?: string | null;
  id: string;
}

function FieldShell({ label, hint, error, id, children, required }: FieldBase & { children: ReactNode; required?: boolean }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
        {required && <span aria-hidden="true" className="text-earth"> *</span>}
      </label>
      {children}
      {hint && !error && (
        <p id={`${id}-hint`} className="text-sm text-muted">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="text-sm text-danger" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

const INPUT =
  "w-full rounded-lg border border-line bg-surface px-3.5 py-2.5 text-ink placeholder:text-muted/80 focus:border-forest min-h-[44px] aria-[invalid=true]:border-danger";

function describedBy(id: string, hint?: ReactNode, error?: string | null) {
  return error ? `${id}-error` : hint ? `${id}-hint` : undefined;
}

export function Input({ label, hint, error, id, className, ...rest }: FieldBase & ComponentProps<"input">) {
  return (
    <FieldShell label={label} hint={hint} error={error} id={id} required={rest.required}>
      <input id={id} aria-invalid={!!error} aria-describedby={describedBy(id, hint, error)} className={cn(INPUT, className)} {...rest} />
    </FieldShell>
  );
}

export function Textarea({ label, hint, error, id, className, ...rest }: FieldBase & ComponentProps<"textarea">) {
  return (
    <FieldShell label={label} hint={hint} error={error} id={id} required={rest.required}>
      <textarea id={id} aria-invalid={!!error} aria-describedby={describedBy(id, hint, error)} className={cn(INPUT, "min-h-[120px]", className)} {...rest} />
    </FieldShell>
  );
}

export function Select({
  label,
  hint,
  error,
  id,
  className,
  options,
  ...rest
}: FieldBase & ComponentProps<"select"> & { options: { value: string; label: string }[] }) {
  return (
    <FieldShell label={label} hint={hint} error={error} id={id} required={rest.required}>
      <select id={id} aria-invalid={!!error} aria-describedby={describedBy(id, hint, error)} className={cn(INPUT, className)} {...rest}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </FieldShell>
  );
}

export function Checkbox({ label, id, error, ...rest }: { label: ReactNode; id: string; error?: string | null } & ComponentProps<"input">) {
  return (
    <div>
      <div className="flex items-start gap-3">
        <input
          id={id}
          type="checkbox"
          aria-invalid={!!error}
          aria-describedby={error ? `${id}-error` : undefined}
          className="mt-1 h-5 w-5 shrink-0 accent-[var(--color-forest)]"
          {...rest}
        />
        <label htmlFor={id} className="text-[0.95rem]">
          {label}
        </label>
      </div>
      {error && (
        <p id={`${id}-error`} role="alert" className="mt-1 text-sm text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ Table / Empty / Skeleton */

export function Table({ caption, children, className }: { caption: ReactNode; children: ReactNode; className?: string }) {
  return (
    <div className={cn("overflow-x-auto rounded-[var(--radius)] border border-line bg-surface", className)}>
      <table className="w-full border-collapse text-left text-sm [&_td]:border-t [&_td]:border-line [&_td]:px-4 [&_td]:py-3 [&_th]:px-4 [&_th]:py-3 [&_th]:font-semibold [&_th]:text-muted">
        <caption className="sr-only">{caption}</caption>
        {children}
      </table>
    </div>
  );
}

export function EmptyState({ title, children, action }: { title: ReactNode; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="rounded-[var(--radius)] border border-dashed border-line px-6 py-12 text-center">
      <p className="font-display text-2xl">{title}</p>
      {children && <div className="mx-auto mt-2 max-w-prose text-muted">{children}</div>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cn("animate-pulse rounded-lg bg-surface-2", className)} />;
}

export function Loading({ label }: { label: string }) {
  return (
    <div role="status" aria-live="polite" className="flex items-center gap-3 py-8 text-muted">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-line border-t-forest" aria-hidden="true" />
      {label}
    </div>
  );
}

export function SectionHeading({ eyebrow, title, lead, id }: { eyebrow?: ReactNode; title: ReactNode; lead?: ReactNode; id?: string }) {
  return (
    <div className="mb-10 max-w-3xl">
      {eyebrow && <p className="mb-3 text-xs font-semibold uppercase tracking-[0.22em] text-earth">{eyebrow}</p>}
      <h2 id={id} className="text-4xl sm:text-5xl">
        {title}
      </h2>
      {lead && <p className="mt-4 text-lg text-muted">{lead}</p>}
    </div>
  );
}

export function PageHeader({ eyebrow, title, lead, children }: { eyebrow?: ReactNode; title: ReactNode; lead?: ReactNode; children?: ReactNode }) {
  return (
    <div className="border-b border-line bg-surface-2/60">
      <div className="mx-auto max-w-6xl px-5 py-14 sm:px-8 sm:py-20">
        {eyebrow && <p className="mb-3 text-xs font-semibold uppercase tracking-[0.22em] text-earth">{eyebrow}</p>}
        <h1 className="reveal text-5xl sm:text-6xl">{title}</h1>
        {lead && <p className="reveal reveal-delay mt-5 max-w-2xl text-lg text-muted">{lead}</p>}
        {children}
      </div>
    </div>
  );
}

export function Container({ className, ...rest }: ComponentProps<"div">) {
  return <div className={cn("mx-auto w-full max-w-6xl px-5 sm:px-8", className)} {...rest} />;
}
