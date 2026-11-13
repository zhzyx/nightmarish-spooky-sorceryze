import { EmptyState } from "@/components/EmptyState";

export default function NotFound() {
  return (
    <div className="page-stack">
      <header className="page-header">
        <div className="page-title-group">
          <p className="eyebrow">
            <span className="eyebrow-rule" aria-hidden="true" />
            TIANXUAN · NOT FOUND
          </p>
          <h1>
            留白<span className="title-period">。</span>
          </h1>
          <p className="page-lede">
            这一页不在当前工作区里，也许被移动了，也许还没有被写下。
          </p>
        </div>
      </header>
      <EmptyState
        actionHref="/docs"
        actionLabel="返回文档空间"
        description="可以从页面树重新进入，或回到工作台让天璇帮你找一条线索。"
        eyebrow="404 · PAGE ABSENT"
        title="没有找到这个页面"
      />
    </div>
  );
}
