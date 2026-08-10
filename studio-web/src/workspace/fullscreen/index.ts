export type {
  FullscreenPlatformAdapter,
  FullscreenWorkspaceController,
  WorkspaceFullscreenState,
  WorkspaceId,
  WorkspaceViewMode,
  WorkspaceViewPreference,
  WorkspaceViewportMode,
} from "./types";
export { browserFullscreenAdapter, getFullscreenAdapter, setFullscreenAdapter } from "./platformAdapter";
export {
  loadWorkspaceViewPreference,
  rememberExpandedLayout,
  rememberViewportMode,
  saveWorkspaceViewPreference,
  viewportModeFromPreference,
} from "./workspaceViewPrefs";
export { useWorkspaceFullscreen } from "./useWorkspaceFullscreen";
export type { UseWorkspaceFullscreenOptions, UseWorkspaceFullscreenResult } from "./useWorkspaceFullscreen";
export { WorkspaceFullscreenControls } from "./WorkspaceFullscreenControls";
export { WorkspaceFullscreenBanner } from "./WorkspaceFullscreenBanner";
import "./workspace-fullscreen.css";
