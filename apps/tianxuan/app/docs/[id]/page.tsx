import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { DocEditor } from "@/components/DocEditor";
import { fetchDoc, type ApiDocDetail } from "@/lib/api";
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
    title: doc ? doc.title : "文档",
    description: doc?.excerpt,
  };
}

function LiveDoc({ doc }: { doc: ApiDocDetail }) {
  return (
    <article className="panel" style={{ padding: 28 }}>
      <p className="section-kicker">LIVE API</p>
      <h1>{doc.title}</h1>
      <p className="section-note">
        v{doc.version} · {doc.kind}
      </p>
      <pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit", lineHeight: 1.8 }}>{doc.body_md}</pre>
    </article>
  );
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
      return (
        <div className="page-stack doc-detail-page">
          <LiveDoc doc={liveDoc} />
        </div>
      );
    } catch {
      notFound();
    }
  }
  notFound();
}
