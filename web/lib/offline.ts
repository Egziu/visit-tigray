// Offline storage: saved content packs (destinations, itineraries) and a submission outbox.
// IndexedDB only — never used for bureau data or credentials. Every record carries savedAt.

const DB_NAME = "visit-tigray";
const DB_VERSION = 1;
export const STORES = { saved: "saved", outbox: "outbox" } as const;

export interface SavedItem {
  key: string; // e.g. "destination:aksum:en"
  kind: "destination" | "itinerary";
  title: string;
  href: string;
  locale: string;
  savedAt: string;
  sourceUpdatedAt?: string | null;
  data: unknown;
}

export interface OutboxItem {
  id: string;
  kind: "memory";
  createdAt: string;
  payload: Record<string, unknown>;
  attempts: number;
  lastError?: string;
}

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") return reject(new Error("IndexedDB unavailable"));
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORES.saved)) db.createObjectStore(STORES.saved, { keyPath: "key" });
      if (!db.objectStoreNames.contains(STORES.outbox)) db.createObjectStore(STORES.outbox, { keyPath: "id" });
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function tx<T>(store: string, mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest<T> | void): Promise<T | undefined> {
  const db = await open();
  return new Promise((resolve, reject) => {
    const t = db.transaction(store, mode);
    const s = t.objectStore(store);
    const req = fn(s);
    t.oncomplete = () => {
      resolve(req ? (req as IDBRequest<T>).result : undefined);
      db.close();
    };
    t.onerror = () => reject(t.error);
  });
}

export const saveItem = (item: SavedItem) => tx(STORES.saved, "readwrite", (s) => s.put(item));
export const getItem = (key: string) => tx<SavedItem>(STORES.saved, "readonly", (s) => s.get(key));
export const listItems = async () => ((await tx<SavedItem[]>(STORES.saved, "readonly", (s) => s.getAll())) ?? []).sort((a, b) => b.savedAt.localeCompare(a.savedAt));
export const removeItem = (key: string) => tx(STORES.saved, "readwrite", (s) => s.delete(key));
export const clearSaved = () => tx(STORES.saved, "readwrite", (s) => s.clear());

export const queue = (item: OutboxItem) => tx(STORES.outbox, "readwrite", (s) => s.put(item));
export const listOutbox = async () => (await tx<OutboxItem[]>(STORES.outbox, "readonly", (s) => s.getAll())) ?? [];
export const removeOutbox = (id: string) => tx(STORES.outbox, "readwrite", (s) => s.delete(id));
export const clearOutbox = () => tx(STORES.outbox, "readwrite", (s) => s.clear());

/** Remove everything this app stored on the device (saved packs, outbox, cached API responses). */
export async function clearAllOfflineData(): Promise<void> {
  await clearSaved().catch(() => undefined);
  await clearOutbox().catch(() => undefined);
  if (typeof caches !== "undefined") {
    for (const name of await caches.keys()) if (name.startsWith("vt-")) await caches.delete(name);
  }
}

export async function storageEstimate(): Promise<{ used: number; quota: number } | null> {
  if (typeof navigator === "undefined" || !navigator.storage?.estimate) return null;
  const e = await navigator.storage.estimate();
  return { used: e.usage ?? 0, quota: e.quota ?? 0 };
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(0)} KB`;
  if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MB`;
  return `${(n / 1024 ** 3).toFixed(1)} GB`;
}

/** Try to submit queued memory drafts. Returns number sent. */
export async function flushOutbox(send: (item: OutboxItem) => Promise<void>): Promise<number> {
  let sent = 0;
  for (const item of await listOutbox()) {
    try {
      await send(item);
      await removeOutbox(item.id);
      sent++;
    } catch (e) {
      await queue({ ...item, attempts: item.attempts + 1, lastError: e instanceof Error ? e.message : String(e) });
    }
  }
  return sent;
}
