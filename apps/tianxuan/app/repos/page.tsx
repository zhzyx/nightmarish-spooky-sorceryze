import { currentActor } from "@/lib/server-api";
import type { Metadata } from "next";
import { cookies } from "next/headers";
import Link from "next/link";
import { Icon } from "@/components/Icon";
import { LocalGitRepos } from "@/components/LocalGitRepos";
import { MergeQueuePanel } from "@/components/MergeQueuePanel";
import { RepoPulls } from "@/components/RepoPulls";
import { RepoTree } from "@/components/RepoTree";
import { fetchRepoCapabilities, fetchRepos } from "@/lib/server-api";
import { NativeRepoBrowser } from "@/components/NativeRepoBrowser";
import { LOCALE_COOKIE, normalizeLocale, translate, type MessageKey } from "@/lib/i18n";

export function generateMetadata(): Metadata {
  const locale = normalizeLocale(cookies().get(LOCALE_COOKIE)?.value);
  return { title: translate(locale, "repos.title") };
}

export const dynamic = "force-dynamic";

export default async function ReposPage() {
  const locale = normalizeLocale(cookies().get(LOCALE_COOKIE)?.value);
  const t = (key: MessageKey) => translate(locale, key);
  const actor = await currentActor();
  const capabilities = actor ? await fetchRepoCapabilities().catch(() => null) : null;
  const showGit = capabilities?.git !== false;
  const liveRepos = actor && showGit ? await fetchRepos(actor).catch(() => null) : null;

  return (
    <div className="page-stack repos-page">
      <header className="page-header">
        <div className="page-title-group">
          <h1>
            {t("repos.title")}
            {locale === "zh" ? <span className="title-period">。</span> : null}
          </h1>
        </div>
        <div className="page-actions">
          {!actor && <Link className="btn btn-ghost" href="/login">{t("repos.login")}</Link>}
          <Link className="btn btn-ghost" href="/docs/duobao-git">
            <Icon name="docs" size={16} />
            {t("repos.guide")}
          </Link>
          <Link className="btn btn-primary" href="/issues">
            <Icon name="issues" size={16} />
            {t("repos.viewQueue")}
          </Link>
        </div>
      </header>

      {capabilities?.native_candidates && <NativeRepoBrowser />}

      {showGit && (
        <>
          <LocalGitRepos />
          <RepoTree />
          <MergeQueuePanel />
          <RepoPulls />
        </>
      )}

      {liveRepos && liveRepos.length > 0 ? (
        <section className="panel" aria-labelledby="live-repos-title">
          <div className="section-heading">
            <div>
              <p className="section-kicker">GITEA · LIVE</p>
              <h2 id="live-repos-title">{t("repos.liveTitle")}</h2>
            </div>
            <span className="section-note">
              {liveRepos.length} {t("repos.liveNote")}
            </span>
          </div>
          <div className="reading-list live-list">
            {liveRepos.slice(0, 8).map((repo) => (
              <div className="reading-item" key={repo.full_name}>
                <span className="reading-index">{repo.private ? t("repos.private") : t("repos.public")}</span>
                <span className="reading-copy">
                  <strong>{repo.full_name}</strong>
                  <span>
                    {t("repos.defaultBranch")} {repo.default_branch}
                  </span>
                </span>
                <Icon name="repos" size={14} />
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
