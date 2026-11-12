// Browser-side API helper. Same-origin requests via the Next.js /api rewrite, so session
// cookies stay HttpOnly; unsafe methods echo the per-session CSRF token from the vt_csrf cookie.

import type { ApiErrorBody } from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** The endpoint is not deployed yet (planned contract) — render a "not available yet" state. */
  get notAvailable(): boolean {
    return this.status === 404 && this.code === "not_found" && this.message.toLowerCase() === "not found";
  }
}

const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export function readCookie(name: string, cookieString?: string): string | null {
  const src = cookieString ?? (typeof document !== "undefined" ? document.cookie : "");
  for (const part of src.split(";")) {
    const [k, ...v] = part.trim().split("=");
    if (k === name) return decodeURIComponent(v.join("="));
  }
  return null;
}

export async function parseError(res: Response): Promise<ApiError> {
  let body: Partial<ApiErrorBody> | null = null;
  try {
    body = (await res.json()) as ApiErrorBody;
  } catch {
    /* non-JSON error */
  }
  const e = body?.error;
  return new ApiError(res.status, e?.code ?? `http_${res.status}`, e?.message ?? `Request failed (${res.status})`, e?.details);
}

export interface ApiOptions extends Omit<RequestInit, "body"> {
  json?: unknown;
  body?: BodyInit | null;
}

export async function api<T = unknown>(path: string, opts: ApiOptions = {}): Promise<T> {
  const method = (opts.method ?? (opts.json !== undefined ? "POST" : "GET")).toUpperCase();
  const headers = new Headers(opts.headers);
  let body = opts.body ?? null;
  if (opts.json !== undefined) {
    headers.set("content-type", "application/json");
    body = JSON.stringify(opts.json);
  }
  if (UNSAFE.has(method)) {
    const csrf = readCookie("vt_csrf");
    if (csrf) headers.set("x-csrf-token", csrf);
  }
  let res: Response;
  try {
    res = await fetch(path.startsWith("/api") ? path : `/api${path}`, {
      ...opts,
      method,
      headers,
      body,
      credentials: "same-origin",
    });
  } catch {
    throw new ApiError(0, "network_error", "You appear to be offline or the service is unreachable.");
  }
  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return undefined as T;
  const ct = res.headers.get("content-type") ?? "";
  return (ct.includes("application/json") ? res.json() : res.text()) as Promise<T>;
}

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  if (e instanceof Error) return e.message;
  return "Something went wrong.";
}
