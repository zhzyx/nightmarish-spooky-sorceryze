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
  requirements,
  repos,
  type Tone,
} from "@/lib/data";
import { fetchIssues, fetchRepoCapabilities, fetchRepos, fetchRequirements, fetchSearch, type ApiSearchResult } from "@/lib/server-api";
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

type LiveResult = ApiSearchResult & { href: string; icon: IconName };

function LiveSearchResults({
  query,
  results,
  t,
}: {
  query: string;
  results: LiveResult[];
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
      </div>

      {results.length > 0 ? (
        <div className="search-results-list">
          {results.map((result) => (
            <Link
              className="search-result"
              href={result.href}
              key={result.href + result.id}
            >
              <span className="search-result-icon tone-jade">
                <Icon name={result.icon} size={17} />
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
  const liveResults: LiveResult[] = [];
  const failedScopes: string[] = [];
  let showNativeCatalog = false;
  if (query && actor) {
    const matches = (value: string) => value.toLowerCase().includes(needle);
    const loaders: Record<Exclude<SearchType, "all">, () => Promise<LiveResult[]>> = {
      docs: async () => (await fetchSearch(actor, query)).map(doc => ({
        ...doc, href: `/docs/${encodeURIComponent(doc.id)}`, icon: "file",
      })),
      issues: async () => (await fetchIssues(actor))
        .filter(issue => matches(`#${issue.number} ${issue.title} ${issue.status}`))
        .map(issue => ({
          id: issue.id, kind: "工单", title: `#${issue.number} ${issue.title}`, snippet: issue.status,
          href: `/issues/${encodeURIComponent(issue.id)}`, icon: "issues",
        })),
      requirements: async () => (await fetchRequirements(actor))
        .filter(req => matches(`${req.title} ${req.id} ${req.request_id ?? ""}`))
        .map(req => ({
          id: req.id, kind: "需求", title: req.title, snippet: req.status,
          href: `/docs/${encodeURIComponent(req.id)}`, icon: "requirements",
        })),
      repos: async () => {
        const capabilities = await fetchRepoCapabilities();
        showNativeCatalog = capabilities.native_candidates;
        if (!capabilities.git) return [];
        return (await fetchRepos(actor)).filter(repo => matches(repo.full_name)).map(repo => ({
          id: repo.full_name, kind: "仓库", title: repo.full_name, snippet: repo.default_branch,
          href: "/repos", icon: "repos",
        }));
      },
    };
    const scopes = searchScopes.filter(scope => scope.id !== "all" && (activeType === "all" || scope.id === activeType));
    const responses = await Promise.allSettled(scopes.map(scope => loaders[scope.id as Exclude<SearchType, "all">]()));
    const seen = new Set<string>();
    responses.forEach((response, index) => {
      if (response.status === "rejected") {
        failedScopes.push(scopes[index].label);
        return;
      }
      for (const item of response.value) {
        const key = item.href + item.id;
        if (!seen.has(key)) liveResults.push(item);
        seen.add(key);
      }
    });
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

  return (
    <div className="page-stack search-page">
      <header className="search-hero">
        <h1>
          {t("search.title")}
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
          {activeType !== "all" && <input type="hidden" name="type" value={activeType} />}
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
              <span>{formatMessage(t("search.found"), { count: visibleResults.length + liveResults.length })}</span>
            </p>
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
              </Link>
            ))}
          </div>

          <div className="route-results">
            <div className="search-main">
              {failedScopes.length > 0 && <p role="status">{locale === "zh" ? "暂时无法读取" : "Currently unavailable"} · {failedScopes.join(" · ")}</p>}
              {actor && (liveResults.length > 0 || failedScopes.length === 0) ? (
                <LiveSearchResults query={query} results={liveResults} t={t} />
              ) : null}

              {showNativeCatalog && <p className="native-search-note">
                {locale === "zh" ? "仓库搜索覆盖 Git 仓库。" : "Repository search covers Git repositories."}{" "}
                <Link className="text-link" href="/repos#native-repo-title">
                  {locale === "zh" ? "浏览原生模块目录" : "Browse native modules"}
                </Link>
              </p>}

              {visibleResults.length > 0 ? (
                <>
                  <h2>{t("search.localIndex")}</h2>
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
              ) : !actor || (!liveResults.length && !failedScopes.length) ? (
                <EmptyState
                  actionHref="/search"
                  actionLabel={t("search.clear")}
                  description={t("search.emptyDesc")}
                  eyebrow="DITING · NO MATCH"
                  title={t("search.emptyTitle")}
                />
              ) : null}
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
