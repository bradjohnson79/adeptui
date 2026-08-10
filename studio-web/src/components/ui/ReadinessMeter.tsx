import type { ReactNode } from "react";
import { STATUS_KIND_LABELS, type StatusKind } from "../../status";
import "./status.css";

export type ReadinessMeterProps = { readyCount: number; totalCount: number; blockedCount?: number; kind?: StatusKind; summary?: ReactNode; className?: string };

export function ReadinessMeter({ readyCount, totalCount, blockedCount = 0, kind = "Ready", summary, className = "" }: ReadinessMeterProps) {
  const percent = totalCount > 0 ? Math.min(100, Math.max(0, (readyCount / totalCount) * 100)) : 0;
  return <div className={["ds-readiness-meter", className].filter(Boolean).join(" ")}>
    <div className="ds-readiness-meter__header"><strong>{summary ?? STATUS_KIND_LABELS[kind]}</strong><span>{readyCount} of {totalCount} ready</span></div>
    <progress value={readyCount} max={Math.max(totalCount, 1)} aria-label={`${readyCount} of ${totalCount} ready`} />
    {blockedCount > 0 ? <small>{blockedCount} blocked</small> : <small>{Math.round(percent)}% ready</small>}
  </div>;
}
