import { currentActor } from "@/lib/server-api";
import type { Metadata } from "next";
import { cookies } from "next/headers";
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
import { fetchSearch, type ApiSearchResult } from "@/lib/server-api";
import { LOCALE_COOKIE, formatMessage, normalizeLocale, translate, type MessageKey } from "@/lib/i18n";

export function generateMetadata(): Metadata {
  const locale = normalizeLocale(cookies().get(LOCALE_COOKIE)?.value);
  return { title: translate(locale, "search.title") };
}

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

function LiveSearchResults({
  query,
  results,
  t,
}: {
  query: string;
  results: ApiSearchResult[];
  t: (key: MessageKey) => string;
}) {
  const kindLabel = (kind: string): string => {
    const keys: Record<string, MessageKey> = {
      文档: "search.scopeDocs",
      工单: "search.scopeIssues",
      仓库: "search.scopeRepos",
      需求: "search.scopeRequirements",
    };
    const key = keys[kind];
    return key ? t(key) : kind;
  };
  return (
    <section aria-labelledby="live-search-title" className="live-search-section">
      <div className="search-summary-row live-search-head">
        <p>
          <strong id="live-search-title">{t("search.liveTitle")}</strong>
          <span>{formatMessage(t("search.liveMeta"), { count: results.length })}</span>
        </p>
        <span className="search-index-tag">
          <span className="live-dot" aria-hidden="true" />
          {t("search.liveTag")}
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
                  <span className="search-result-kind">{kindLabel(result.kind ?? "文档")}</span>
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
        <p className="live-search-empty">{t("search.liveEmpty")}</p>
      )}
    </section>
  );
}

export default async function SearchPage({
  searchParams,
}: {
  searchParams: { q?: string; type?: string };
}) {
  const locale = normalizeLocale(cookies().get(LOCALE_COOKIE)?.value);
  const t = (key: MessageKey) => translate(locale, key);
  const suggestions = [
    { label: t("search.suggestAi"), query: "AI" },
    { label: t("search.suggestEvidence"), query: "验收" },
    { label: t("search.suggestMerge"), query: "合并" },
    { label: t("search.suggestGlass"), query: "毛玻璃" },
    { label: t("search.suggestDesign"), query: "设计" },
  ];
  const searchScopes: { id: SearchType; label: string; icon: IconName }[] = [
    { id: "all", label: t("search.scopeAll"), icon: "search" },
    { id: "docs", label: t("search.scopeDocs"), icon: "docs" },
    { id: "issues", label: t("search.scopeIssues"), icon: "issues" },
    { id: "repos", label: t("search.scopeRepos"), icon: "repos" },
    { id: "requirements", label: t("search.scopeRequirements"), icon: "requirements" },
  ];
  const kindLabel = (kind: string): string => {
    const keys: Record<string, MessageKey> = {
      文档: "search.scopeDocs",
      工单: "search.scopeIssues",
      仓库: "search.scopeRepos",
      需求: "search.scopeRequirements",
    };
    const key = keys[kind];
    return key ? t(key) : kind;
  };
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

  const actor = await currentActor();
  let liveResults: ApiSearchResult[] | null = null;
  if (query && (actor)) {
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
      meta: `${issue.project} · ${issue.status === "done" ? t("issues.colDone") : t("search.openIssue")} · ${issue.updated}`,
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
      meta: `${requirement.id} · ${requirement.status} · ${t("search.ownerPrefix")} ${requirement.owner}`,
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
          {t("search.title")}
          {locale === "zh" ? <span className="title-period">。</span> : null}
        </h1>
        <p className="search-lede">{t("search.lede")}</p>

        <form action="/search" className="global-search-form" role="search">
          <span className="global-search-icon">
            <Icon name="search" size={20} />
          </span>
          <label className="sr-only" htmlFor="global-search-input">
            {t("search.inputLabel")}
          </label>
          <input
            autoComplete="off"
            defaultValue={query}
            id="global-search-input"
            name="q"
            placeholder={t("search.placeholder")}
            type="search"
          />
          <kbd>↵</kbd>
          <button className="btn btn-primary" type="submit">
            {t("search.submit")}
          </button>
        </form>

        <div className="search-quick-row">
          <span>{t("search.try")}</span>
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
              <strong>{formatMessage(t("search.resultsFor"), { query })}</strong>
              <span>{formatMessage(t("search.found"), { count: allResults.length })}</span>
            </p>
            <span className="search-index-tag">
              <span className="live-dot" aria-hidden="true" />
              {t("search.localIndex")}
            </span>
          </div>

          <div aria-label={t("search.scopeAria")} className="search-scope-tabs" role="navigation">
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
                <LiveSearchResults query={query} results={liveResults} t={t} />
              ) : null}

              {visibleResults.length > 0 ? (
                <>
                  <section className="ai-answer" aria-labelledby="ai-answer-title">
                    <div className="ai-answer-head">
                      <span className="ai-answer-orb">
                        <Icon name="sparkles" size={15} />
                      </span>
                      <span>
                        <strong id="ai-answer-title">{t("search.aiTitle")}</strong>
                        <small>{t("search.aiNote")}</small>
                      </span>
                      <span className="ai-answer-badge">LOCAL</span>
                    </div>
                    <p>
                      {formatMessage(t("search.aiBody"), {
                        query,
                        kind: kindLabel(visibleResults[0]?.kind ?? ""),
                        title: visibleResults[0]?.title ?? "",
                        count: visibleResults.length,
                      })}
                    </p>
                    <div className="ai-answer-sources">
                      {visibleResults.slice(0, 3).map((result) => (
                        <Link href={result.href} key={result.id}>
                          <span>{kindLabel(result.kind)}</span>
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
                            <span className="search-result-kind">{kindLabel(result.kind)}</span>
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
                  actionLabel={t("search.clear")}
                  description={t("search.emptyDesc")}
                  eyebrow="DITING · NO MATCH"
                  title={t("search.emptyTitle")}
                />
              ) : null}
            </div>

            <aside className="search-aside">
              <section className="panel search-index-panel">
                <header className="panel-head">
                  <div>
                    <p className="section-kicker">INDEX STATUS</p>
                    <h2>{t("search.indexScope")}</h2>
                  </div>
                  <Icon className="panel-head-icon" name="layers" size={18} />
                </header>
                <div className="index-rows">
                  <div>
                    <span>{t("search.indexDocs")}</span>
                    <strong>{docs.length}</strong>
                  </div>
                  <div>
                    <span>{t("search.indexIssues")}</span>
                    <strong>{issues.length}</strong>
                  </div>
                  <div>
                    <span>{t("search.indexRepos")}</span>
                    <strong>{repos.length}</strong>
                  </div>
                  <div>
                    <span>{t("search.indexReq")}</span>
                    <strong>{requirements.length}</strong>
                  </div>
                </div>
                <p className="index-note">
                  {t("search.indexNote")}
                </p>
              </section>

              <section className="panel search-recent-panel">
                <header className="panel-head">
                  <div>
                    <p className="section-kicker">RECENTLY READ</p>
                    <h2>{t("search.recent")}</h2>
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
                <p>{t("search.tip")}</p>
                <span>{t("search.tipCaption")}</span>
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
                <h2 id="search-suggest-title">{t("search.start")}</h2>
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
                <h2 id="recent-search-title">{t("search.recent")}</h2>
              </div>
              <Link className="text-link" href="/docs">
                {t("search.allDocs")}
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
                <h2 id="scope-title">{t("search.sources")}</h2>
              </div>
            </header>
            <div className="search-source-list">
              <div>
                <span className="source-icon tone-jade">
                  <Icon name="docs" size={15} />
                </span>
                <span>
                  <strong>{formatMessage(t("search.sourceDocs"), { count: docs.length })}</strong>
                  <small>{t("search.sourceDocsNote")}</small>
                </span>
              </div>
              <div>
                <span className="source-icon tone-cinnabar">
                  <Icon name="issues" size={15} />
                </span>
                <span>
                  <strong>{formatMessage(t("search.sourceIssues"), { count: issues.length })}</strong>
                  <small>{t("search.sourceIssuesNote")}</small>
                </span>
              </div>
              <div>
                <span className="source-icon tone-gold">
                  <Icon name="repos" size={15} />
                </span>
                <span>
                  <strong>{formatMessage(t("search.sourceRepos"), { count: repos.length })}</strong>
                  <small>{t("search.sourceReposNote")}</small>
                </span>
              </div>
            </div>
          </section>

          <section className="search-tip search-tip-large">
            <span className="aside-quote-mark" aria-hidden="true">
              〝
            </span>
            <p>{t("search.tipLarge")}</p>
            <span>{t("search.tipLargeCaption")}</span>
          </section>
        </div>
      )}
    </div>
  );
}
