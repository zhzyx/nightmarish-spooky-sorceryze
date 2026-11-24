import Link from "next/link";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { LOCALE_COOKIE, normalizeLocale } from "@/lib/i18n";
import { currentIdentity, fetchMembers } from "@/lib/server-api";
import { AdminKeyForm } from "./AdminKeyForm";

export default async function AdminKeysPage() {
  const identity = await currentIdentity();
  if (!identity) redirect("/login");
  if (!identity.can_issue_admin_keys) redirect("/accounts");

  const zh = normalizeLocale(cookies().get(LOCALE_COOKIE)?.value) === "zh";
  const members = await fetchMembers();
  return <div className="page-stack account-page">
    <header className="page-header">
      <div className="page-title-group">
        <h1>{zh ? "分配管理员密钥" : "Assign administrator keys"}</h1>
        <p className="page-lede">{zh ? "选择本工作空间的管理员。需要新增管理员时，可在账号管理中创建或调整角色。" : "Choose an administrator in this workspace. To add one, create an account or change its role in account management."}</p>
      </div>
      <Link href="/accounts" className="btn btn-ghost">{zh ? "管理账号" : "Manage accounts"}</Link>
    </header>
    <AdminKeyForm recipients={members.filter(member => member.role === "admin")} />
    <Link href="/accounts#issued-keys">{zh ? "查看或撤销已签发密钥" : "View or revoke issued keys"}</Link>
  </div>;
}
