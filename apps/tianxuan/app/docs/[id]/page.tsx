import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { DocComments } from "@/components/DocComments";
import { DocEditor } from "@/components/DocEditor";
import { DocSharing } from "@/components/DocSharing";
import { DocVersions } from "@/components/DocVersions";
import { fetchDoc } from "@/lib/api";
import { getDoc, getDocContent, type DocRecord } from "@/lib/data";

interface DocPageProps {
  params: {
    id: string;
  };
}

export const dynamic = "force-dynamic";

export function generateMetadata({ params }: DocPageProps): Metadata {
  const doc = getDoc(params.id);
  return {
    title: doc ? doc.title : "文档",
    description: doc?.excerpt,
  };
}

export default async function DocPage({ params }: DocPageProps) {
  const doc = getDoc(params.id);
  if (doc) {
    return (
      <div className="page-stack doc-detail-page">
        <DocEditor key={doc.id} doc={doc} initialContent={getDocContent(doc)} />
      </div>
    );
  }

  const actor = process.env.TIANXUAN_ACTOR ?? "";
  if (actor) {
    try {
      const liveDoc = await fetchDoc(params.id, actor);
      const record: DocRecord = {
        id: liveDoc.id,
        title: liveDoc.title,
        spaceId: "live",
        spaceName: "实时",
        kind: "记录",
        excerpt: "",
        updated: "",
        updatedBy: "",
        readTime: "",
        tags: [],
        words: liveDoc.body_md.length,
        version: liveDoc.version,
      };
      return (
        <div className="page-stack doc-detail-page">
          <DocEditor
            key={liveDoc.id}
            doc={record}
            initialContent={liveDoc.body_md}
            version={liveDoc.version}
          />
          <DocSharing docId={liveDoc.id} initialVisibility={liveDoc.visibility} />
          <DocComments docId={liveDoc.id} />
          <DocVersions docId={liveDoc.id} />
        </div>
      );
    } catch {
      notFound();
    }
  }
  notFound();
}
