import type { Metadata } from "next";
import Link from "next/link";
import { Icon } from "@/components/Icon";
import {
  getDoc,
  requirements,
  type RequirementStatus,
} from "@/lib/data";
import {
  fetchRequirementProgress,
  fetchRequirements,
  type ApiRequirement,
  type ApiRequirementProgress,
} from "@/lib/requirements-api";

export const metadata: Metadata = {
  title: "需求",
};

// 实时需求依赖每次请求的 TIANXUAN_ACTOR，禁用静态化。
export const dynamic = "force-dynamic";

const LIVE_REQUIREMENT_LIMIT = 8;

const statusClass: Record<RequirementStatus, string> = {
  澄清中: "is-clarifying",
  已成稿: "is-ready",
  拆单中: "is-split",
  已拆单: "is-split",
  已验收: "is-accepted",
};

const flowSteps = [
  {
    index: "01",
    title: "对话",
    copy: "把零散判断、截图与链接交给偃师。",
  },
  {
    index: "02",
    title: "成稿",
    copy: "自动形成范围、非目标与可验证的验收。",
  },
  {
    index: "03",
    title: "拆单",
    copy: "按依赖拆成独立工单，关联设计文档。",
  },
  {
    index: "04",
    title: "回读",
    copy: "每个回执与证据都回到需求原文。",
  },
];

/** 把后端百分比收敛到 0–100 的整数，避免异常值撑破进度条。 */
function normalizePercent(progress: ApiRequirementProgress | null | undefined): number {
  const percent = Number(progress?.percent);
  if (!Number.isFinite(percent)) {
    return 0;
  }
  return Math.min(100, Math.max(0, Math.round(percent)));
}

/**
 * 读取实时需求：先取列表，再并行为前 8 条回读详情（进度与 request_id）。
 *
 * 任意一次请求失败都会向上抛出，由页面静默回退到示例数据。
 */
async function loadLiveRequirements(actor: string): Promise<ApiRequirement[]> {
  const listed = await fetchRequirements(actor);
  const head = listed.slice(0, LIVE_REQUIREMENT_LIMIT);
  return Promise.all(
    head.map(async (requirement) => {
      const detail = await fetchRequirementProgress(actor, requirement.id);
      return {
        ...requirement,
        request_id: detail.request_id ?? requirement.request_id ?? null,
        progress: detail.progress ?? requirement.progress ?? null,
      };
    }),
  );
}

export default async function RequirementsPage() {
  const actor = process.env.TIANXUAN_ACTOR?.trim() ?? "";
  let liveRequirements: ApiRequirement[] = [];
  if (actor) {
    try {
      liveRequirements = await loadLiveRequirements(actor);
    } catch {
      // 后端不可用时静默回退到示例数据，保持页面结构与文案不变。
      liveRequirements = [];
    }
  }

  const clarifying = requirements.filter((requirement) => requirement.status === "澄清中").length;
  const drafted = requirements.filter((requirement) => requirement.status === "已成稿").length;
  const accepted = requirements.filter((requirement) => requirement.status === "已验收").length;
  const tickets = requirements.reduce(
    (total, requirement) => ({
      done: total.done + requirement.ticketsDone,
      all: total.all + requirement.ticketsTotal,
    }),
    { done: 0, all: 0 },
  );

  return (
    <div className="page-stack requirements-page">
      <header className="page-header">
        <div className="page-title-group">
          <p className="eyebrow">
            <span className="eyebrow-rule" aria-hidden="true" />
            YANSHI · REQUIREMENTS
          </p>
          <h1>
            需求<span className="title-period">。</span>
          </h1>
          <p className="page-lede">
            从一句模糊的愿望，到一份能被工单、代码和验收共同引用的文档。需求不是入口表格，而是决策开始变得可回读的地方。
          </p>
        </div>
        <div className="page-actions">
          <Link className="btn btn-ghost" href="/docs/tianxuan-platform">
            <Icon name="docs" size={16} />
            设计基线
          </Link>
          <Link className="btn btn-primary" href="/">
            <Icon name="sparkles" size={16} />
            让偃师起草
          </Link>
        </div>
      </header>

      {liveRequirements.length > 0 ? (
        <section className="panel" aria-labelledby="live-requirements-title">
          <header className="panel-head">
            <div>
              <p className="section-kicker">LIVE API</p>
              <h2 id="live-requirements-title">实时需求</h2>
            </div>
            <span className="section-note">{liveRequirements.length} 条来自后端 · 含工单进度</span>
          </header>

          <div className="reading-list live-list">
            {liveRequirements.map((requirement, index) => {
              const percent = normalizePercent(requirement.progress);
              return (
                <Link className="reading-item" href={`/docs/${requirement.id}`} key={requirement.id}>
                  <span className="reading-index">{String(index + 1).padStart(2, "0")}</span>
                  <span className="reading-copy">
                    <strong>{requirement.title}</strong>
                    <span>
                      {requirement.request_id ? `请求 ${requirement.request_id} · ` : ""}
                      v{requirement.version} · {requirement.status}
                    </span>
                    <span className="meter" aria-hidden="true">
                      <span style={{ width: `${percent}%` }} />
                    </span>
                    <span>
                      {requirement.progress
                        ? `${requirement.progress.done}/${requirement.progress.total} 工单 · ${percent}%`
                        : "进度待回读"}
                    </span>
                  </span>
                  <Icon name="chevronRight" size={14} />
                </Link>
              );
            })}
          </div>
        </section>
      ) : null}

      <section className="requirement-hero">
        <div className="requirement-hero-copy">
          <p className="section-kicker">REQUIREMENT INTAKE</p>
          <h2>
            一句话进来，
            <br />
            <span>一份可执行的需求出去。</span>
          </h2>
          <p>
            偃师会保留原始讨论的出处，把结论写成 Markdown，再交给司南拆成有依赖的工单。人只需确认边界与顺序。
          </p>
          <div className="requirement-hero-tags">
            <span>
              <Icon name="sparkles" size={13} />
              自动成稿
            </span>
            <span>
              <Icon name="link" size={13} />
              双向引用
            </span>
            <span>
              <Icon name="shield" size={13} />
              人工确认
            </span>
          </div>
        </div>

        <div className="requirement-flow" aria-label="需求工作流">
          {flowSteps.map((step, index) => (
            <div className="flow-step" key={step.index}>
              <span className="flow-index">{step.index}</span>
              <div>
                <strong>{step.title}</strong>
                <p>{step.copy}</p>
              </div>
              {index < flowSteps.length - 1 ? <span className="flow-connector" aria-hidden="true" /> : null}
            </div>
          ))}
        </div>

        <span className="requirement-hero-watermark" aria-hidden="true">
          需
        </span>
      </section>

      <section className="requirement-stats" aria-label="需求池摘要">
        <div className="requirement-stat">
          <span className="requirement-stat-label">需求池</span>
          <strong>{String(requirements.length).padStart(2, "0")}</strong>
          <small>本地演示条目</small>
        </div>
        <div className="requirement-stat">
          <span className="requirement-stat-label">澄清中</span>
          <strong>{String(clarifying).padStart(2, "0")}</strong>
          <small>等待边界确认</small>
        </div>
        <div className="requirement-stat">
          <span className="requirement-stat-label">已成稿</span>
          <strong>{String(drafted).padStart(2, "0")}</strong>
          <small>可进入拆单</small>
        </div>
        <div className="requirement-stat">
          <span className="requirement-stat-label">工单进度</span>
          <strong>
            {tickets.done}
            <span>/{tickets.all}</span>
          </strong>
          <small>{accepted} 个需求已验收</small>
        </div>
      </section>

      <div className="requirements-layout">
        <section className="panel requirement-pool" aria-labelledby="requirement-pool-title">
          <header className="panel-head">
            <div>
              <p className="section-kicker">THE POOL</p>
              <h2 id="requirement-pool-title">需求池</h2>
            </div>
            <span className="section-note">按最近更新排序</span>
          </header>

          <div className="req-table-head" aria-hidden="true">
            <span>需求</span>
            <span>进度</span>
            <span>工单</span>
            <span>负责人</span>
            <span>状态</span>
          </div>

          <div className="requirement-list">
            {requirements.map((requirement) => {
              const doc = getDoc(requirement.docId);
              return (
                <Link className="requirement-row" href={`/docs/${requirement.docId}`} key={requirement.id}>
                  <span className="req-main">
                    <span className="req-id">
                      {requirement.id}
                      <span className={`req-status ${statusClass[requirement.status]}`}>
                        <span className="status-dot" aria-hidden="true" />
                        {requirement.status}
                      </span>
                    </span>
                    <span className="req-title">{requirement.title}</span>
                    <span className="req-summary">{requirement.summary}</span>
                    <span className="req-link-doc">
                      <Icon name="docs" size={12} />
                      {doc ? doc.title : "关联文档"}
                    </span>
                  </span>

                  <span className="req-progress">
                    <span className="req-progress-value">
                      <strong>{requirement.progress}%</strong>
                      <span>{requirement.updated}</span>
                    </span>
                    <span className={`meter tone-${requirement.tone}`} aria-hidden="true">
                      <span style={{ width: `${requirement.progress}%` }} />
                    </span>
                  </span>

                  <span className="req-tickets">
                    <strong>{requirement.ticketsDone}</strong>
                    <span>/{requirement.ticketsTotal}</span>
                    <small>工单</small>
                  </span>

                  <span className="req-owner">
                    <span className={`avatar avatar-sm avatar-${requirement.tone}`} aria-hidden="true">
                      {requirement.owner.slice(0, 1)}
                    </span>
                    <span>{requirement.owner}</span>
                  </span>

                  <span className={`req-status req-status-wide ${statusClass[requirement.status]}`}>
                    <span className="status-dot" aria-hidden="true" />
                    {requirement.status}
                  </span>

                  <Icon className="req-arrow" name="chevronRight" size={15} />
                </Link>
              );
            })}
          </div>

          <footer className="panel-foot">
            <span>
              <Icon name="link" size={14} />
              所有需求均关联一份 Markdown 权威文档
            </span>
            <span>已同步至司南</span>
          </footer>
        </section>

        <aside className="requirements-side">
          <section className="panel yanshi-card" aria-labelledby="yanshi-title">
            <header className="yanshi-head">
              <span className="agent-orb" aria-hidden="true">
                偃
              </span>
              <span>
                <strong id="yanshi-title">偃师</strong>
                <small>
                  <span className="live-dot" aria-hidden="true" />
                  需求 Agent · 演示
                </small>
              </span>
              <Icon className="yanshi-mark" name="sparkles" size={18} />
            </header>
            <p className="yanshi-intro">
              从最近 3 份设计文档与 2 个未闭环工单里，识别到 2 条可以进一步成稿的线索。
            </p>
            <div className="suggestion-list">
              <div className="suggestion">
                <span className="suggestion-index">01</span>
                <span>
                  <strong>文档块级协同</strong>
                  <small>建议：先补充冲突合并边界</small>
                </span>
                <Icon name="chevronRight" size={14} />
              </div>
              <div className="suggestion">
                <span className="suggestion-index">02</span>
                <span>
                  <strong>模型调用审计视图</strong>
                  <small>建议：确认 BYOK 范围</small>
                </span>
                <Icon name="chevronRight" size={14} />
              </div>
            </div>
            <Link className="text-link yanshi-link" href="/docs/ai-native-docs">
              查看来源文档
              <Icon name="arrowRight" size={14} />
            </Link>
          </section>

          <section className="panel requirement-guide" aria-labelledby="guide-title">
            <header className="panel-head">
              <div>
                <p className="section-kicker">GOOD REQUIREMENT</p>
                <h2 id="guide-title">一份好需求</h2>
              </div>
              <Icon className="panel-head-icon" name="requirements" size={18} />
            </header>
            <ul className="guide-list">
              <li>
                <span className="guide-index">壹</span>
                <span>
                  <strong>范围可被拒绝</strong>
                  <small>非目标与范围内同等重要。</small>
                </span>
              </li>
              <li>
                <span className="guide-index">贰</span>
                <span>
                  <strong>验收可被回读</strong>
                  <small>使用文件、提交或事件，不用“差不多了”。</small>
                </span>
              </li>
              <li>
                <span className="guide-index">叁</span>
                <span>
                  <strong>顺序可被交接</strong>
                  <small>依赖明确，其他人才能继续推进。</small>
                </span>
              </li>
            </ul>
          </section>

          <section className="aside-quote aside-quote-warm">
            <span className="aside-quote-mark" aria-hidden="true">
              〝
            </span>
            <p>先写清楚不做什么，剩下的路径才会自己浮现。</p>
            <span>偃师手记 · 027</span>
          </section>
        </aside>
      </div>
    </div>
  );
}
