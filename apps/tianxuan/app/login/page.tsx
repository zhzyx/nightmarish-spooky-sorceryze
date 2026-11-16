"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { saveSession } from "@/lib/auth";
import { useI18n } from "@/lib/i18n-client";

const API_BASE = process.env.NEXT_PUBLIC_TIANXUAN_API_BASE?.replace(/\/$/, "") ?? "";

function apiBase(): string {
  return typeof window === "undefined" ? API_BASE : "";
}

const inputStyle = {
  padding: "8px 12px",
  borderRadius: "6px",
  border: "1px solid rgba(245, 242, 234, 0.18)",
  background: "transparent",
  color: "inherit",
} as const;

const fieldStyle = {
  display: "flex",
  flexDirection: "column",
  gap: "6px",
} as const;

export default function LoginPage() {
  const router = useRouter();
  const { t, locale } = useI18n();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${apiBase()}/api/v1/auth/session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password }),
      });
      if (!response.ok) {
        setError(response.status === 401 ? t("login.invalid") : `${t("login.failed")} (${response.status})`);
        return;
      }
      const body = (await response.json()) as { token?: string };
      if (!body.token) {
        setError(t("login.missingToken"));
        return;
      }
      saveSession(body.token);
      router.push("/repos");
      router.refresh();
    } catch {
      setError(t("login.network"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page-stack">
      <header className="page-header">
        <div className="page-title-group">
          <p className="eyebrow">
            <span className="eyebrow-rule" aria-hidden="true" />
            TIANXUAN · SESSION
          </p>
          <h1>
            {t("login.title")}
            {locale === "zh" ? <span className="title-period">。</span> : null}
          </h1>
          <p className="page-lede">{t("login.lede")}</p>
        </div>
      </header>

      <section className="panel" aria-labelledby="login-title">
        <div className="section-heading">
          <div>
            <p className="section-kicker">SESSION</p>
            <h2 id="login-title">{t("login.session")}</h2>
          </div>
          <span className="section-note">POST /api/v1/auth/session</span>
        </div>
        <form
          onSubmit={submit}
          style={{ display: "flex", flexDirection: "column", gap: "12px", maxWidth: "420px", padding: "16px 26px 22px" }}
        >
          <label style={fieldStyle}>
            {t("login.email")}
            <input
              type="email"
              required
              autoComplete="username"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              style={inputStyle}
            />
          </label>
          <label style={fieldStyle}>
            {t("login.password")}
            <input
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              style={inputStyle}
            />
          </label>
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? t("login.busy") : t("login.submit")}
          </button>
          {error ? <p style={{ color: "#D48B80" }}>{error}</p> : null}
        </form>
      </section>
    </div>
  );
}
