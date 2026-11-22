"use client";
import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useI18n } from "@/lib/i18n-client";
import { useIdentity } from "@/components/IdentityProvider";
interface Member { id: string; email: string; name: string; role: string }
interface Key { id: string; user_id: string; name: string; created_at: string; expires_at: string | null; revoked_at: string | null }

export default function AccountsPage() {
  const identity = useIdentity();
  const { locale } = useI18n();
  const label = (zh: string, en: string) => locale === "zh" ? zh : en;
  const roles = [
    ["viewer", label("只读", "Viewer")],
    ["editor", label("编辑", "Editor")],
    ["admin", label("管理员", "Administrator")],
  ];
  const [members,setMembers] = useState<Member[]>([]);
  const [keys,setKeys] = useState<Key[]>([]);
  const [error,setError] = useState("");
  const [issued,setIssued] = useState("");
  const [busy,setBusy] = useState(false);
  async function request(path: string, method="GET", body?: object) {
    const result = await fetch(`/api/v1/${path}`, {method, headers:{"Content-Type":"application/json"}, body:body ? JSON.stringify(body) : undefined});
    if (!result.ok) throw new Error(`${label("操作失败，请检查权限或重新登录。", "Request failed. Check access or sign in again.")} (${result.status})`);
    return result.status === 204 ? null : result.json();
  }
  async function reload() {
    const [users,access] = await Promise.all([request("users"),request("auth/keys")]);
    setMembers(users.users); setKeys(access.keys);
  }
  useEffect(()=>{ if(identity?.role === "admin") reload().catch(e=>setError(e.message)); },[identity?.role]);
  async function act(operation:()=>Promise<void>) {
    setBusy(true); setError("");
    try { await operation(); await reload(); } catch(e) { setError(e instanceof Error ? e.message : "操作失败"); }
    finally { setBusy(false); }
  }
  function createUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form=event.currentTarget; const data=new FormData(form);
    void act(async()=>{
      const user = await request("users","POST",{email:data.get("email"),name:data.get("name"),role:data.get("role"),password:crypto.randomUUID()+crypto.randomUUID()});
      const key = await request("auth/keys","POST",{user_id:user.user_id,name:"初始访问",days:90});
      setIssued(key.key); form.reset();
    });
  }
  async function signOut() {
    setBusy(true);
    try {
      await request("auth/key-logout", "POST");
      window.location.assign("/login");
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : label("退出失败", "Sign-out failed"));
      setBusy(false);
    }
  }

  return <div className="page-stack account-page">
    <header className="page-header">
      <div className="page-title-group">
        <h1>{label("账号与访问密钥", "Accounts and access keys")}</h1>
        {identity && <p className="page-lede">{identity.name || identity.email} · {roles.find(([role]) => role === identity.role)?.[1] ?? identity.role}</p>}
      </div>
      <div className="page-actions">
        {identity?.can_issue_admin_keys && <Link className="btn btn-primary" href="/accounts/admin-keys">{label("分配管理员密钥", "Assign administrator keys")}</Link>}
        {identity && <button className="btn btn-ghost" disabled={busy} onClick={signOut}>{label("退出登录", "Sign out")}</button>}
      </div>
    </header>
    {!identity && <section className="panel route-state">
      <p>{label("登录后可查看账号。", "Sign in to view your account.")}</p>
      <Link href="/login" className="btn btn-primary">{label("登录", "Sign in")}</Link>
    </section>}
    {error && <p role="alert">{error}</p>}
    {identity?.role === "admin" && <>
      {issued && <section className="panel account-card">
        <h2>{label("新密钥", "New access key")}</h2>
        <p>{label("密钥仅显示一次。请保存并通过安全渠道交给对应用户。", "Save the key and share it securely with its owner. It is only shown once.")}</p>
        <input aria-label={label("新密钥", "New access key")} readOnly value={issued} />
        <button className="btn btn-ghost" onClick={() => setIssued("")}>{label("已保存，隐藏", "Saved, hide key")}</button>
      </section>}
      <section className="panel account-card">
        <h2>{label("创建受限账号", "Create an account")}</h2>
        <form className="account-fields" onSubmit={createUser}>
          <label>{label("邮箱", "Email")}<input name="email" type="email" required /></label>
          <label>{label("姓名", "Name")}<input name="name" /></label>
          <label>{label("权限", "Role")}<select name="role">{roles.map(([role, name]) => <option key={role} value={role}>{name}</option>)}</select></label>
          <button className="btn btn-primary" disabled={busy}>{label("创建并签发密钥", "Create and issue key")}</button>
        </form>
      </section>
      <section className="panel account-card">
        <h2>{label("现有账号", "Accounts")}</h2>
        <div className="account-table"><table><thead><tr>
          <th>{label("账号", "Account")}</th><th>{label("权限", "Role")}</th><th>{label("访问", "Access")}</th>
        </tr></thead><tbody>{members.map(member => <tr key={member.id}>
          <td>{member.name || member.email}</td>
          <td><select aria-label={member.email + " " + label("权限", "role")} value={member.role} disabled={busy || member.id === identity.id}
            onChange={e => {
              const role = e.target.value;
              void act(async () => { await request(`users/${member.id}/role`, "PATCH", { role }); });
            }}>{roles.map(([role, name]) => <option key={role} value={role}>{name}</option>)}</select></td>
          <td><button className="btn btn-ghost" disabled={busy} onClick={() => void act(async () => {
            const key = await request("auth/keys", "POST", { user_id: member.id, name: "新增访问", days: 90 });
            setIssued(key.key);
          })}>{label("签发密钥", "Issue key")}</button></td>
        </tr>)}</tbody></table></div>
      </section>
      <section className="panel account-card">
        <h2 id="issued-keys">{label("已签发密钥", "Issued keys")}</h2>
        <div className="account-table"><table><thead><tr>
          <th>{label("账号", "Account")}</th><th>{label("名称", "Name")}</th>
          <th>{label("有效期", "Expires")}</th><th>{label("状态", "Status")}</th>
        </tr></thead><tbody>{keys.map(key => <tr key={key.id}>
          <td>{members.find(m => m.id === key.user_id)?.email ?? key.user_id}</td>
          <td>{key.name}</td><td>{key.expires_at ?? "—"}</td>
          <td>{key.revoked_at ? label("已撤销", "Revoked") :
            <button className="btn btn-danger" disabled={busy} onClick={() => void act(async () => {
              await request(`auth/keys/${key.id}`, "DELETE");
            })}>{label("撤销", "Revoke")}</button>}</td>
        </tr>)}</tbody></table></div>
      </section>
    </>}
  </div>;
}
