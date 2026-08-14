import { SceneCreatorCore } from "./SceneCreatorCore";

export type SceneCreatorPanelProps = {
  projectId: string;
  onGoTab?: (tab: string, extra?: Record<string, string>) => void;
};

export function SceneCreatorPanel({ projectId, onGoTab }: SceneCreatorPanelProps) {
  return <SceneCreatorCore projectId={projectId} variant="express" onGoTab={onGoTab} />;
}
