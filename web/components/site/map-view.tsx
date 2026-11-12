"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { Destination } from "@/lib/types";
import { useI18n } from "./providers";

type Pin = Pick<Destination, "slug" | "name" | "area" | "coordinates">;

// Approximate bounding box used for the schematic plot (not a cartographic product).
const BOX = { minLat: 12.2, maxLat: 14.95, minLng: 36.4, maxLng: 40.1 };

export function MapView({ pins }: { pins: Pin[] }) {
  const { t, locale } = useI18n();
  const styleUrl = process.env.NEXT_PUBLIC_MAP_STYLE_URL;
  const located = pins.filter((p) => p.coordinates);
  return (
    <div className="grid gap-8 lg:grid-cols-[1.5fr_1fr]">
      {styleUrl ? <MapLibre pins={located} styleUrl={styleUrl} /> : <Schematic pins={located} />}
      <div>
        <h2 className="text-2xl">{t("map.list")}</h2>
        <ul className="mt-4 divide-y divide-line rounded-[var(--radius)] border border-line bg-surface">
          {pins.map((p) => (
            <li key={p.slug} id={p.slug} className="flex items-center justify-between gap-3 px-4 py-3 target:bg-surface-2">
              <Link href={`/${locale}/destinations/${p.slug}`} className="font-medium underline-offset-4 hover:underline">
                {p.name}
              </Link>
              <span className="text-right text-xs text-muted">
                {p.coordinates
                  ? `${p.coordinates.lat.toFixed(p.coordinates.precision === "exact" ? 3 : 1)}, ${p.coordinates.lng.toFixed(p.coordinates.precision === "exact" ? 3 : 1)}${p.coordinates.precision === "approximate" ? ` (${t("map.approx")})` : ""}`
                  : t("map.noLocation")}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function Schematic({ pins }: { pins: Pin[] }) {
  const { t, locale } = useI18n();
  const x = (lng: number) => ((lng - BOX.minLng) / (BOX.maxLng - BOX.minLng)) * 600;
  const y = (lat: number) => ((BOX.maxLat - lat) / (BOX.maxLat - BOX.minLat)) * 460;
  return (
    <figure className="rounded-[var(--radius)] border border-line bg-surface p-4">
      <svg viewBox="0 0 600 460" role="img" aria-label={t("map.title")} className="h-auto w-full">
        <rect width="600" height="460" rx="12" fill="var(--color-surface-2)" />
        {[0, 1, 2, 3, 4].map((i) => (
          <line key={`h${i}`} x1="0" x2="600" y1={i * 115} y2={i * 115} stroke="var(--color-line)" />
        ))}
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <line key={`v${i}`} y1="0" y2="460" x1={i * 120} x2={i * 120} stroke="var(--color-line)" />
        ))}
        {pins.map((p) => {
          const c = p.coordinates!;
          const cx = x(c.lng);
          const cy = y(c.lat);
          return (
            <a key={p.slug} href={`/${locale}/destinations/${p.slug}`} aria-label={p.name}>
              {c.precision === "approximate" ? (
                <circle cx={cx} cy={cy} r="16" fill="var(--color-sandstone)" fillOpacity=".25" stroke="var(--color-earth)" strokeDasharray="4 3" />
              ) : (
                <circle cx={cx} cy={cy} r="6" fill="var(--color-forest)" />
              )}
              <text x={cx + 10} y={cy - 8} fontSize="13" fill="var(--color-ink)">
                {p.name}
              </text>
            </a>
          );
        })}
      </svg>
      <figcaption className="mt-3 text-sm text-muted">{t("map.fallback")}</figcaption>
    </figure>
  );
}

function MapLibre({ pins, styleUrl }: { pins: Pin[]; styleUrl: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const { t } = useI18n();
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let map: { remove: () => void } | undefined;
    let cancelled = false;
    (async () => {
      try {
        const maplibregl = await import("maplibre-gl");
        await import("maplibre-gl/dist/maplibre-gl.css");
        if (cancelled || !ref.current) return;
        const m = new maplibregl.Map({ container: ref.current, style: styleUrl, center: [39.0, 13.6], zoom: 6.6, attributionControl: { compact: false } });
        m.addControl(new maplibregl.NavigationControl(), "top-right");
        for (const p of pins) {
          const c = p.coordinates!;
          new maplibregl.Marker({ color: c.precision === "approximate" ? "#b98a5a" : "#102d27" })
            .setLngLat([c.lng, c.lat])
            .setPopup(new maplibregl.Popup().setText(p.name))
            .addTo(m);
        }
        map = m;
      } catch {
        setFailed(true);
      }
    })();
    return () => {
      cancelled = true;
      map?.remove();
    };
  }, [pins, styleUrl]);
  if (failed) return <Schematic pins={pins} />;
  return <div ref={ref} className="h-[520px] w-full overflow-hidden rounded-[var(--radius)] border border-line" role="region" aria-label={t("map.title")} />;
}
