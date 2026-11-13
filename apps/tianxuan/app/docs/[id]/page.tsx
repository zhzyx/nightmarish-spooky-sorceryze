import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { DocEditor } from "@/components/DocEditor";
import { docs, getDoc, getDocContent } from "@/lib/data";

interface DocPageProps {
  params: {
    id: string;
  };
}

export function generateStaticParams() {
  return docs.map((doc) => ({ id: doc.id }));
}

export function generateMetadata({ params }: DocPageProps): Metadata {
  const doc = getDoc(params.id);
  return {
    title: doc ? doc.title : "页面未找到",
    description: doc?.excerpt,
  };
}

export default function DocPage({ params }: DocPageProps) {
  const doc = getDoc(params.id);
  if (!doc) {
    notFound();
  }

  return (
    <div className="page-stack doc-detail-page">
      <DocEditor key={doc.id} doc={doc} initialContent={getDocContent(doc)} />
    </div>
  );
}
