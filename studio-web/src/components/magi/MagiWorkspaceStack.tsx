import type { ReactNode } from "react";
import { TimelineWorkspaceStack } from "../timeline-master/TimelineWorkspaceStack";

/**
 * Magi preview/timeline vertical stack — reuses Timeline Generator divider math
 * and project-scoped height persistence with Magi-facing testids.
 */
export function MagiWorkspaceStack({
  monitor,
  timeline,
  projectId,
  extraControls,
}: {
  monitor: ReactNode;
  timeline: ReactNode;
  projectId?: string | null;
  extraControls?: ReactNode;
}) {
  return (
    <div className="magi-workspace-stack" data-testid="magi-workspace-stack">
      <TimelineWorkspaceStack
        monitor={monitor}
        timeline={timeline}
        projectId={projectId}
        extraControls={extraControls}
      />
    </div>
  );
}
