import { PropCreatorCore } from "./PropCreatorCore";

export type PropCreatorPanelProps = {
  projectId: string;
  onGoTab?: (tab: string, extra?: Record<string, string>) => void;
};

export function PropCreatorPanel({ projectId, onGoTab }: PropCreatorPanelProps) {
  return <PropCreatorCore projectId={projectId} variant="express" onGoTab={onGoTab} />;
}
