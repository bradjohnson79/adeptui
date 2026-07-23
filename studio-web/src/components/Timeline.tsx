import { useMemo } from "react";
import type { Project } from "../types";
import { api } from "../api";
import { PanelHeading } from "./HelpTip";

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

  return (
    <div className="panel timeline">
      <PanelHeading
        title="Scenes"
        tip="Ordered story beats for this project. Select one to edit Director tracks; total duration is capped near 30s for local renders."
      >
        <span className="scene-meta">{total.toFixed(1)}s / 30s</span>
      </PanelHeading>
      {project.scenes.map((scene) => (
        <div
          key={scene.id}
          className={`scene-block ${selectedId === scene.id ? "active" : ""}`}
          onClick={() => onSelect(scene.id)}
        >
          <div className="scene-head">
            <strong>
              {scene.index + 1}. {scene.name}
            </strong>
            <span className="scene-meta">
              {scene.engine.replace(/^fal_/, "FAL/").toUpperCase()} · {scene.duration_sec}s
            </span>
          </div>
          <p className="scene-meta" style={{ marginTop: 6 }}>
            {scene.prompt || "Open Director tracks to edit media, prompts, audio, SFX, lip sync"}
          </p>
        </div>
      ))}
      <button
        onClick={async () => {
          await api.addScene(project.id, {
            name: `Scene ${project.scenes.length + 1}`,
            engine: project.engine_default,
            duration_sec: 5,
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
