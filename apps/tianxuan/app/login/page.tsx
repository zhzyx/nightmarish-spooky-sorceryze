"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { saveSession } from "@/lib/auth";

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
        setError(response.status === 401 ? "邮箱或密码不正确" : `登录失败（${response.status}）`);
        return;
      }
      const body = (await response.json()) as { token?: string };
      if (!body.token) {
        setError("登录响应缺少 token");
        return;
      }
      saveSession(body.token);
      router.push("/repos");
      router.refresh();
    } catch {
      setError("无法连接服务器");
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
            登录<span className="title-period">。</span>
          </h1>
          <p className="page-lede">
            使用已注册账号换取会话 token。登录后浏览器请求携带 Bearer token；服务端渲染可配置
            <code> TIANXUAN_TOKEN </code>。
          </p>
        </div>
      </header>

      <section className="panel" aria-labelledby="login-title">
        <div className="section-heading">
          <div>
            <p className="section-kicker">SESSION</p>
            <h2 id="login-title">会话登录</h2>
          </div>
          <span className="section-note">POST /api/v1/auth/session</span>
        </div>
        <form
          onSubmit={submit}
          style={{ display: "flex", flexDirection: "column", gap: "12px", maxWidth: "420px", padding: "16px 26px 22px" }}
        >
          <label style={fieldStyle}>
            邮箱
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
            密码
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
            {busy ? "登录中…" : "登录"}
          </button>
          {error ? <p style={{ color: "#D48B80" }}>{error}</p> : null}
        </form>
      </section>
    </div>
  );
}
