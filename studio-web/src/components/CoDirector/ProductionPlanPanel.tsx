import { useEffect, useState } from "react";
import { api } from "../../api";

async function loadActivePlan(projectId: string) {
  const active = await api.getCoDirectorActivePlan(projectId);
  const activePlanId = String(active.plan?.planId || "");
  if (!activePlanId) return null;
  const resolved = await api.getCoDirectorProjectPlanById(projectId, activePlanId);
  return (resolved.plan || null) as Record<string, unknown> | null;
}

export function ProductionPlanPanel({ projectId }: { projectId: string }) {
  const [data, setData] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await loadActivePlan(projectId);
      if (!cancelled) setData(res);
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const stages =
    (data?.steps as Array<{ stepId?: string; id?: string; status: string }>) ||
    (data?.stages as Array<{ id: string; status: string }>) ||
    [];

  return (
    <section className="m214-plan" data-testid="m214-production-plan" aria-label="Production plan">
      <h3>Production plan</h3>
      <ol>
        {stages.map((s) => (
          <li key={String(s.stepId || s.id)} data-status={s.status} aria-current={s.status === "current" ? "step" : undefined}>
            {String(s.stepId || s.id)}
            <span className={`m214-status m214-status-${s.status}`}> {s.status}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}
