import type { ProductionPlanStep } from "./types";

export function PlanRevisionDiff({
  beforeSteps,
  afterSteps,
  reason,
}: {
  beforeSteps: ProductionPlanStep[];
  afterSteps: ProductionPlanStep[];
  reason?: string;
}) {
  const beforeIds = new Set(beforeSteps.map((s) => s.stepId));
  const afterIds = new Set(afterSteps.map((s) => s.stepId));
  const added = afterSteps.filter((s) => !beforeIds.has(s.stepId));
  const removed = beforeSteps.filter((s) => !afterIds.has(s.stepId));
  const reordered = afterSteps.filter((s, i) => {
    const prev = beforeSteps.find((b) => b.stepId === s.stepId);
    return prev && (prev.order || 0) !== (s.order || i + 1);
  });
  return (
    <div className="codirector-plan-revision-diff" data-testid="codirector-plan-revision-diff">
      <h4>Revision diff</h4>
      {reason ? <p className="muted">{reason}</p> : null}
      <ul>
        <li>Added: {added.length ? added.map((s) => s.title).join(", ") : "none"}</li>
        <li>Removed: {removed.length ? removed.map((s) => s.title).join(", ") : "none"}</li>
        <li>Reordered: {reordered.length ? reordered.map((s) => s.title).join(", ") : "none"}</li>
      </ul>
      <p className="muted">Diff is shown before approval; no production execution begins.</p>
    </div>
  );
}
