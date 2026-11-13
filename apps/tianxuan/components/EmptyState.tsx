import Link from "next/link";
import { Icon } from "@/components/Icon";

export interface EmptyStateProps {
  title: string;
  description: string;
  eyebrow?: string;
  actionLabel?: string;
  actionHref?: string;
  onAction?: () => void;
  compact?: boolean;
}

export function EmptyState({
  title,
  description,
  eyebrow = "此处留白",
  actionLabel,
  actionHref,
  onAction,
  compact = false,
}: EmptyStateProps) {
  return (
    <div className={`empty-state${compact ? " empty-state-compact" : ""}`}>
      <div className="empty-visual" aria-hidden="true">
        <span className="empty-orbit empty-orbit-one" />
        <span className="empty-orbit empty-orbit-two" />
        <span className="empty-sheet empty-sheet-back" />
        <span className="empty-sheet empty-sheet-front">
          <span className="empty-line empty-line-long" />
          <span className="empty-line" />
          <span className="empty-line empty-line-short" />
        </span>
        <span className="empty-seal">空</span>
        <span className="empty-spark" />
      </div>
      <p className="empty-eyebrow">{eyebrow}</p>
      <h3>{title}</h3>
      <p className="empty-description">{description}</p>
      {actionLabel && onAction ? (
        <button className="btn btn-ghost btn-sm" onClick={onAction} type="button">
          {actionLabel}
          <Icon name="arrowRight" size={14} />
        </button>
      ) : actionLabel && actionHref ? (
        <Link className="btn btn-ghost btn-sm" href={actionHref}>
          {actionLabel}
          <Icon name="arrowRight" size={14} />
        </Link>
      ) : null}
    </div>
  );
}
