import Link from "next/link";
import { IssueWork } from "@/components/IssueWork";

export default function IssueWorkPage({ params }: { params: { id: string } }) {
  return (
    <main className="page-stack">
      <Link href="/issues">返回工单看板</Link>
      <IssueWork key={params.id} id={params.id} />
    </main>
  );
}
