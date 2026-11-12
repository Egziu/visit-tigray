// Per-device display preferences (theme, data saver) in localStorage, exposed as an
// external store so React reads them without setState-in-effect and without hydration flicker.

export type Theme = "system" | "light" | "dark";

const listeners = new Set<() => void>();
function emit() {
  listeners.forEach((l) => l());
}

export function subscribePrefs(cb: () => void): () => void {
  listeners.add(cb);
  const onStorage = (e: StorageEvent) => {
    if (e.key === "vt_theme" || e.key === "vt_saver") cb();
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(cb);
    window.removeEventListener("storage", onStorage);
  };
}

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function getTheme(): Theme {
  const v = read("vt_theme");
  return v === "light" || v === "dark" ? v : "system";
}

export function setTheme(next: Theme): void {
  try {
    if (next === "system") localStorage.removeItem("vt_theme");
    else localStorage.setItem("vt_theme", next);
  } catch {
    /* storage unavailable: still apply for this page view */
  }
  if (next === "system") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = next;
  emit();
}

export function getSaver(): boolean {
  return read("vt_saver") === "on";
}

export function setSaver(on: boolean): void {
  try {
    if (on) localStorage.setItem("vt_saver", "on");
    else localStorage.removeItem("vt_saver");
  } catch {
    /* ignore */
  }
  if (on) document.documentElement.dataset.saver = "on";
  else delete document.documentElement.dataset.saver;
  emit();
}
