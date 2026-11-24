"use client";
import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useI18n } from "@/lib/i18n-client";
import { clearSession } from "@/lib/auth";


export default function LoginPage() {
    const router = useRouter();
    const { locale } = useI18n();
    const label = (zh: string, en: string) => locale === "zh" ? zh : en;
    const [mode, setMode] = useState("");
    const [register, setRegister] = useState(false);
    const [useKey, setUseKey] = useState(false);
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [workspace, setWorkspace] = useState("");
    const [error, setError] = useState("");
    const [busy, setBusy] = useState(false);
    useEffect(() => {
        fetch("/api/v1/auth/config").then(response => {
            if (!response.ok)
                throw new Error();
            return response.json();
        }).then(data => setMode(data.mode)).catch(() => setError(label("无法读取登录配置，请刷新重试", "Unable to load sign-in settings. Please refresh.")));
    }, []);
    async function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (busy || !mode)
            return;
        setBusy(true);
        setError("");
        try {
            if (mode === "accounts" && !useKey && register) {
                const created = await fetch("/api/v1/auth/register", {
                    method: "POST", headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ tenant_name: workspace, email, password }),
                });
                if (!created.ok)
                    throw new Error(`${label("注册失败", "Registration failed")} (${created.status})`);
                setRegister(false);
            }
            const response = await fetch(`/api/v1/auth/${mode === "accounts" && !useKey ? "session" : "key-login"}`, {
                method: "POST", headers: { "Content-Type": "application/json" },
                body: JSON.stringify(mode === "accounts" && !useKey ? { email, password } : { key: password }),
            });
            if (!response.ok)
                throw new Error(`${label("登录失败", "Sign-in failed")} (${response.status})`);
            clearSession();
            router.push("/docs");
            router.refresh();
        }
        catch (failure) {
            setError(failure instanceof Error ? failure.message : label("网络连接失败", "Network connection failed"));
        }
        finally {
            setBusy(false);
        }
    }
    return (
        <div className="page-stack sign-in-page">
            <header className="page-header">
                <h1>{register ? label("创建文曲工作空间", "Create a Wenqu workspace") : label("登录天璇", "Sign in to Tianxuan")}</h1>
            </header>
            <section className="panel">
                <form onSubmit={submit} className="sign-in-form">
                    {mode === "accounts" && !useKey ? (
                        <>
                            <label>
                                {label("邮箱", "Email")}
                                <input type="email" autoComplete="username" required
                                    value={email} onChange={event => setEmail(event.target.value)} />
                            </label>
                            {register ? (
                                <label>
                                    {label("工作空间名称", "Workspace name")}
                                    <input required value={workspace}
                                        onChange={event => setWorkspace(event.target.value)} />
                                </label>
                            ) : null}
                        </>
                    ) : null}
                    <label>
                        {mode === "accounts" && !useKey ? label("密码", "Password") : label("个人访问密钥", "Personal access key")}
                        <input type="password" required
                            autoComplete={register ? "new-password" : "current-password"}
                            value={password} onChange={event => setPassword(event.target.value)} />
                    </label>
                    <button className="btn btn-primary" disabled={busy || !mode}>
                        {busy ? label("处理中", "Working…") : register ? label("注册并进入文档", "Register and open documents") : label("登录", "Sign in")}
                    </button>
                    {mode === "accounts" && !useKey ? (
                        <button type="button" className="btn btn-ghost" onClick={() => setRegister(!register)}>
                            {register ? label("已有账号，登录", "Already registered? Sign in") : label("注册新账号", "Create an account")}
                        </button>
                    ) : null}
                    {mode === "accounts" ? (
                        <button type="button" className="btn btn-ghost" onClick={() => {
                            setUseKey(!useKey);
                            setRegister(false);
                            setPassword("");
                        }}>
                            {useKey ? label("使用账号登录", "Use an account") : label("使用个人访问密钥", "Use a personal access key")}
                        </button>
                    ) : null}
                    {error ? <p role="alert">{error}</p> : null}
                </form>
            </section>
        </div>
    );
}
