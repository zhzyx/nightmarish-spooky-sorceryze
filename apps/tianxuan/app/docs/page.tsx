import type { Metadata } from "next";
import { cookies } from "next/headers";
import Link from "next/link";
import { Icon } from "@/components/Icon";
import { fetchDocs, type ApiDoc } from "@/lib/api";
import {
  docs,
  getDoc,
  pageTree,
  recentDocIds,
  spaces,
  type DocRecord,
  type PageTreeNode,
} from "@/lib/data";
import { LOCALE_COOKIE, formatMessage, normalizeLocale, translate, type MessageKey } from "@/lib/i18n";

export function generateMetadata(): Metadata {
  const locale = normalizeLocale(cookies().get(LOCALE_COOKIE)?.value);
  return { title: translate(locale, "docs.title") };
}

export const dynamic = "force-dynamic";

function countTree(nodes: PageTreeNode[]): number {
  return nodes.reduce((total, node) => total + 1 + (node.children ? countTree(node.children) : 0), 0);
}

function renderTreePage(page: PageTreeNode) {
  const doc = getDoc(page.id);
  return (
    <div className="tree-node" key={page.id}>
      <Link className="tree-page-link" href={`/docs/${page.id}`}>
        <span className="tree-file-icon">
          <Icon name={page.children ? "folder" : "file"} size={15} />
        </span>
        <span className="tree-page-name">{page.title}</span>
        {doc ? <span className={`kind-dot kind-dot-${doc.kind}`}>{doc.kind}</span> : null}
      </Link>
      {page.children ? (
        <div className="tree-children">
          {page.children.map((child) => {
            const childDoc = getDoc(child.id);
            return (
              <Link className="tree-page-link tree-page-child" href={`/docs/${child.id}`} key={child.id}>
                <span className="tree-file-icon">
                  <Icon name="file" size={14} />
                </span>
                <span className="tree-page-name">{child.title}</span>
                {childDoc ? <span className="tree-page-meta">{childDoc.updated}</span> : null}
              </Link>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

export default async function DocsPage() {
  const locale = normalizeLocale(cookies().get(LOCALE_COOKIE)?.value);
  const t = (key: MessageKey) => translate(locale, key);
  const actor = process.env.TIANXUAN_ACTOR ?? "";
  let liveDocs: ApiDoc[] | null = null;
  if (actor || process.env.TIANXUAN_TOKEN) {
    try {
      liveDocs = await fetchDocs(actor);
    } catch {
      liveDocs = null;
    }
  }

  const recentDocs = recentDocIds
    .map((id) => getDoc(id))
    .filter((doc): doc is DocRecord => Boolean(doc));

  return (
    <div className="page-stack docs-page">
      <header className="page-header">
        <div className="page-title-group">
          <p className="eyebrow">
            <span className="eyebrow-rule" aria-hidden="true" />
            WENQU · DOCUMENT SPACE
          </p>
          <h1>
            {t("docs.title")}
            {locale === "zh" ? <span className="title-period">。</span> : null}
          </h1>
          <p className="page-lede">{t("docs.lede")}</p>
        </div>
        <div className="page-actions">
          <Link className="btn btn-ghost" href="/search?type=docs">
            <Icon name="search" size={16} />
            {t("docs.searchDocs")}
          </Link>
          <Link className="btn btn-primary" href="/docs/ai-native-docs">
            <Icon name="pen" size={16} />
            {t("docs.openEditor")}
          </Link>
        </div>
      </header>

      {liveDocs && liveDocs.length > 0 ? (
        <section className="panel" aria-labelledby="live-docs-title">
          <div className="section-heading">
            <div>
              <p className="section-kicker">LIVE API</p>
              <h2 id="live-docs-title">{t("docs.liveTitle")}</h2>
            </div>
            <span className="section-note">{formatMessage(t("docs.liveNote"), { count: liveDocs.length })}</span>
          </div>
          <div className="reading-list live-list">
            {liveDocs.slice(0, 8).map((doc) => (
              <Link className="reading-item" href={`/docs/${doc.id}`} key={doc.id}>
                <span className="reading-index">{doc.kind.slice(0, 1)}</span>
                <span className="reading-copy">
                  <strong>{doc.title}</strong>
                  <span>v{doc.version} · {doc.kind}</span>
                </span>
                <Icon name="chevronRight" size={14} />
              </Link>
            ))}
          </div>
        </section>
      ) : null}

      <section aria-labelledby="space-list-title">
        <div className="section-heading">
          <div>
            <p className="section-kicker">ALL SPACES</p>
            <h2 id="space-list-title">{t("docs.spacesTitle")}</h2>
          </div>
          <span className="section-note">{formatMessage(t("docs.spacesNote"), { spaces: spaces.length, pages: spaces.reduce((sum, space) => sum + space.pages, 0) })}</span>
        </div>
        <div className="space-grid">
          {spaces.map((space) => {
            const firstDoc = docs.find((doc) => doc.spaceId === space.id);
            return (
              <article className={`space-card tone-${space.tone}`} key={space.id}>
                <div className="space-card-head">
                  <span className="space-monogram" aria-hidden="true">
                    {space.short.slice(0, 1)}
                  </span>
                  <span className="space-page-count">
                    <strong>{space.pages}</strong>
                    {t("docs.pagesSuffix")}
                  </span>
                </div>
                <div className="space-card-copy">
                  <h3>{space.name}</h3>
                  <p>{space.description}</p>
                </div>
                <footer className="space-card-foot">
                  <span className={space.aiReady ? "space-ai-ready" : "space-ai-idle"}>
                    <Icon name={space.aiReady ? "sparkles" : "clock"} size={13} />
                    {space.aiReady ? t("docs.aiReady") : t("docs.manual")}
                  </span>
                  <Link href={firstDoc ? `/docs/${firstDoc.id}` : "/docs"}>
                    {t("docs.enter")}
                    <Icon name="arrowRight" size={13} />
                  </Link>
                </footer>
                <span className="space-card-watermark" aria-hidden="true">
                  {space.short.slice(0, 1)}
                </span>
              </article>
            );
          })}
        </div>
      </section>

      <div className="docs-workspace">
        <section className="panel tree-panel" aria-labelledby="page-tree-title">
          <header className="tree-panel-head">
            <div>
              <p className="section-kicker">PAGE TREE</p>
              <h2 id="page-tree-title">{t("docs.allPages")}</h2>
            </div>
            <span className="tree-count">{formatMessage(t("docs.pageIndex"), { count: docs.length })}</span>
          </header>

          <form action="/search" className="tree-search" role="search">
            <input name="type" type="hidden" value="docs" />
            <Icon name="search" size={15} />
            <input aria-label={t("docs.filterAria")} name="q" placeholder={t("docs.filterPlaceholder")} type="search" />
            <kbd>↵</kbd>
          </form>

          <div className="tree-root">
            {pageTree.map((branch) => (
              <details className="tree-branch" key={branch.label} open>
                <summary>
                  <span className="tree-chevron">
                    <Icon name="chevronRight" size={14} />
                  </span>
                  <span className="tree-folder">
                    <Icon name="folder" size={16} />
                  </span>
                  <span className="tree-branch-name">{branch.label}</span>
                  <span className="tree-branch-count">{countTree(branch.pages)}</span>
                </summary>
                <div className="tree-branch-pages">{branch.pages.map(renderTreePage)}</div>
              </details>
            ))}
          </div>

          <footer className="tree-panel-foot">
            <span>
              <Icon name="sparkles" size={14} />
              {t("docs.aiReadable")}
            </span>
            <Link className="text-link" href="/docs/ai-native-docs">
              {t("docs.editPage")}
              <Icon name="pen" size={13} />
            </Link>
          </footer>
        </section>

        <aside className="docs-side">
          <section className="panel reading-panel" aria-labelledby="reading-title">
            <header className="panel-head">
              <div>
                <p className="section-kicker">CONTINUE READING</p>
                <h2 id="reading-title">{t("docs.continueReading")}</h2>
              </div>
              <Icon className="panel-head-icon" name="history" size={18} />
            </header>
            <div className="reading-list">
              {recentDocs.map((doc, index) => (
                <Link className="reading-item" href={`/docs/${doc.id}`} key={doc.id}>
                  <span className="reading-index">{String(index + 1).padStart(2, "0")}</span>
                  <span className="reading-copy">
                    <strong>{doc.title}</strong>
                    <span>{doc.updated} · {doc.readTime}</span>
                  </span>
                  <Icon name="chevronRight" size={14} />
                </Link>
              ))}
            </div>
          </section>

          <section className="panel health-panel" aria-labelledby="health-title">
            <header className="panel-head">
              <div>
                <p className="section-kicker">KNOWLEDGE HEALTH</p>
                <h2 id="health-title">{t("docs.health")}</h2>
              </div>
            </header>
            <div className="health-body">
              <div className="health-ring" aria-label={t("docs.coverageAria")}>
                <div className="health-ring-inner">
                  <strong>86</strong>
                  <span>%</span>
                  <small>{t("docs.aiReadableShort")}</small>
                </div>
              </div>
              <div className="health-stats">
                <div>
                  <strong>262</strong>
                  <span>{t("docs.anchors")}</span>
                </div>
                <div>
                  <strong>0</strong>
                  <span>{t("docs.brokenRefs")}</span>
                </div>
                <div>
                  <strong>3</strong>
                  <span>{t("docs.unclassified")}</span>
                </div>
              </div>
            </div>
            <p className="health-note">{t("docs.healthNote")}</p>
          </section>

          <section className="aside-quote">
            <span className="aside-quote-mark" aria-hidden="true">
              〝
            </span>
            <p>{t("docs.quote")}</p>
            <span>{t("docs.quoteCaption")}</span>
          </section>
        </aside>
      </div>
    </div>
  );
}
