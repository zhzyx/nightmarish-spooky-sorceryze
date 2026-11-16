import { currentActor } from "@/lib/server-api";
import type { Metadata } from "next";
import { cookies } from "next/headers";
import { notFound } from "next/navigation";
import { DocComments } from "@/components/DocComments";
import { DocEditor } from "@/components/DocEditor";
import { DocExport } from "@/components/DocExport";
import { DocExternalSource } from "@/components/DocExternalSource";
import { DocSharing } from "@/components/DocSharing";
import { DocVersions } from "@/components/DocVersions";
import { fetchDoc } from "@/lib/server-api";
import { getDoc, getDocContent, type DocRecord } from "@/lib/data";
import { LOCALE_COOKIE, normalizeLocale, translate, type MessageKey } from "@/lib/i18n";

interface DocPageProps {
  params: {
    id: string;
  };
}

export const dynamic = "force-dynamic";

export function generateMetadata({ params }: DocPageProps): Metadata {
  const locale = normalizeLocale(cookies().get(LOCALE_COOKIE)?.value);
  const doc = getDoc(params.id);
  return {
    title: doc ? doc.title : translate(locale, "doc.fallbackTitle"),
    description: doc?.excerpt,
  };
}

export default async function DocPage({ params }: DocPageProps) {
  const locale = normalizeLocale(cookies().get(LOCALE_COOKIE)?.value);
  const t = (key: MessageKey) => translate(locale, key);
  const doc = getDoc(params.id);
  if (doc) {
    return (
      <div className="page-stack doc-detail-page">
        <DocEditor key={doc.id} doc={doc} initialContent={getDocContent(doc)} />
      </div>
    );
  }

  const actor = await currentActor();
  if (actor) {
    try {
      const liveDoc = await fetchDoc(params.id, actor);
      const record: DocRecord = {
        id: liveDoc.id,
        title: liveDoc.title,
        spaceId: "live",
        spaceName: t("doc.liveSpace"),
        kind: t("doc.liveKind") as DocRecord["kind"],
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
          <DocExport docId={liveDoc.id} title={liveDoc.title} />
          <DocExternalSource docId={liveDoc.id} />
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
