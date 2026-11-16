"use client";
import { useEffect, useState, type FormEvent } from "react";
import { useIdentity } from "@/components/IdentityProvider";
interface Member { id: string; email: string; name: string; role: string }
interface Key { id: string; user_id: string; name: string; created_at: string; expires_at: string | null; revoked_at: string | null }

export default function AccountsPage() {
  const identity = useIdentity();
  const [members,setMembers] = useState<Member[]>([]);
  const [keys,setKeys] = useState<Key[]>([]);
  const [error,setError] = useState("");
  const [issued,setIssued] = useState("");
  const [busy,setBusy] = useState(false);
  async function request(path: string, method="GET", body?: object) {
    const result = await fetch(`/api/v1/${path}`, {method, headers:{"Content-Type":"application/json"}, body:body ? JSON.stringify(body) : undefined});
    if (!result.ok) throw new Error(`操作失败（${result.status}），请确认权限或重新登录。`);
    return result.json();
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
  return <div className="page-stack"><h1>账号与访问 Key</h1>
    <p>{identity ? `${identity.name || identity.email} · ${identity.role}` : "请先登录。"}</p>
    <button className="button" onClick={async()=>{await request("auth/key-logout","POST"); window.location.assign("/login");}}>退出登录</button>
    {error && <p role="alert">{error}</p>}
    {identity?.role === "admin" && <>
      {issued && <section className="panel" style={{padding:20}}><h2>新 Key（仅此次显示）</h2><p>请通过安全渠道交给对应用户；关闭后无法再次查看。</p><input aria-label="新 Key" readOnly value={issued} style={{width:"100%"}}/><button onClick={()=>setIssued("")}>已保存，隐藏</button></section>}
      <section className="panel" style={{padding:20}}><h2>创建受限账号</h2><form onSubmit={createUser} style={{display:"flex",gap:12,flexWrap:"wrap"}}>
        <input name="email" type="email" placeholder="邮箱" aria-label="邮箱" required/><input name="name" placeholder="姓名" aria-label="姓名"/>
        <select name="role" aria-label="权限"><option value="viewer">只读</option><option value="editor">编辑</option><option value="admin">管理员</option></select>
        <button disabled={busy}>创建并签发 Key</button>
      </form></section>
      <section className="panel" style={{padding:20}}><h2>现有账号</h2><table><thead><tr><th>账号</th><th>权限</th><th>访问</th></tr></thead><tbody>{members.map(member=><tr key={member.id}><td>{member.name || member.email}</td><td><select aria-label={`${member.email}权限`} value={member.role} disabled={busy || member.id===identity.id} onChange={e=>{const role=e.target.value;void act(async()=>{await request(`users/${member.id}/role`,"PATCH",{role});});}}>{["viewer","editor","admin"].map(role=><option key={role}>{role}</option>)}</select></td><td><button disabled={busy} onClick={()=>void act(async()=>{const key=await request("auth/keys","POST",{user_id:member.id,name:"新增访问",days:90});setIssued(key.key);})}>签发 Key</button></td></tr>)}</tbody></table></section>
      <section className="panel" style={{padding:20}}><h2>已签发 Key</h2><table><thead><tr><th>账号</th><th>名称</th><th>有效期</th><th>状态</th></tr></thead><tbody>{keys.map(key=><tr key={key.id}><td>{members.find(m=>m.id===key.user_id)?.email ?? key.user_id}</td><td>{key.name}</td><td>{key.expires_at ?? "已失效"}</td><td>{key.revoked_at ? "已撤销" : <button disabled={busy} onClick={()=>void act(async()=>{await request(`auth/keys/${key.id}`,"DELETE");})}>撤销</button>}</td></tr>)}</tbody></table></section>
    </>}
  </div>;
}
