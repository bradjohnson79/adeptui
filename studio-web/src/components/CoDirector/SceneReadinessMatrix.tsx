import { useEffect, useState } from "react";
import { api } from "../../api";

type SceneRow = {
  sceneId: string;
  status: string;
  blockerSummary?: string;
  castReady?: boolean;
  locationReady?: boolean;
  propsReady?: boolean;
  imageReferencesReady?: boolean;
  generationPlanReady?: boolean;
};

const STATUS_LABEL: Record<string, string> = {
  BLOCKED: "Not ready",
  PARTIAL: "Almost ready",
  READY: "Ready to generate",
  IN_PRODUCTION: "In production",
  COMPLETE: "Complete",
};

export function SceneReadinessMatrix({ projectId }: { projectId: string }) {
  const [rows, setRows] = useState<SceneRow[]>([]);
  const [stage, setStage] = useState("");
  const [blocked, setBlocked] = useState<string | null>(null);
  const [handoffs, setHandoffs] = useState<{ timelineReady?: boolean; magiReady?: boolean }>({});

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.getCoDirectorProductionLifecycle(projectId);
        if (cancelled) return;
        const life = res.lifecycle || {};
        setStage(String(life.currentStage || ""));
        setBlocked(res.productionBlockedReason || null);
        setRows((res as { sceneReadinessMatrix?: SceneRow[] }).sceneReadinessMatrix || []);
        setHandoffs((res as { handoffs?: typeof handoffs }).handoffs || {});
      } catch {
        if (!cancelled) setRows([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  return (
    <section
      className="scene-readiness-matrix"
      data-testid="scene-readiness-matrix"
      aria-label="Scene readiness"
    >
      <h3 style={{ marginTop: 0, fontSize: "0.95rem" }}>Scene readiness</h3>
      <p className="muted" style={{ fontSize: "0.85rem" }}>
        {stage ? `Production stage: ${stage.replace(/_/g, " ").toLowerCase()}` : "Checking production…"}
      </p>
      {blocked ? (
        <p data-testid="scene-readiness-blocked" style={{ fontSize: "0.9rem" }}>
          {blocked}
        </p>
      ) : null}
      {rows.length === 0 ? (
        <p className="muted" style={{ fontSize: "0.85rem" }}>
          Scenes appear here when a locked script and cast are ready for production planning.
        </p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0, margin: "0.5rem 0" }}>
          {rows.map((row) => (
            <li
              key={row.sceneId}
              data-testid={`scene-readiness-row-${row.sceneId}`}
              data-status={row.status}
              style={{
                marginBottom: "0.65rem",
                padding: "0.5rem 0",
                borderBottom: "1px solid var(--border-subtle, #3333)",
              }}
            >
              <strong>{row.sceneId}</strong>
              <span className="muted"> — {STATUS_LABEL[row.status] || row.status}</span>
              {row.blockerSummary ? (
                <div className="muted" style={{ fontSize: "0.8rem", marginTop: 4 }}>
                  {row.blockerSummary}
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      <p className="muted" style={{ fontSize: "0.8rem" }} data-testid="scene-readiness-handoffs">
        Timeline {handoffs.timelineReady ? "available" : "waiting"} · Finishing{" "}
        {handoffs.magiReady ? "available" : "waiting"}
      </p>
    </section>
  );
}
