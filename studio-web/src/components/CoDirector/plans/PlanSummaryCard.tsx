import { CoDirectorPlanCard } from "../cards";
import type { ProductionPlan } from "./types";

export function PlanSummaryCard({ plan }: { plan: ProductionPlan }) {
  const openBlockers = (plan.blockers || []).filter((b) => b.state === "open").length;
  const steps = plan.steps || [];
  const readySteps = steps.filter((s) => s.state === "ready").length;
  return (
    <CoDirectorPlanCard
      title={plan.title}
      meta={`${plan.state} · v${plan.version}${plan.unapproved ? " · unapproved draft" : ""}`}
      testId="codirector-plan-summary"
    >
      <p className="muted">{plan.objective || plan.description || "No objective recorded."}</p>
      <ul className="codirector-plan-summary-stats">
        <li>Readiness: {plan.capabilitySnapshot?.readiness || "unknown"}</li>
        <li>
          Steps: {readySteps}/{steps.length} ready (persisted states only)
        </li>
        <li>Open blockers: {openBlockers}</li>
      </ul>
      {plan.unapproved ? (
        <p className="codirector-plan-unapproved" data-testid="codirector-plan-unapproved">
          Unapproved draft — cannot authorize production actions.
        </p>
      ) : null}
    </CoDirectorPlanCard>
  );
}
