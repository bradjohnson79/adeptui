import type { ProductionPlanBlocker } from "./types";

export function PlanBlockers({ blockers }: { blockers: ProductionPlanBlocker[] }) {
  const open = blockers.filter((b) => b.state !== "resolved" && b.state !== "dismissed");
  if (!open.length) {
    return <p className="muted">No open blockers.</p>;
  }
  return (
    <ul className="codirector-plan-blockers" data-testid="codirector-plan-blockers">
      {open.map((b) => (
        <li key={b.blockerId}>
          <strong>{b.title}</strong>
          <span className="muted"> · {b.severity || "blocking"}</span>
          {b.description ? <p className="muted">{b.description}</p> : null}
        </li>
      ))}
    </ul>
  );
}
