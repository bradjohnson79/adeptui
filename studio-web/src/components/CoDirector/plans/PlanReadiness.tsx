import type { PlanReadinessReport } from "./types";

export function PlanReadiness({ report }: { report: PlanReadinessReport | null }) {
  if (!report) {
    return <p className="muted">Readiness not loaded.</p>;
  }
  const diverge =
    report.snapshotReadiness &&
    report.currentReadiness &&
    report.snapshotReadiness !== report.currentReadiness;
  return (
    <div className="codirector-plan-readiness" data-testid="codirector-plan-readiness">
      <p>
        Snapshot: <strong>{report.snapshotReadiness || "unknown"}</strong>
      </p>
      <p>
        Current: <strong>{report.currentReadiness || "unknown"}</strong>
      </p>
      {diverge || report.requiresRefresh ? (
        <p className="codirector-plan-readiness-stale" data-testid="codirector-plan-readiness-stale">
          Capabilities changed since the plan snapshot. Revise or refresh before later-wave execution.
          {(report.changedCapabilities || []).length
            ? ` Changed: ${(report.changedCapabilities || []).slice(0, 6).join(", ")}`
            : ""}
        </p>
      ) : null}
    </div>
  );
}
