"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, ApiError } from "@/lib/api";
import { getDict, translate, type MsgKey } from "@/lib/i18n";
import type { Me, PublicConfig } from "@/lib/types";

/* ------------------------------------------------------------------ i18n */

interface I18nValue {
  locale: string;
  t: (key: MsgKey, vars?: Record<string, string | number>) => string;
}
const I18nCtx = createContext<I18nValue | null>(null);

export function useI18n(): I18nValue {
  const v = useContext(I18nCtx);
  if (!v) throw new Error("useI18n outside provider");
  return v;
}

/* ------------------------------------------------------------------ session */

interface SessionValue {
  me: Me | null;
  loading: boolean;
  refresh: () => Promise<void>;
  config: PublicConfig | null;
  has: (perm: string) => boolean;
}
const SessionCtx = createContext<SessionValue | null>(null);

export function useSession(): SessionValue {
  const v = useContext(SessionCtx);
  if (!v) throw new Error("useSession outside provider");
  return v;
}

export function Providers({ locale, children }: { locale: string; children: ReactNode }) {
  const dict = useMemo(() => getDict(locale), [locale]);
  const i18n = useMemo<I18nValue>(
    () => ({ locale, t: (key, vars) => translate(dict, key, vars) }),
    [dict, locale],
  );
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [config, setConfig] = useState<PublicConfig | null>(null);

  const refresh = useCallback(async () => {
    try {
      setMe(await api<Me>("/me"));
    } catch (e) {
      if (!(e instanceof ApiError) || e.status === 401 || e.status === 0) setMe(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    api<PublicConfig>("/config/public").then(setConfig).catch(() => setConfig(null));
  }, [refresh]);

  const session = useMemo<SessionValue>(
    () => ({ me, loading, refresh, config, has: (p) => !!me?.permissions.includes(p) }),
    [me, loading, refresh, config],
  );

  return (
    <I18nCtx.Provider value={i18n}>
      <SessionCtx.Provider value={session}>{children}</SessionCtx.Provider>
    </I18nCtx.Provider>
  );
}
