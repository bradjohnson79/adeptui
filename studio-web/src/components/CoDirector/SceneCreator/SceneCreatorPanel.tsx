import { SceneCreatorExpressLauncher } from "./SceneCreatorExpressLauncher";

export type SceneCreatorPanelProps = {
  projectId: string;
  onGoTab?: (tab: string, extra?: Record<string, string>) => void;
};

/** Co-Director Express: introduction + launch into Standard. Not a second editor. */
export function SceneCreatorPanel({ projectId, onGoTab }: SceneCreatorPanelProps) {
  return <SceneCreatorExpressLauncher projectId={projectId} onGoTab={onGoTab} />;
}
