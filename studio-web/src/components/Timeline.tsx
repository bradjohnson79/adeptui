import { useEffect, useMemo, useState } from "react";
import type { Project } from "../types";
import { api } from "../api";
import { PanelHeading } from "./HelpTip";
import type { SceneTimelineMaster } from "../timelineMaster/contracts";

/** Compact scene strip — detailed tracks live in DirectorTracks. */
export function Timeline({
  project,
  selectedId,
  onSelect,
  onChange,
}: {
  project: Project;
  selectedId?: string;
  onSelect: (id: string) => void;
  onChange: () => void;
}) {
  const total = useMemo(
    () => project.scenes.reduce((s, sc) => s + (sc.duration_sec || 0), 0),
    [project.scenes]
  );
  const [sceneMeta, setSceneMeta] = useState<Record<string, { batches: number; status: string }>>({});

  useEffect(() => {
    let alive = true;
    void Promise.all(
      project.scenes.map(async (scene) => {
        try {
          const result = await api.directorTimelineMaster(project.id, scene.id);
          const master = result.master as SceneTimelineMaster;
          const statuses = master.batchBlocks.map((batch) => batch.status);
          const status = statuses.includes("Failed")
            ? "Needs Attention"
            : statuses.includes("Generating") || statuses.includes("Queued")
              ? "Working"
              : statuses.includes("Ready") || statuses.includes("Approved")
                ? "Ready"
                : "Draft";
          return [scene.id, { batches: master.batchBlocks.length, status }] as const;
        } catch {
          return [scene.id, { batches: 0, status: scene.output_path ? "Ready" : "Draft" }] as const;
        }
      }),
    ).then((entries) => {
      if (!alive) return;
      setSceneMeta(Object.fromEntries(entries));
    });
    return () => {
      alive = false;
    };
  }, [project.id, project.scenes]);

  return (
    <div className="panel timeline">
      <PanelHeading
        title="Scenes"
        tip="Ordered story beats for this project. Select one to open Timeline tracks; total Scene duration is capped at 20s for local Timeline renders."
      >
        <span className="scene-meta">{total.toFixed(1)}s / 20s</span>
      </PanelHeading>
      <div className="timeline-v2__scenes-list">
        {project.scenes.map((scene) => (
          <div
            key={scene.id}
            className={`scene-block ${selectedId === scene.id ? "active" : ""}`}
            onClick={() => onSelect(scene.id)}
          >
            <div className="scene-head">
              <strong>{scene.name}</strong>
              <span className="scene-meta scene-head__meta">
                {scene.engine.replace(/^fal_/, "FAL/").toUpperCase()} · {scene.duration_sec}s
              </span>
            </div>
            <div className="scene-meta" style={{ marginTop: 6 }}>
              {(sceneMeta[scene.id]?.batches ?? 0) || 0} batches · {sceneMeta[scene.id]?.status || "Draft"}
            </div>
          </div>
        ))}
      </div>
      <button
        type="button"
        title="Add a Scene (project total capped at 20s)"
        aria-label="Add a Scene (project total capped at 20 seconds)"
        onClick={async () => {
          const remaining = Math.max(0, 20 - total);
          if (remaining < 0.5) {
            window.alert("Scene total is capped at 20s for local Timeline renders. Shorten an existing Scene first.");
            return;
          }
          await api.addScene(project.id, {
            name: `Scene ${project.scenes.length + 1}`,
            engine: project.engine_default,
            duration_sec: Math.min(5, remaining),
            prompt: "",
          });
          onChange();
        }}
      >
        Add scene
      </button>
    </div>
  );
}
