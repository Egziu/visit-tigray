"use client";

import { useCallback, useEffect, useState } from "react";
import { Alert } from "@/components/ui";
import { api, ApiError, errorMessage } from "@/lib/api";
import { useI18n } from "@/components/site/providers";

interface LoadState<T> {
  path: string | null;
  data: T | null;
  error: unknown;
}

/**
 * Fetch JSON for `path` (null = skip). State is keyed by path, so a path change never shows
 * stale data, and effects only set state from promise callbacks.
 */
export function useLoad<T>(path: string | null) {
  const [state, setState] = useState<LoadState<T>>({ path: null, data: null, error: null });
  useEffect(() => {
    if (!path) return;
    let cancelled = false;
    api<T>(path).then(
      (data) => !cancelled && setState({ path, data, error: null }),
      (error) => !cancelled && setState({ path, data: null, error }),
    );
    return () => {
      cancelled = true;
    };
  }, [path]);
  const reload = useCallback(async () => {
    if (!path) return;
    try {
      const data = await api<T>(path);
      setState({ path, data, error: null });
    } catch (error) {
      setState({ path, data: null, error });
    }
  }, [path]);
  const setData = useCallback((data: T) => setState({ path, data, error: null }), [path]);
  const current = state.path === path;
  return {
    data: current ? state.data : null,
    error: current ? state.error : null,
    loading: !!path && !current,
    reload,
    setData,
  };
}

export function LoadError({ error }: { error: unknown }) {
  const { t } = useI18n();
  if (!error) return null;
  if (error instanceof ApiError && error.notAvailable) return <Alert tone="caution">{t("common.notAvailableYet")}</Alert>;
  if (error instanceof ApiError && error.status === 403) return <Alert tone="caution">{t("bureau.dashboard.unavailable")}</Alert>;
  return <Alert tone="danger">{errorMessage(error)}</Alert>;
}

/** Run an action and report a status message (success or the API error message). */
export function useAction() {
  const [msg, setMsg] = useState<{ tone: "success" | "danger"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  async function run(fn: () => Promise<unknown>, ok: string) {
    setBusy(true);
    setMsg(null);
    try {
      await fn();
      setMsg({ tone: "success", text: ok });
      return true;
    } catch (e) {
      setMsg({ tone: "danger", text: errorMessage(e) });
      return false;
    } finally {
      setBusy(false);
    }
  }
  const view = msg ? (
    <Alert tone={msg.tone} role="status" className="mt-3">
      {msg.text}
    </Alert>
  ) : null;
  return { run, busy, view, setMsg };
}
