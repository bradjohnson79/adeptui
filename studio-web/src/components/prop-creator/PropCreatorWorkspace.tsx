import type { Project } from "../../types";
import { PropCreatorCore } from "../CoDirector/PropCreator/PropCreatorCore";

export function PropCreatorWorkspace({
  project,
  onGo,
}: {
  project: Project;
  onGo?: (tab: string) => void;
}) {
  return (
    <PropCreatorCore
      projectId={project.id}
      variant="standard"
      onGoTab={(tab) => onGo?.(tab === "spatial_map" ? "spatial" : tab)}
    />
  );
}
