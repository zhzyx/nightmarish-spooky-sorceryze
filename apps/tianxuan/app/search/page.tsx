import type { Metadata } from "next";
import Link from "next/link";
import { Fragment, type ReactNode } from "react";
import { EmptyState } from "@/components/EmptyState";
import { Icon, type IconName } from "@/components/Icon";
import {
  docs,
  issues,
  recentDocIds,
  requirements,
  repos,
  type DocRecord,
  type Tone,
} from "@/lib/data";
import { fetchSearch, type ApiSearchResult } from "@/lib/search-api";

export const metadata: Metadata = {
  title: "全局搜索",
};

// 实时检索依赖每次请求的 q 与 TIANXUAN_ACTOR，禁用静态化。
export const dynamic = "force-dynamic";

type SearchType = "all" | "docs" | "issues" | "repos" | "requirements";

interface SearchResult {
  id: string;
  kind: "文档" | "工单" | "仓库" | "需求";
  title: string;
  excerpt: string;
  meta: string;
  href: string;
  icon: IconName;
  tone: Tone;
  tags: string[];
}

const suggestions = [
  { label: "AI 原生文档", query: "AI" },
  { label: "验收证据", query: "验收" },
  { label: "合并队列", query: "合并" },
  { label: "毛玻璃", query: "毛玻璃" },
  { label: "设计令牌", query: "设计" },
];

const searchScopes: {
  id: SearchType;
  label: string;
  icon: IconName;
}[] = [
  { id: "all", label: "全部", icon: "search" },
  { id: "docs", label: "文档", icon: "docs" },
  { id: "issues", label: "工单", icon: "issues" },
  { id: "repos", label: "仓库", icon: "repos" },
  { id: "requirements", label: "需求", icon: "requirements" },
];

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function highlight(text: string, query: string): ReactNode[] | string {
  if (!query) {
    return text;
  }
  const parts = text.split(new RegExp(`(${escapeRegExp(query)})`, "gi"));
  return parts.map((part, index) =>
    part.toLowerCase() === query.toLowerCase() ? (
      <mark key={`${part}-${index}`}>{part}</mark>
    ) : (
      <Fragment key={`${part}-${index}`}>{part}</Fragment>
    ),
  );
}

function buildSearchHref(query: string, type: SearchType): string {
  const params = new URLSearchParams();
  if (query) {
    params.set("q", query);
  }
  if (type !== "all") {
    params.set("type", type);
  }
  const suffix = params.toString();
  return suffix ? `/search?${suffix}` : "/search";
}

function LiveSearchResults({ query, results }: { query: string; results: ApiSearchResult[] }) {
  return (
    <section aria-labelledby="live-search-title" className="live-search-section">
      <div className="search-summary-row live-search-head">
        <p>
          <strong id="live-search-title">实时结果</strong>
          <span>文曲检索 API · {results.length} 条</span>
        </p>
        <span className="search-index-tag">
          <span className="live-dot" aria-hidden="true" />
          实时索引
        </span>
      </div>

      {results.length > 0 ? (
        <div className="search-results-list">
          {results.map((result) => (
            <Link
              className="search-result"
              href={`/docs/${encodeURIComponent(result.id)}`}
              key={result.id}
            >
              <span className="search-result-icon tone-jade">
                <Icon name="file" size={17} />
              </span>
              <span className="search-result-body">
                <span className="search-result-head">
                  <span className="search-result-kind">{result.kind ?? "文档"}</span>
                  <strong>{highlight(result.title ?? result.id, query)}</strong>
                </span>
                {result.snippet ? (
                  <span className="search-result-excerpt">{highlight(result.snippet, query)}</span>
                ) : null}
              </span>
              <Icon className="search-result-arrow" name="arrowRight" size={15} />
            </Link>
          ))}
        </div>
      ) : (
        <p className="live-search-empty">实时索引没有匹配的文档。</p>
      )}
    </section>
  );
}

export default async function SearchPage({
  searchParams,
}: {
  searchParams: { q?: string; type?: string };
}) {
  const query = (searchParams.q ?? "").trim();
  const typeParam = searchParams.type;
  const activeType: SearchType =
    typeParam === "docs" ||
    typeParam === "issues" ||
    typeParam === "repos" ||
    typeParam === "requirements"
      ? typeParam
      : "all";
  const needle = query.toLowerCase();

  const actor = process.env.TIANXUAN_ACTOR?.trim() ?? "";
  let liveResults: ApiSearchResult[] | null = null;
  if (query && actor) {
    try {
      liveResults = await fetchSearch(actor, query);
    } catch {
      // 实时检索不可用时静默回退到本地示例结果。
      liveResults = null;
    }
  }

  const docResults: SearchResult[] = docs
    .filter((doc) =>
      `${doc.title} ${doc.excerpt} ${doc.spaceName} ${doc.tags.join(" ")} ${doc.content ?? ""}`
        .toLowerCase()
        .includes(needle),
    )
    .map((doc) => ({
      id: `doc-${doc.id}`,
      kind: "文档",
      title: doc.title,
      excerpt: doc.excerpt,
      meta: `${doc.spaceName} · ${doc.kind} · ${doc.updated}`,
      href: `/docs/${doc.id}`,
      icon: "file",
      tone: "jade",
      tags: doc.tags,
    }));

  const issueResults: SearchResult[] = issues
    .filter((issue) =>
      `${issue.key} ${issue.title} ${issue.project} ${issue.tags.join(" ")} ${issue.detail}`
        .toLowerCase()
        .includes(needle),
    )
    .map((issue) => ({
      id: `issue-${issue.id}`,
      kind: "工单",
      title: `${issue.key} ${issue.title}`,
      excerpt: issue.detail,
      meta: `${issue.project} · ${issue.status === "done" ? "已完成" : "未闭环"} · ${issue.updated}`,
      href: "/issues",
      icon: "issues",
      tone: "cinnabar",
      tags: issue.tags,
    }));

  const repoResults: SearchResult[] = repos
    .filter((repo) =>
      `${repo.name} ${repo.description} ${repo.language} ${repo.branch}`
        .toLowerCase()
        .includes(needle),
    )
    .map((repo) => ({
      id: `repo-${repo.id}`,
      kind: "仓库",
      title: repo.name,
      excerpt: repo.description,
      meta: `${repo.language} · ${repo.branch} · ${repo.visibility}`,
      href: "/repos",
      icon: "repos",
      tone: "gold",
      tags: [repo.language, repo.status],
    }));

  const requirementResults: SearchResult[] = requirements
    .filter((requirement) =>
      `${requirement.id} ${requirement.title} ${requirement.summary} ${requirement.status}`
        .toLowerCase()
        .includes(needle),
    )
    .map((requirement) => ({
      id: `req-${requirement.id}`,
      kind: "需求",
      title: requirement.title,
      excerpt: requirement.summary,
      meta: `${requirement.id} · ${requirement.status} · 负责人 ${requirement.owner}`,
      href: `/docs/${requirement.docId}`,
      icon: "requirements",
      tone: "mist",
      tags: [requirement.status, `${requirement.progress}%`],
    }));

  const allResults = query
    ? [...docResults, ...issueResults, ...repoResults, ...requirementResults]
    : [];

  const counts: Record<SearchType, number> = {
    all: allResults.length,
    docs: docResults.length,
    issues: issueResults.length,
    repos: repoResults.length,
    requirements: requirementResults.length,
  };

  const visibleResults =
    activeType === "all"
      ? allResults
      : activeType === "docs"
        ? docResults
        : activeType === "issues"
          ? issueResults
          : activeType === "repos"
            ? repoResults
            : requirementResults;

  const recentDocs = recentDocIds
    .map((id) => docs.find((doc) => doc.id === id))
    .filter((doc): doc is DocRecord => Boolean(doc));

  return (
    <div className="page-stack search-page">
      <header className="search-hero">
        <p className="eyebrow">
          <span className="eyebrow-rule" aria-hidden="true" />
          DITING · GLOBAL SEARCH
        </p>
        <h1>
          全局搜索<span className="title-period">。</span>
        </h1>
        <p className="search-lede">
          从一句话出发，找到文档、工单、仓库与需求之间的同一条线索。搜索结果只来自本地工作区索引。
        </p>

        <form action="/search" className="global-search-form" role="search">
          <span className="global-search-icon">
            <Icon name="search" size={20} />
          </span>
          <label className="sr-only" htmlFor="global-search-input">
            搜索工作区
          </label>
          <input
            autoComplete="off"
            defaultValue={query}
            id="global-search-input"
            name="q"
            placeholder="搜索页面、编号、仓库或一句话…"
            type="search"
          />
          <kbd>↵</kbd>
          <button className="btn btn-primary" type="submit">
            搜索
          </button>
        </form>

        <div className="search-quick-row">
          <span>试试看</span>
          {suggestions.map((suggestion) => (
            <Link href={buildSearchHref(suggestion.query, "all")} key={suggestion.label}>
              {suggestion.label}
            </Link>
          ))}
        </div>
      </header>

      {query ? (
        <>
          <div className="search-summary-row">
            <p>
              关于 <strong>“{query}”</strong> 的结果
              <span>在本地索引中找到 {allResults.length} 条</span>
            </p>
            <span className="search-index-tag">
              <span className="live-dot" aria-hidden="true" />
              本地演示索引
            </span>
          </div>

          <div aria-label="搜索范围" className="search-scope-tabs" role="navigation">
            {searchScopes.map((scope) => (
              <Link
                aria-current={activeType === scope.id ? "page" : undefined}
                className={activeType === scope.id ? "is-active" : ""}
                href={buildSearchHref(query, scope.id)}
                key={scope.id}
              >
                <Icon name={scope.icon} size={14} />
                {scope.label}
                <span>{counts[scope.id]}</span>
              </Link>
            ))}
          </div>

          <div className="search-results-layout">
            <div className="search-main">
              {liveResults !== null ? (
                <LiveSearchResults query={query} results={liveResults} />
              ) : null}

              {visibleResults.length > 0 ? (
                <>
                  <section className="ai-answer" aria-labelledby="ai-answer-title">
                    <div className="ai-answer-head">
                      <span className="ai-answer-orb">
                        <Icon name="sparkles" size={15} />
                      </span>
                      <span>
                        <strong id="ai-answer-title">AI 摘要</strong>
                        <small>演示生成 · 不调用模型</small>
                      </span>
                      <span className="ai-answer-badge">LOCAL</span>
                    </div>
                    <p>
                      与“{query}”最相关的线索集中在
                      <strong> {visibleResults[0]?.kind}「{visibleResults[0]?.title}」</strong>
                      。当前共有 {visibleResults.length} 条可回读结果，建议先打开最接近原始判断的文档，再检查关联工单的验收条件。
                    </p>
                    <div className="ai-answer-sources">
                      {visibleResults.slice(0, 3).map((result) => (
                        <Link href={result.href} key={result.id}>
                          <span>{result.kind}</span>
                          {result.title}
                        </Link>
                      ))}
                    </div>
                  </section>

                  <div className="search-results-list">
                    {visibleResults.map((result) => (
                      <Link className="search-result" href={result.href} key={result.id}>
                        <span className={`search-result-icon tone-${result.tone}`}>
                          <Icon name={result.icon} size={17} />
                        </span>
                        <span className="search-result-body">
                          <span className="search-result-head">
                            <span className="search-result-kind">{result.kind}</span>
                            <strong>{highlight(result.title, query)}</strong>
                          </span>
                          <span className="search-result-excerpt">{highlight(result.excerpt, query)}</span>
                          <span className="search-result-meta">{result.meta}</span>
                          <span className="search-result-tags">
                            {result.tags.slice(0, 3).map((tag) => (
                              <span className="micro-tag" key={tag}>
                                {tag}
                              </span>
                            ))}
                          </span>
                        </span>
                        <Icon className="search-result-arrow" name="arrowRight" size={15} />
                      </Link>
                    ))}
                  </div>
                </>
              ) : liveResults === null || liveResults.length === 0 ? (
                <EmptyState
                  actionHref="/search"
                  actionLabel="清除搜索"
                  description="换一个更短的关键词，或先在文档空间中建立一条新的可检索记录。"
                  eyebrow="DITING · NO MATCH"
                  title="没有找到对应的线索"
                />
              ) : null}
            </div>

            <aside className="search-aside">
              <section className="panel search-index-panel">
                <header className="panel-head">
                  <div>
                    <p className="section-kicker">INDEX STATUS</p>
                    <h2>索引范围</h2>
                  </div>
                  <Icon className="panel-head-icon" name="layers" size={18} />
                </header>
                <div className="index-rows">
                  <div>
                    <span>文档页面</span>
                    <strong>{docs.length}</strong>
                  </div>
                  <div>
                    <span>工单</span>
                    <strong>{issues.length}</strong>
                  </div>
                  <div>
                    <span>仓库</span>
                    <strong>{repos.length}</strong>
                  </div>
                  <div>
                    <span>需求</span>
                    <strong>{requirements.length}</strong>
                  </div>
                </div>
                <p className="index-note">
                  本地演示索引，不包含真实语义向量。真实环境中由谛听记录来源与读取回执。
                </p>
              </section>

              <section className="panel search-recent-panel">
                <header className="panel-head">
                  <div>
                    <p className="section-kicker">RECENTLY READ</p>
                    <h2>最近阅读</h2>
                  </div>
                </header>
                <div className="search-recent-list">
                  {recentDocs.slice(0, 3).map((doc) => (
                    <Link href={`/docs/${doc.id}`} key={doc.id}>
                      <Icon name="file" size={14} />
                      <span>{doc.title}</span>
                      <Icon name="chevronRight" size={13} />
                    </Link>
                  ))}
                </div>
              </section>

              <section className="search-tip">
                <span className="aside-quote-mark" aria-hidden="true">
                  〝
                </span>
                <p>搜索不是找到更多，而是更快看见值得相信的那一条。</p>
                <span>谛听手记 · 009</span>
              </section>
            </aside>
          </div>
        </>
      ) : (
        <div className="search-landing">
          <section className="panel search-suggest-panel" aria-labelledby="search-suggest-title">
            <header className="panel-head">
              <div>
                <p className="section-kicker">START HERE</p>
                <h2 id="search-suggest-title">从一个词开始</h2>
              </div>
              <Icon className="panel-head-icon" name="search" size={18} />
            </header>
            <div className="suggest-list">
              {suggestions.map((suggestion, index) => (
                <Link href={buildSearchHref(suggestion.query, "all")} key={suggestion.label}>
                  <span className="suggest-index">{String(index + 1).padStart(2, "0")}</span>
                  <span>{suggestion.label}</span>
                  <Icon name="arrowRight" size={14} />
                </Link>
              ))}
            </div>
          </section>

          <section className="panel search-recent-large" aria-labelledby="recent-search-title">
            <header className="panel-head">
              <div>
                <p className="section-kicker">CURATED FOR YOU</p>
                <h2 id="recent-search-title">最近阅读</h2>
              </div>
              <Link className="text-link" href="/docs">
                全部文档
                <Icon name="arrowRight" size={14} />
              </Link>
            </header>
            <div className="search-doc-grid">
              {recentDocs.map((doc) => (
                <Link className="search-doc-card" href={`/docs/${doc.id}`} key={doc.id}>
                  <span className="search-doc-top">
                    <span className={`doc-glyph tone-${doc.spaceId === "sinan" ? "cinnabar" : doc.spaceId === "duobao" ? "gold" : "jade"}`}>
                      <Icon name="file" size={16} />
                    </span>
                    <span className={`kind-tag kind-${doc.kind}`}>{doc.kind}</span>
                  </span>
                  <strong>{doc.title}</strong>
                  <span>{doc.excerpt}</span>
                  <small>
                    {doc.updated} · {doc.readTime}
                  </small>
                </Link>
              ))}
            </div>
          </section>

          <section className="panel search-scope-panel" aria-labelledby="scope-title">
            <header className="panel-head">
              <div>
                <p className="section-kicker">SOURCES</p>
                <h2 id="scope-title">搜索范围</h2>
              </div>
            </header>
            <div className="search-source-list">
              <div>
                <span className="source-icon tone-jade">
                  <Icon name="docs" size={15} />
                </span>
                <span>
                  <strong>{docs.length} 个页面</strong>
                  <small>文曲 · Markdown 全文</small>
                </span>
              </div>
              <div>
                <span className="source-icon tone-cinnabar">
                  <Icon name="issues" size={15} />
                </span>
                <span>
                  <strong>{issues.length} 个工单</strong>
                  <small>司南 · 标题与验收条件</small>
                </span>
              </div>
              <div>
                <span className="source-icon tone-gold">
                  <Icon name="repos" size={15} />
                </span>
                <span>
                  <strong>{repos.length} 个仓库</strong>
                  <small>多宝 · 描述与分支</small>
                </span>
              </div>
            </div>
          </section>

          <section className="search-tip search-tip-large">
            <span className="aside-quote-mark" aria-hidden="true">
              〝
            </span>
            <p>把问题写得具体一点，索引就会更像一面镜子。</p>
            <span>天璇 · 搜索札记</span>
          </section>
        </div>
      )}
    </div>
  );
}
