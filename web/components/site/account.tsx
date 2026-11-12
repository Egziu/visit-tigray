"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Alert, Button, Card, Checkbox, Input, Loading, Select, Textarea } from "@/components/ui";
import { api, ApiError, errorMessage } from "@/lib/api";
import type { Me } from "@/lib/types";
import { useLoad } from "@/components/bureau/hooks";
import { useI18n, useSession } from "./providers";

type Msg = { tone: "success" | "danger" | "info"; text: string } | null;

function MfaVerify({ onDone }: { onDone: () => void }) {
  const { t } = useI18n();
  const [code, setCode] = useState("");
  const [msg, setMsg] = useState<Msg>(null);
  return (
    <form
      className="space-y-4"
      onSubmit={async (e) => {
        e.preventDefault();
        try {
          await api("/auth/mfa/verify", { json: { code } });
          onDone();
        } catch (err) {
          setMsg({ tone: "danger", text: errorMessage(err) });
        }
      }}
    >
      <h2 className="text-3xl">{t("account.mfaTitle")}</h2>
      <Input id="mfa-code" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6,8}" label={t("account.mfaCode")} value={code} onChange={(e) => setCode(e.target.value.trim())} required />
      <Button type="submit">{t("account.mfaVerify")}</Button>
      {msg && <Alert tone={msg.tone}>{msg.text}</Alert>}
    </form>
  );
}

export function MfaSetup({ onDone }: { onDone: () => void }) {
  const { t } = useI18n();
  const [setup, setSetup] = useState<{ otpauth_uri: string; secret: string } | null>(null);
  const [code, setCode] = useState("");
  const [msg, setMsg] = useState<Msg>(null);
  return (
    <div className="space-y-4">
      <h2 className="text-3xl">{t("account.mfaSetup")}</h2>
      <p className="text-muted">{t("account.mfaSetupBody")}</p>
      {!setup ? (
        <Button
          onClick={async () => {
            try {
              setSetup(await api("/auth/mfa/setup", { method: "POST" }));
            } catch (err) {
              setMsg({ tone: "danger", text: errorMessage(err) });
            }
          }}
        >
          {t("account.mfaSetup")}
        </Button>
      ) : (
        <form
          className="space-y-4"
          onSubmit={async (e) => {
            e.preventDefault();
            try {
              await api("/auth/mfa/enable", { json: { code } });
              setMsg({ tone: "success", text: t("account.mfaEnabled") });
              onDone();
            } catch (err) {
              setMsg({ tone: "danger", text: errorMessage(err) });
            }
          }}
        >
          <Input id="mfa-secret" label={t("account.mfaKey")} value={setup.secret} readOnly className="font-mono" onFocus={(e) => e.currentTarget.select()} />
          <p className="text-sm">
            <a href={setup.otpauth_uri} className="break-all underline">
              {t("account.mfaUri")}
            </a>
          </p>
          <Input id="mfa-enable-code" inputMode="numeric" autoComplete="one-time-code" label={t("account.mfaCode")} value={code} onChange={(e) => setCode(e.target.value.trim())} required />
          <Button type="submit">{t("account.mfaEnable")}</Button>
        </form>
      )}
      {msg && <Alert tone={msg.tone}>{msg.text}</Alert>}
    </div>
  );
}

function SignIn({ onSignedIn }: { onSignedIn: () => void }) {
  const { t, locale } = useI18n();
  const [mode, setMode] = useState<"signin" | "register" | "forgot">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [age, setAge] = useState(false);
  const [msg, setMsg] = useState<Msg>(null);
  const [step, setStep] = useState<"form" | "mfa" | "mfa-setup">("form");
  const [busy, setBusy] = useState(false);

  if (step === "mfa") return <MfaVerify onDone={onSignedIn} />;
  if (step === "mfa-setup") return <MfaSetup onDone={onSignedIn} />;

  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setMsg(null);
    try {
      await fn();
    } catch (err) {
      setMsg({ tone: "danger", text: errorMessage(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      {mode === "signin" && (
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            void run(async () => {
              const r = await api<{ mfa_required: boolean; mfa_setup_required: boolean }>("/auth/login", { json: { email, password } });
              if (r.mfa_required) setStep("mfa");
              else if (r.mfa_setup_required) setStep("mfa-setup");
              else onSignedIn();
            });
          }}
        >
          <h2 className="text-3xl">{t("account.signInTitle")}</h2>
          <Input id="email" type="email" autoComplete="email" label={t("account.email")} value={email} onChange={(e) => setEmail(e.target.value)} required />
          <Input id="password" type="password" autoComplete="current-password" label={t("account.password")} value={password} onChange={(e) => setPassword(e.target.value)} required />
          <div className="flex flex-wrap items-center gap-4">
            <Button type="submit" disabled={busy}>
              {t("common.signIn")}
            </Button>
            <button type="button" className="text-sm underline" onClick={() => setMode("forgot")}>
              {t("account.forgot")}
            </button>
          </div>
          <p className="text-sm text-muted">
            {t("account.noAccount")}{" "}
            <button type="button" className="underline" onClick={() => setMode("register")}>
              {t("account.registerTitle")}
            </button>
          </p>
          <button
            type="button"
            className="text-sm underline"
            onClick={() =>
              run(async () => {
                const r = await api<{ redirect_url: string }>("/auth/oidc/login");
                window.location.assign(r.redirect_url);
              })
            }
          >
            {t("account.sso")}
          </button>
        </form>
      )}
      {mode === "register" && (
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            void run(async () => {
              await api("/auth/register", { json: { email, password, display_name: name, locale, age_confirmed_16_plus: age } });
              setMsg({ tone: "success", text: t("account.registered") });
            });
          }}
        >
          <h2 className="text-3xl">{t("account.registerTitle")}</h2>
          <Input id="r-name" autoComplete="nickname" label={t("account.displayName")} value={name} onChange={(e) => setName(e.target.value)} required minLength={2} maxLength={80} />
          <Input id="r-email" type="email" autoComplete="email" label={t("account.email")} value={email} onChange={(e) => setEmail(e.target.value)} required />
          <Input id="r-password" type="password" autoComplete="new-password" minLength={12} label={t("account.password")} hint={t("account.passwordHint")} value={password} onChange={(e) => setPassword(e.target.value)} required />
          <Checkbox id="r-age" label={t("account.age")} checked={age} onChange={(e) => setAge(e.target.checked)} required />
          <Button type="submit" disabled={busy}>
            {t("account.register")}
          </Button>
          <p className="text-sm text-muted">
            {t("account.haveAccount")}{" "}
            <button type="button" className="underline" onClick={() => setMode("signin")}>
              {t("common.signIn")}
            </button>
          </p>
        </form>
      )}
      {mode === "forgot" && (
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            void run(async () => {
              await api("/auth/password/forgot", { json: { email } });
              setMsg({ tone: "success", text: t("account.resetSent") });
            });
          }}
        >
          <h2 className="text-3xl">{t("account.forgotTitle")}</h2>
          <Input id="f-email" type="email" autoComplete="email" label={t("account.email")} value={email} onChange={(e) => setEmail(e.target.value)} required />
          <div className="flex gap-4">
            <Button type="submit" disabled={busy}>
              {t("account.sendReset")}
            </Button>
            <button type="button" className="text-sm underline" onClick={() => setMode("signin")}>
              {t("common.back")}
            </button>
          </div>
        </form>
      )}
      {msg && <Alert tone={msg.tone}>{msg.text}</Alert>}
    </div>
  );
}

interface ProfileData {
  handle?: string | null;
  bio?: string | null;
  visibility?: string;
  display_name?: string;
}

function ProfileLoader({ me }: { me: Me }) {
  const { t } = useI18n();
  const { data, error, loading } = useLoad<ProfileData>("/me/profile");
  if (loading) return <Loading label={t("common.loading")} />;
  return <Profile key={data ? "loaded" : "empty"} me={me} initial={error ? null : data} />;
}

function Profile({ me, initial }: { me: Me; initial: ProfileData | null }) {
  const { t } = useI18n();
  const [name, setName] = useState(initial?.display_name ?? me.display_name);
  const [handle, setHandle] = useState(initial?.handle ?? "");
  const [bio, setBio] = useState(initial?.bio ?? "");
  const [visibility, setVisibility] = useState(initial?.visibility ?? "private");
  const [msg, setMsg] = useState<Msg>(null);
  return (
    <form
      className="space-y-4"
      onSubmit={async (e) => {
        e.preventDefault();
        try {
          await api("/me/profile", { method: "PUT", json: { display_name: name, handle: handle || undefined, bio, visibility } });
          setMsg({ tone: "success", text: t("account.profileSaved") });
        } catch (err) {
          setMsg({ tone: "danger", text: err instanceof ApiError && err.notAvailable ? t("common.notAvailableYet") : errorMessage(err) });
        }
      }}
    >
      <h2 className="text-2xl">{t("account.profile")}</h2>
      <Input id="p-name" label={t("account.displayName")} value={name} onChange={(e) => setName(e.target.value)} required maxLength={80} />
      <Input id="p-handle" label={t("account.handle")} value={handle} onChange={(e) => setHandle(e.target.value)} pattern="[a-z0-9_]{3,40}" maxLength={40} />
      <Textarea id="p-bio" label={t("account.bio")} value={bio} onChange={(e) => setBio(e.target.value)} maxLength={600} />
      <Select id="p-vis" label={t("account.visibility")} value={visibility} onChange={(e) => setVisibility(e.target.value)} options={[{ value: "private", label: t("account.private") }, { value: "public", label: t("account.public") }]} />
      <Button type="submit">{t("common.save")}</Button>
      {msg && <Alert tone={msg.tone}>{msg.text}</Alert>}
    </form>
  );
}

function MyData() {
  const { t } = useI18n();
  const { refresh } = useSession();
  const [confirm, setConfirm] = useState("");
  const [msg, setMsg] = useState<Msg>(null);
  return (
    <div className="space-y-4">
      <h2 className="text-2xl">{t("account.dataTitle")}</h2>
      <a href="/api/me/export" className="inline-flex min-h-[44px] items-center rounded-full border border-line px-5 py-2.5 text-sm" download>
        {t("account.export")}
      </a>
      <form
        className="space-y-3"
        onSubmit={async (e) => {
          e.preventDefault();
          if (confirm !== "DELETE") return;
          try {
            await api("/me", { method: "DELETE" });
            setMsg({ tone: "success", text: t("account.deleted") });
            await refresh();
          } catch (err) {
            setMsg({ tone: "danger", text: err instanceof ApiError && err.notAvailable ? t("common.notAvailableYet") : errorMessage(err) });
          }
        }}
      >
        <Input id="del" label={t("account.deleteConfirm")} value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="off" />
        <Button type="submit" variant="danger" disabled={confirm !== "DELETE"}>
          {t("account.delete")}
        </Button>
      </form>
      {msg && <Alert tone={msg.tone}>{msg.text}</Alert>}
    </div>
  );
}

export function AccountPanel() {
  const { t, locale } = useI18n();
  const { me, loading, refresh } = useSession();
  const [resent, setResent] = useState(false);
  if (loading) return <Loading label={t("common.loading")} />;
  if (!me)
    return (
      <Card className="max-w-xl">
        <SignIn onSignedIn={() => void refresh()} />
      </Card>
    );
  const staffPending = me.pending_permissions.length > 0;
  return (
    <div className="grid gap-8 lg:grid-cols-2">
      <Card className="space-y-4">
        <p className="text-lg">{t("account.signedInAs", { name: me.display_name })}</p>
        <p className="text-sm text-muted">{me.email}</p>
        {!me.email_verified && (
          <Alert tone="caution" title={t("account.emailUnverified")}>
            <button
              type="button"
              className="underline"
              onClick={async () => {
                await api("/auth/resend-verification", { method: "POST" }).catch(() => undefined);
                setResent(true);
              }}
            >
              {t("account.resend")}
            </button>
            {resent && <span role="status"> ✓</span>}
          </Alert>
        )}
        {staffPending && !me.mfa_verified && (me.mfa_enabled ? <MfaVerify onDone={() => void refresh()} /> : <MfaSetup onDone={() => void refresh()} />)}
        {(me.permissions.length > 0 || staffPending) && (
          <Link href={`/${locale}/bureau`} className="inline-block underline">
            {t("account.toBureau")}
          </Link>
        )}
        <Button
          variant="secondary"
          onClick={async () => {
            await api("/auth/logout", { method: "POST" }).catch(() => undefined);
            await refresh();
          }}
        >
          {t("common.signOut")}
        </Button>
      </Card>
      <Card>
        <ProfileLoader me={me} />
      </Card>
      <Card className="lg:col-span-2">
        <MyData />
      </Card>
    </div>
  );
}

export function VerifyEmail({ token }: { token: string }) {
  const { t } = useI18n();
  const [state, setState] = useState<Msg>({ tone: "info", text: t("account.verifying") });
  useEffect(() => {
    api("/auth/verify-email", { json: { token } })
      .then(() => setState({ tone: "success", text: t("account.verified") }))
      .catch((e) => setState({ tone: "danger", text: errorMessage(e) }));
  }, [token, t]);
  return state ? <Alert tone={state.tone}>{state.text}</Alert> : null;
}

export function ResetPassword({ token }: { token: string }) {
  const { t, locale } = useI18n();
  const [password, setPassword] = useState("");
  const [msg, setMsg] = useState<Msg>(null);
  return (
    <form
      className="max-w-lg space-y-4"
      onSubmit={async (e) => {
        e.preventDefault();
        try {
          await api("/auth/password/reset", { json: { token, password } });
          setMsg({ tone: "success", text: t("account.resetDone") });
        } catch (err) {
          setMsg({ tone: "danger", text: errorMessage(err) });
        }
      }}
    >
      <Input id="np" type="password" autoComplete="new-password" minLength={12} label={t("account.newPassword")} hint={t("account.passwordHint")} value={password} onChange={(e) => setPassword(e.target.value)} required />
      <Button type="submit">{t("common.save")}</Button>
      {msg && <Alert tone={msg.tone}>{msg.text}</Alert>}
      {msg?.tone === "success" && (
        <Link href={`/${locale}/account`} className="underline">
          {t("common.signIn")}
        </Link>
      )}
    </form>
  );
}
