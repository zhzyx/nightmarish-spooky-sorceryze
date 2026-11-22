"use client";

import { useState, type FormEvent } from "react";
import { useI18n } from "@/lib/i18n-client";

interface Recipient { id: string; name: string; email: string }

export function AdminKeyForm({ recipients }: { recipients: Recipient[] }) {
  const { locale } = useI18n();
  const label = (zh: string, en: string) => locale === "zh" ? zh : en;
  const [issued, setIssued] = useState<{ email: string; key: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function issue(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || issued) return;
    const form = event.currentTarget;
    const fields = new FormData(form);
    const recipient = recipients.find(member => member.id === fields.get("recipient"));
    if (!recipient) return;

    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/v1/auth/keys/admin", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: recipient.id, name: fields.get("name"), days: Number(fields.get("days")) }),
      });
      if (!response.ok) {
        setError(response.status === 409
          ? label("收件人的角色已变更。请刷新后重新选择。", "The recipient’s role changed. Refresh and choose again.")
          : label(`签发失败（${response.status}）。请检查账号权限。`, `Could not issue the key (${response.status}). Check account access.`));
        return;
      }
      const { key } = await response.json();
      setIssued({ email: recipient.email, key });
      form.reset();
    } catch {
      setError(label("未收到签发结果。请先在已签发密钥中核对记录。", "No result received. Check issued keys before retrying."));
    } finally {
      setBusy(false);
    }
  }

  if (issued) return <section className="panel account-card">
    <h2>{label("交付密钥", "Deliver key")}</h2>
    <p>{label(`请通过私密渠道将密钥交给 ${issued.email}。明文仅显示一次。`, `Share this key privately with ${issued.email}. It is shown only once.`)}</p>
    <input aria-label={label("新管理员密钥", "New administrator key")} readOnly value={issued.key} onFocus={event => event.target.select()} />
    <button className="btn btn-ghost" onClick={() => setIssued(null)}>{label("已保存，隐藏密钥", "Saved, hide key")}</button>
  </section>;

  return <section className="panel account-card">
    <form className="account-fields" onSubmit={issue}>
      <label>{label("管理员账号", "Administrator account")}
        <select name="recipient" required defaultValue="">
          <option value="" disabled>{label("选择收件人", "Choose recipient")}</option>
          {recipients.map(member => <option key={member.id} value={member.id}>{member.name} · {member.email}</option>)}
        </select>
      </label>
      <label>{label("密钥用途", "Key purpose")}<input name="name" required maxLength={100} pattern=".*\S.*" /></label>
      <label>{label("有效天数", "Valid for (days)")}<input name="days" type="number" required min={1} max={365} defaultValue={90} /></label>
      <button className="btn btn-primary" disabled={busy}>{busy ? label("签发中…", "Issuing…") : label("签发管理员密钥", "Issue administrator key")}</button>
    </form>
    {error && <p role="alert">{error}</p>}
  </section>;
}
