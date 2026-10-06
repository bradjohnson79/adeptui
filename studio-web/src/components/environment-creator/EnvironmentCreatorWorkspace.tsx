import type { Project } from "../../types";
import { EnvironmentCreatorSurface } from "../CoDirector/EnvironmentCreator/EnvironmentCreatorSurface";

export function EnvironmentCreatorWorkspace({
  project,
  onGo,
}: {
  project: Project;
  onGo?: (tab: string, extra?: Record<string, string>) => void;
}) {
  return (
    <EnvironmentCreatorSurface
      projectId={project.id}
      variant="standard"
      onGoTab={(tab, extra) => onGo?.(tab === "spatial_map" ? "spatial" : tab, extra)}
    />
  );
}
