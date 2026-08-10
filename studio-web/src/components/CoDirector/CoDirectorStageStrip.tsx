import { useEffect, useState } from "react";
import { api } from "../../api";
import { useCoDirectorSession } from "./CoDirectorSession";

async function loadActivePlan(projectId: string) {
  const active = await api.getCoDirectorActivePlan(projectId);
  const activePlanId = String(active.plan?.planId || "");
  if (!activePlanId) return null;
  const resolved = await api.getCoDirectorProjectPlanById(projectId, activePlanId);
  return (resolved.plan || null) as Record<string, any> | null;
}

export function CoDirectorStageStrip({ onOpenProduction }: { onOpenProduction: () => void }) {
  const { uiContext } = useCoDirectorSession();
  const [current, setCurrent] = useState<string>("");
  const [next, setNext] = useState<string>("");

  useEffect(() => {
    const projectId = uiContext.projectId;
    if (!projectId) {
      setCurrent("");
      setNext("");
      return;
    }
    let cancelled = false;
    loadActivePlan(projectId)
      .then((res) => {
        if (cancelled) return;
        const stages =
          (res?.steps as Array<{ stepId?: string; id?: string; status?: string }>) ||
          (res?.stages as Array<{ id: string; status: string }>) ||
          [];
        const cur = stages.find((s) => s.status === "current");
        const upcoming = stages.find((s) => s.status === "upcoming");
        setCurrent(String(cur?.stepId || cur?.id || res?.activeStepId || ""));
        setNext(String(upcoming?.stepId || upcoming?.id || ""));
      })
      .catch(() => {
        if (!cancelled) {
          setCurrent("");
          setNext("");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [uiContext.projectId]);

  if (!uiContext.projectId || !current) return null;

  const label = current.replace(/_/g, " ");
  const nextLabel = next ? next.replace(/_/g, " ") : "—";

  return (
    <button
      type="button"
      className="codirector-stage-strip"
      data-testid="codirector-stage-strip"
      onClick={onOpenProduction}
    >
      <span>
        <strong>{label}</strong> · Current
      </span>
      <span>Next: {nextLabel}</span>
    </button>
  );
}
