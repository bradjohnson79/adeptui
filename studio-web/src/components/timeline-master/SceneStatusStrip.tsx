import { useEffect, useState } from "react";
import { api } from "../../api";

const STATUS_ORDER = [
  "Draft",
  "Planning",
  "Ready",
  "Generating",
  "Review",
  "Approved",
  "Locked",
] as const;

/**
 * SceneStatusStrip — aggregate scene lifecycle counts across the project
 * (SCENE_HAS_LIFECYCLE_STATUS). Read-only; consumed from the Co-Director
 * scene-status endpoint. e.g. "18 Approved · 7 Generating · 41 Draft".
 */
export function SceneStatusStrip({ projectId }: { projectId: string }) {
  const [data, setData] = useState<Awaited<ReturnType<typeof api.getTimelineSceneStatus>> | null>(null);

  useEffect(() => {
    let alive = true;
    api.getTimelineSceneStatus(projectId).then((r) => {
      if (alive) setData(r);
    }).catch(() => {
      if (alive) setData(null);
    });
    return () => {
      alive = false;
    };
  }, [projectId]);

  if (!data || !data.ok || data.totalScenes === 0) return null;

  const parts = STATUS_ORDER.filter((s) => (data.counts[s] || 0) > 0).map((s) => (
    <span key={s} className="scene-status-pill" data-status={s.toLowerCase()}>
      <strong>{data.counts[s]}</strong> {s}
    </span>
  ));

  if (parts.length === 0) return null;

  return (
    <div className="scene-status-strip" data-testid="scene-status-strip">
      {parts}
    </div>
  );
}
