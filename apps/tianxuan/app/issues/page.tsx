import type { Metadata } from "next";
import Link from "next/link";
import { Icon } from "@/components/Icon";
import { IssueBoard } from "@/components/IssueBoard";
import { issues } from "@/lib/data";

export const metadata: Metadata = {
  title: "工单",
};

export default function IssuesPage() {
  const done = issues.filter((issue) => issue.status === "done").length;
  const blocked = issues.filter((issue) => issue.blocked).length;
  const completion = Math.round((done / issues.length) * 100);

  return (
    <div className="page-stack issues-page">
      <header className="page-header">
        <div className="page-title-group">
          <p className="eyebrow">
            <span className="eyebrow-rule" aria-hidden="true" />
            SINAN · WORK ORDERS
          </p>
          <h1>
            工单<span className="title-period">。</span>
          </h1>
          <p className="page-lede">
            事件推进工作，而不是提醒推动人。看板保留每一步判断，列表保留每一个可以回读的编号。
          </p>
        </div>
        <div className="page-actions">
          <Link className="btn btn-ghost" href="/docs/sinan-events">
            <Icon name="branch" size={16} />
            推进规则
          </Link>
          <Link className="btn btn-primary" href="/requirements">
            <Icon name="sparkles" size={16} />
            让偃师拆单
          </Link>
        </div>
      </header>

      <section className="sprint-banner" aria-label="当前迭代">
        <div className="sprint-main">
          <p className="section-kicker">SPRINT 07 · 冬日切片</p>
          <h2>让文档与工单说同一种语言</h2>
          <span className="sprint-meta">
            <Icon name="clock" size={14} />
            11 月 11 日 — 11 月 20 日 · 还剩 6 天
          </span>
        </div>
        <div className="sprint-progress">
          <div className="sprint-stat">
            <strong>{completion}%</strong>
            <span>整体完成</span>
          </div>
          <div className="meter meter-lg" aria-hidden="true">
            <span style={{ width: `${completion}%` }} />
          </div>
          <small>
            {done} / {issues.length} 已完成
            {blocked > 0 ? ` · ${blocked} 个阻塞` : ""}
          </small>
        </div>
        <div className="sprint-people">
          <div className="avatar-stack">
            <span className="avatar avatar-sm avatar-jade">文</span>
            <span className="avatar avatar-sm avatar-gold">偃</span>
            <span className="avatar avatar-sm avatar-cinnabar">司</span>
            <span className="avatar avatar-sm avatar-mist">S</span>
          </div>
          <span>5 位协作者</span>
        </div>
      </section>

      <IssueBoard initialIssues={issues} />
    </div>
  );
}
