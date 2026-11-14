"use client";

import { useState } from "react";
import { Alert, Button, Input } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useI18n } from "./providers";

export function CalendarConverter() {
  const { t, locale } = useI18n();
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  return (
    <section className="rounded-[var(--radius)] border border-line bg-surface p-7" aria-labelledby="conv">
      <h2 id="conv" className="text-3xl">
        {t("travel.convert")}
      </h2>
      <form
        className="mt-5 flex flex-wrap items-end gap-4"
        onSubmit={async (e) => {
          e.preventDefault();
          setError(null);
          try {
            const r = await api<{ formatted: string }>(`/calendar/convert?gregorian=${date}&locale=${locale}`);
            setResult(r.formatted);
          } catch (err) {
            setResult(null);
            setError(errorMessage(err));
          }
        }}
      >
        <div className="min-w-[220px]">
          <Input id="greg" type="date" label={t("travel.gregorian")} value={date} onChange={(e) => setDate(e.target.value)} required />
        </div>
        <Button type="submit">{t("travel.convert")}</Button>
      </form>
      <div aria-live="polite" className="mt-4">
        {result && (
          <p className="text-lg">
            {t("travel.ethiopian")}: <strong className="font-display text-2xl text-earth">{result}</strong>
          </p>
        )}
        {error && <Alert tone="danger">{error}</Alert>}
      </div>
    </section>
  );
}
