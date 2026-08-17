import type { Project } from "../../types";
import { SceneCreatorCore } from "../CoDirector/SceneCreator/SceneCreatorCore";

export function SceneCreatorWorkspace({
  project,
  onGo,
}: {
  project: Project;
  onGo?: (tab: string) => void;
}) {
  return (
    <SceneCreatorCore
      projectId={project.id}
      onGoTab={(tab) => onGo?.(tab === "spatial_map" ? "spatial" : tab)}
    />
  );
}
