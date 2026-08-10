export type WorkspaceId = "timeline" | "codirector" | "magi";

export type WorkspaceViewMode = "STANDARD" | "EXPANDED" | "FULLSCREEN";

export type WorkspaceViewportMode = "STANDARD" | "EXPANDED";

export interface WorkspaceFullscreenState {
  workspaceId: WorkspaceId;
  isFullscreen: boolean;
  previousViewMode: WorkspaceViewportMode;
  enteredBy: "BUTTON" | "SHORTCUT";
}

export interface WorkspaceViewPreference {
  workspaceId: WorkspaceId;
  lastViewMode: WorkspaceViewMode;
  panelSizes: Record<string, number>;
  collapsedPanels: string[];
}

export interface FullscreenWorkspaceController {
  workspaceId: WorkspaceId;
  isFullscreen: boolean;
  enterFullscreen: () => Promise<void>;
  exitFullscreen: () => Promise<void>;
  toggleFullscreen: () => Promise<void>;
}

export interface FullscreenPlatformAdapter {
  requestFullscreen: (element: HTMLElement) => Promise<void>;
  exitFullscreen: () => Promise<void>;
  getFullscreenElement: () => Element | null;
}
