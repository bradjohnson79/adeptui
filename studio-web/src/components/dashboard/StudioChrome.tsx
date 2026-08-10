import type { ReactNode } from "react";
import type { EditorTab } from "../../core/workspaces";
import { AppChrome } from "./AppChrome";

export { SystemStatusStrip } from "./SystemStatusStrip";

/**
 * Shared application chrome — EXE-style menu bar:
 * Project | Setup | Production | Status | Co-Director | Search
 * Fixed on scroll; breadcrumbs below.
 */
export function StudioChrome({
  variant = "home",
  projectName,
  workspaceLabel,
  onOpenCoDirector,
  onSetup,
  projectId,
  queuedJobs,
  activeWorkspace,
  onNavigateWorkspace,
  onNewProject,
  onExport,
  breadcrumbs,
}: {
  variant?: "home" | "project";
  projectName?: string;
  workspaceLabel?: string;
  /** @deprecated */
  leftExtra?: ReactNode;
  /** @deprecated hamburger removed */
  rightExtra?: ReactNode;
  onOpenCoDirector?: () => void;
  onSetup?: () => void;
  searchValue?: string;
  onSearchChange?: (v: string) => void;
  onSearchSubmit?: () => void;
  projectId?: string;
  queuedJobs?: number | null;
  activeWorkspace?: EditorTab;
  onNavigateWorkspace?: (tab: EditorTab) => void;
  onNewProject?: () => void;
  onExport?: () => void;
  breadcrumbs?: { label: string; onClick?: () => void }[];
}) {
  return (
    <AppChrome
      variant={variant}
      projectId={projectId}
      projectName={projectName}
      workspaceLabel={workspaceLabel}
      activeWorkspace={activeWorkspace}
      onNavigateWorkspace={onNavigateWorkspace}
      onOpenCoDirector={onOpenCoDirector}
      onSetup={onSetup}
      onNewProject={onNewProject}
      onExport={onExport}
      queuedJobs={queuedJobs}
      breadcrumbs={breadcrumbs}
    />
  );
}
