import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, errorMessage, readCookie } from "@/lib/api";

type FetchArgs = [RequestInfo | URL, RequestInit | undefined];

describe("readCookie", () => {
  it("reads and decodes a named cookie", () => {
    expect(readCookie("vt_csrf", "a=1; vt_csrf=abc%2B123; b=2")).toBe("abc+123");
    expect(readCookie("missing", "a=1")).toBeNull();
  });
});

describe("api()", () => {
  const calls: FetchArgs[] = [];
  beforeEach(() => {
    calls.length = 0;
    vi.stubGlobal("document", { cookie: "vt_session=secret; vt_csrf=tok-123" });
  });
  afterEach(() => vi.unstubAllGlobals());

  function mockFetch(res: Response) {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (...args: FetchArgs) => {
        calls.push(args);
        return res;
      }),
    );
  }

  it("sends JSON with the CSRF header on unsafe methods", async () => {
    mockFetch(new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "content-type": "application/json" } }));
    const out = await api<{ ok: boolean }>("/auth/logout", { json: {} });
    expect(out.ok).toBe(true);
    const [url, init] = calls[0];
    expect(url).toBe("/api/auth/logout");
    expect(init?.method).toBe("POST");
    const headers = new Headers(init?.headers);
    expect(headers.get("x-csrf-token")).toBe("tok-123");
    expect(headers.get("content-type")).toBe("application/json");
    expect(init?.credentials).toBe("same-origin");
  });

  it("does not send the CSRF header on GET", async () => {
    mockFetch(new Response("[]", { status: 200, headers: { "content-type": "application/json" } }));
    await api("/destinations");
    expect(new Headers(calls[0][1]?.headers).get("x-csrf-token")).toBeNull();
  });

  it("surfaces structured API errors", async () => {
    mockFetch(
      new Response(JSON.stringify({ error: { code: "weak_password", message: "Use at least 12 characters.", details: null } }), {
        status: 422,
        headers: { "content-type": "application/json" },
      }),
    );
    const err = (await api("/auth/register", { json: {} }).catch((e: unknown) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(422);
    expect(err.code).toBe("weak_password");
    expect(errorMessage(err)).toBe("Use at least 12 characters.");
    expect(err.notAvailable).toBe(false);
  });

  it("recognises a not-yet-deployed endpoint", async () => {
    mockFetch(new Response(JSON.stringify({ error: { code: "not_found", message: "Not Found" } }), { status: 404 }));
    const err = (await api("/tie/status").catch((e: unknown) => e)) as ApiError;
    expect(err.notAvailable).toBe(true);
  });

  it("reports network failures as offline", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))));
    const err = (await api("/destinations").catch((e: unknown) => e)) as ApiError;
    expect(err.code).toBe("network_error");
    expect(err.status).toBe(0);
  });
});
