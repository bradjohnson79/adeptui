import { TimelineExpressLauncher } from "./TimelineExpressLauncher";

export type TimelinePanelProps = {
  projectId: string;
  onGoTab?: (tab: string, extra?: Record<string, string>) => void;
};

/** Co-Director Express: introduction + launch into Timeline Standard. Not a second editor. */
export function TimelinePanel({ projectId, onGoTab }: TimelinePanelProps) {
  return <TimelineExpressLauncher projectId={projectId} onGoTab={onGoTab} />;
}
