import { EnvironmentCreatorSurface } from "../EnvironmentCreator/EnvironmentCreatorSurface";

export type SceneCreatorExpressLauncherProps = {
  projectId: string;
  onGoTab?: (tab: string, extra?: Record<string, string>) => void;
};

/**
 * Co-Director Express Environment Creator surface.
 * Plans/creates the Environment Reference Sheet (ERS) for a location/set.
 * Not shot creation, frame generation, posing, storyboard, or final rendering.
 * Standard Scene Creator production workflows stay untouched.
 */
export function SceneCreatorExpressLauncher({
  projectId,
  onGoTab,
}: SceneCreatorExpressLauncherProps) {
  return (
    <div data-testid="scene-creator-panel">
      <EnvironmentCreatorSurface projectId={projectId} variant="express" onGoTab={onGoTab} />
    </div>
  );
}
