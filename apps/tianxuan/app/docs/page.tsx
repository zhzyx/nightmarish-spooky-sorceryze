import type { Metadata } from "next";
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

export const metadata: Metadata = {
  title: "文档",
};

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
  const actor = process.env.TIANXUAN_ACTOR ?? "";
  let liveDocs: ApiDoc[] | null = null;
  if (actor) {
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
            文档<span className="title-period">。</span>
          </h1>
          <p className="page-lede">
            一份 Markdown，成为团队、模型与工单共同阅读的事实。空间负责归类，页面负责留下可回读的判断。
          </p>
        </div>
        <div className="page-actions">
          <Link className="btn btn-ghost" href="/search?type=docs">
            <Icon name="search" size={16} />
            搜索文档
          </Link>
          <Link className="btn btn-primary" href="/docs/ai-native-docs">
            <Icon name="pen" size={16} />
            打开编辑器
          </Link>
        </div>
      </header>

      {liveDocs && liveDocs.length > 0 ? (
        <section className="panel" aria-labelledby="live-docs-title">
          <div className="section-heading">
            <div>
              <p className="section-kicker">LIVE API</p>
              <h2 id="live-docs-title">实时文档</h2>
            </div>
            <span className="section-note">{liveDocs.length} 篇来自后端</span>
          </div>
          <div className="reading-list">
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
            <h2 id="space-list-title">文档空间</h2>
          </div>
          <span className="section-note">{spaces.length} 个空间 · {spaces.reduce((sum, space) => sum + space.pages, 0)} 个页面</span>
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
                    页
                  </span>
                </div>
                <div className="space-card-copy">
                  <h3>{space.name}</h3>
                  <p>{space.description}</p>
                </div>
                <footer className="space-card-foot">
                  <span className={space.aiReady ? "space-ai-ready" : "space-ai-idle"}>
                    <Icon name={space.aiReady ? "sparkles" : "clock"} size={13} />
                    {space.aiReady ? "AI 索引已就绪" : "手动整理"}
                  </span>
                  <Link href={firstDoc ? `/docs/${firstDoc.id}` : "/docs"}>
                    进入空间
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
              <h2 id="page-tree-title">全部页面</h2>
            </div>
            <span className="tree-count">{docs.length} 页索引</span>
          </header>

          <form action="/search" className="tree-search" role="search">
            <input name="type" type="hidden" value="docs" />
            <Icon name="search" size={15} />
            <input aria-label="筛选页面" name="q" placeholder="筛选页面与标题" type="search" />
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
              所有页面均可被 AI 读取
            </span>
            <Link className="text-link" href="/docs/ai-native-docs">
              编辑页面
              <Icon name="pen" size={13} />
            </Link>
          </footer>
        </section>

        <aside className="docs-side">
          <section className="panel reading-panel" aria-labelledby="reading-title">
            <header className="panel-head">
              <div>
                <p className="section-kicker">CONTINUE READING</p>
                <h2 id="reading-title">继续阅读</h2>
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
                <h2 id="health-title">文档健康</h2>
              </div>
            </header>
            <div className="health-body">
              <div className="health-ring" aria-label="AI 可读覆盖率 86%">
                <div className="health-ring-inner">
                  <strong>86</strong>
                  <span>%</span>
                  <small>AI 可读</small>
                </div>
              </div>
              <div className="health-stats">
                <div>
                  <strong>262</strong>
                  <span>稳定锚点</span>
                </div>
                <div>
                  <strong>0</strong>
                  <span>失效引用</span>
                </div>
                <div>
                  <strong>3</strong>
                  <span>待归类页面</span>
                </div>
              </div>
            </div>
            <p className="health-note">
              标题与摘要覆盖良好。建议为 3 个未归类页面补充一句摘要，AI 才能准确复用。
            </p>
          </section>

          <section className="aside-quote">
            <span className="aside-quote-mark" aria-hidden="true">
              〝
            </span>
            <p>文档不是写给人看的成品，而是人与 AI 共同维护的活体结构。</p>
            <span>文曲手记 · 011</span>
          </section>
        </aside>
      </div>
    </div>
  );
}
