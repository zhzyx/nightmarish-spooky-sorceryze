import Link from "next/link";
import { IssueWork } from "@/components/IssueWork";

export default function IssueWorkPage({ params }: { params: { id: string } }) {
  return (
    <div className="page-stack">
      <Link href="/issues">返回工单看板</Link>
      <IssueWork key={params.id} id={params.id} />
    </div>
  );
}
