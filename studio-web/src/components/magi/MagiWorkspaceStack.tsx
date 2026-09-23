import type { ReactNode } from "react";
import { TimelineWorkspaceStack } from "../timeline-master/TimelineWorkspaceStack";

/**
 * Magi preview/timeline vertical stack — reuses Timeline Generator divider
 * with MAGI-owned 50/50 persistence (never Timeline Large Viewer).
 */
export function MagiWorkspaceStack({
  monitor,
  timeline,
  projectId,
  extraControls,
  expanded = false,
}: {
  monitor: ReactNode;
  timeline: ReactNode;
  projectId?: string | null;
  extraControls?: ReactNode;
  expanded?: boolean;
}) {
  return (
    <div className="magi-workspace-stack" data-testid="magi-workspace-stack">
      <TimelineWorkspaceStack
        monitor={monitor}
        timeline={timeline}
        projectId={projectId}
        extraControls={extraControls}
        splitProfile="magi"
        expanded={expanded}
      />
    </div>
  );
}
