import type { Metadata } from "next";
import { cookies } from "next/headers";
import Link from "next/link";
import { CreateDoc } from "@/components/CreateDoc";
import { Icon } from "@/components/Icon";
import { currentActor, fetchDocs, type ApiDoc } from "@/lib/server-api";
import { LOCALE_COOKIE, normalizeLocale, translate } from "@/lib/i18n";

export function generateMetadata(): Metadata {
  const locale = normalizeLocale(cookies().get(LOCALE_COOKIE)?.value);
  return { title: translate(locale, "docs.title") };
}

export const dynamic = "force-dynamic";

export default async function DocsPage() {
  const locale = normalizeLocale(cookies().get(LOCALE_COOKIE)?.value);
  const zh = locale === "zh";
  const actor = await currentActor();
  let documents: ApiDoc[] = [];
  let failed = false;
  if (actor) {
    try {
      documents = await fetchDocs(actor);
    } catch {
      failed = true;
    }
  }

  return (
    <div className="page-stack docs-page">
      <header className="page-header">
        <div className="page-title-group">
          <h1>{translate(locale, "docs.title")}</h1>
          <p className="page-lede">{zh ? "创建、编辑和检索你的 Markdown 文档。" : "Create, edit and search your Markdown documents."}</p>
        </div>
        <Link className="btn btn-ghost" href="/search?type=docs">
          <Icon name="search" size={16} />
          {translate(locale, "docs.searchDocs")}
        </Link>
      </header>
      {actor ? <CreateDoc /> : (
        <section className="panel route-state">
          <p>{zh ? "登录后查看和创建文档。" : "Sign in to view and create documents."}</p>
          <Link className="btn btn-primary" href="/login">{zh ? "登录" : "Sign in"}</Link>
        </section>
      )}
      {actor ? (
        <section className="panel" aria-labelledby="documents-title">
          <div className="section-heading">
            <h2 id="documents-title">{zh ? "我的文档" : "My documents"}</h2>
            {!failed ? <span className="section-note">{documents.length}</span> : null}
          </div>
          {failed ? (
            <div style={{ padding: "0 26px 26px" }}>
              <p role="alert">{zh ? "文档加载失败，请重新加载。" : "Documents could not be loaded. Please reload."}</p>
              <a className="btn btn-ghost" href="/docs">{zh ? "重新加载" : "Reload"}</a>
            </div>
          ) : documents.length === 0 ? (
            <p style={{ padding: "0 26px 26px" }}>{zh ? "还没有可查看的文档。" : "No documents to display yet."}</p>
          ) : (
            <div className="reading-list live-list">
              {documents.map(document => (
                <Link className="reading-item" href={`/docs/${encodeURIComponent(document.id)}`} key={document.id}>
                  <Icon name="file" size={18} />
                  <span className="reading-copy">
                    <strong>{document.title}</strong>
                    <span>v{document.version} · {document.kind}</span>
                  </span>
                  <Icon name="chevronRight" size={14} />
                </Link>
              ))}
            </div>
          )}
        </section>
      ) : null}
    </div>
  );
}
