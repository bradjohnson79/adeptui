import type { ProductionPlanStep } from "./types";

export function PlanDependencyView({ steps }: { steps: ProductionPlanStep[] }) {
  const withDeps = steps.filter((s) => (s.dependsOn || []).length > 0);
  if (!withDeps.length) {
    return <p className="muted">No step dependencies recorded.</p>;
  }
  return (
    <ul className="codirector-plan-deps" data-testid="codirector-plan-deps">
      {withDeps.map((s) => (
        <li key={s.stepId}>
          {s.title} depends on {(s.dependsOn || []).join(", ")}
        </li>
      ))}
    </ul>
  );
}
