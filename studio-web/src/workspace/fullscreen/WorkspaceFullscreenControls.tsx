import type { UseWorkspaceFullscreenResult } from "./useWorkspaceFullscreen";

function ExpandIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <path
        fill="currentColor"
        d="M2 6V2h4v1.5H3.5V6H2zm8-4h4v4h-1.5V3.5H10V2zM2 10h1.5v2.5H6V14H2v-4zm8 4v-1.5h2.5V10H14v4h-4z"
      />
    </svg>
  );
}

function EnterFullscreenIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <path
        fill="currentColor"
        d="M1 1h5v1.5H2.5V6H1V1zm9 0h5v5h-1.5V2.5H10V1zM1 10h1.5v3.5H6V15H1v-5zm9 5v-1.5h3.5V10H15v5h-5z"
      />
      <rect x="5" y="5" width="6" height="6" fill="none" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

function ExitFullscreenIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <path
        fill="currentColor"
        d="M5 1v4H1V3.5h2.5V1H5zm6 0h1.5v2.5H15V5h-4V1zM1 11h4v4H3.5v-2.5H1V11zm10 0h4v1.5h-2.5V15H11v-4z"
      />
    </svg>
  );
}

export function WorkspaceFullscreenControls({
  fs,
  onExpand,
  expandActive = false,
  showExpand = true,
  className,
}: {
  fs: UseWorkspaceFullscreenResult;
  onExpand?: () => void;
  expandActive?: boolean;
  showExpand?: boolean;
  className?: string;
}) {
  return (
    <div className={`workspace-fs-controls ${className || ""}`.trim()} data-testid="workspace-fullscreen-controls">
      {showExpand && onExpand ? (
        <button
          type="button"
          className="workspace-fs-btn"
          data-testid="workspace-expand"
          title="Expand workspace"
          aria-label="Expand workspace"
          aria-pressed={expandActive}
          onClick={onExpand}
        >
          <ExpandIcon />
          <span className="workspace-fs-btn__label">{expandActive ? "Collapse" : "Expand"}</span>
        </button>
      ) : null}
      <button
        type="button"
        className="workspace-fs-btn"
        data-testid={`workspace-fullscreen-toggle-${fs.workspaceId}`}
        title={fs.isFullscreen ? "Exit full screen" : "Enter full screen (Ctrl+Shift+F)"}
        aria-label={fs.isFullscreen ? "Exit full screen" : "Enter full screen"}
        aria-pressed={fs.isFullscreen}
        onClick={() => void fs.toggleFullscreen()}
      >
        {fs.isFullscreen ? <ExitFullscreenIcon /> : <EnterFullscreenIcon />}
        <span className="workspace-fs-btn__label">{fs.isFullscreen ? "Exit full screen" : "Full screen"}</span>
      </button>
      {fs.error ? (
        <span className="workspace-fs-error" role="alert" data-testid="workspace-fullscreen-error">
          {fs.error}{" "}
          <button type="button" className="workspace-fs-retry" onClick={() => void fs.enterFullscreen()}>
            Try again
          </button>
          <button type="button" className="workspace-fs-retry" onClick={fs.clearError}>
            Dismiss
          </button>
        </span>
      ) : null}
    </div>
  );
}
