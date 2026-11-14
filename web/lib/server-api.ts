import "server-only";

// Server-side fetch to the API origin. Never throws: pages render an honest
// "service unavailable" state instead of failing or showing invented data.

export const API_ORIGIN = process.env.API_ORIGIN ?? "http://localhost:8000";

export type Result<T> = { ok: true; data: T } | { ok: false; status: number; message: string };

export async function serverGet<T>(path: string, revalidate = 60): Promise<Result<T>> {
  try {
    const res = await fetch(`${API_ORIGIN}${path}`, {
      next: { revalidate },
      headers: { accept: "application/json" },
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) {
      let message = `HTTP ${res.status}`;
      try {
        const body = await res.json();
        message = body?.error?.message ?? message;
      } catch {
        /* ignore */
      }
      return { ok: false, status: res.status, message };
    }
    return { ok: true, data: (await res.json()) as T };
  } catch {
    return { ok: false, status: 0, message: "The Visit Tigray service is unreachable right now." };
  }
}
