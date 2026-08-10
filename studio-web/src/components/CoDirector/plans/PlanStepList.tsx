import type { ProductionPlanStep } from "./types";

export function PlanStepList({ steps }: { steps: ProductionPlanStep[] }) {
  if (!steps.length) {
    return <p className="muted">No steps in this plan.</p>;
  }
  return (
    <ol className="codirector-plan-steps" data-testid="codirector-plan-steps">
      {steps
        .slice()
        .sort((a, b) => (a.order || 0) - (b.order || 0))
        .map((step) => (
          <li key={step.stepId} data-testid={`codirector-plan-step-${step.stepId}`}>
            <div className="codirector-plan-step-head">
              <strong>{step.title}</strong>
              <span className="muted">
                {step.state || "pending"}
                {step.executionAvailability === "deferred" ? " · deferred" : ""}
              </span>
            </div>
            {step.description ? <p className="muted">{step.description}</p> : null}
            {step.executionAvailability === "deferred" ? (
              <p className="codirector-plan-deferred" data-testid="codirector-plan-step-deferred">
                Planned for a later wave — not executable in Wave 4. No progress invented.
              </p>
            ) : null}
          </li>
        ))}
    </ol>
  );
}
