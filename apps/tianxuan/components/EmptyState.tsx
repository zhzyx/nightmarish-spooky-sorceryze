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
  eyebrow,
  actionLabel,
  actionHref,
  onAction,
  compact = false,
}: EmptyStateProps) {
  return (
    <div className={`empty-state${compact ? " empty-state-compact" : ""}`}>
      <span className="empty-state-symbol" aria-hidden="true"><Icon name="search" size={23} /></span>
      {eyebrow && <p className="empty-eyebrow">{eyebrow}</p>}
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
