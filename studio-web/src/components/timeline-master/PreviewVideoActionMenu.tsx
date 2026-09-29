import type { VideoRetakeSession } from "../../timelineMaster/videoRetake";

export function PreviewVideoActionMenu({
  enabled,
  showWhenDisabled = false,
  retakeActive = false,
  onOpenRetake,
  isFullscreen = false,
  onToggleFullscreen,
}: {
  enabled: boolean;
  showWhenDisabled?: boolean;
  retakeActive?: boolean;
  onOpenRetake?: () => void;
  isFullscreen?: boolean;
  onToggleFullscreen?: () => void | Promise<void>;
  session?: VideoRetakeSession;
}) {
  if ((!enabled && !showWhenDisabled) || !onOpenRetake) return null;
  const locked = !enabled;

  return (
    <div data-testid="timeline-open-retake" style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
      <button
        type="button"
        className={`timeline-retake-launcher${retakeActive ? " is-pressed" : ""}`}
        data-testid="preview-video-retake"
        title={retakeActive ? "Close Re-Take" : "Change this part of the video"}
        aria-label="Re-Take"
        aria-pressed={retakeActive}
        disabled={locked}
        onClick={onOpenRetake}
      >
        Re-Take
      </button>
      {onToggleFullscreen && (
        <button
          type="button"
          className="timeline-retake-launcher"
          data-testid="preview-video-fullscreen"
          title={isFullscreen ? "Exit Full Screen" : "Full Screen"}
          aria-label={isFullscreen ? "Exit Full Screen" : "Full Screen"}
          aria-pressed={isFullscreen}
          disabled={locked}
          onClick={onToggleFullscreen}
        >
          {isFullscreen ? "Exit Full Screen" : "Full Screen"}
        </button>
      )}
    </div>
  );
}
