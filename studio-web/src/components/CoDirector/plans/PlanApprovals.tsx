import type { PlanApprovalRequirement } from "./types";

export function PlanApprovals({ approvals }: { approvals: PlanApprovalRequirement[] }) {
  if (!approvals.length) {
    return <p className="muted">No plan-acceptance requirements recorded.</p>;
  }
  return (
    <ul className="codirector-plan-approvals" data-testid="codirector-plan-approvals">
      {approvals.map((a) => (
        <li key={a.requirementId}>
          <strong>{a.approvalType || "plan_acceptance"}</strong>
          <span className="muted"> · {a.status || "required"}</span>
          {a.reason ? <p className="muted">{a.reason}</p> : null}
          <p className="muted">Plan acceptance is distinct from production-action approval.</p>
        </li>
      ))}
    </ul>
  );
}
