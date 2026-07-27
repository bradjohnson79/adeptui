import { useEffect, useState } from "react";
import { api } from "../../api";

export function ProductionPlanPanel({ projectId }: { projectId: string }) {
  const [data, setData] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await api.m214Plan(projectId);
      if (!cancelled) setData(res);
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const stages = (data?.stages as Array<{ id: string; status: string }>) || [];

  return (
    <section className="m214-plan" data-testid="m214-production-plan" aria-label="Production plan">
      <h3>Production plan</h3>
      <ol>
        {stages.map((s) => (
          <li key={s.id} data-status={s.status} aria-current={s.status === "current" ? "step" : undefined}>
            {s.id}
            <span className={`m214-status m214-status-${s.status}`}> {s.status}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}
