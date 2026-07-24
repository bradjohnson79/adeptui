import { IconClose, IconCoDirector, IconCollapse, IconExpand, IconOverflow } from "./icons";
import { useCoDirectorSession } from "./CoDirectorSession";
import type { CoDirectorDisplayMode } from "./types";

export function CoDirectorHeader({
  mode,
  onClose,
}: {
  mode: CoDirectorDisplayMode;
  onClose: () => void;
}) {
  const {
    uiContext,
    overflowPanel,
    setOverflowPanel,
    expandToFullScreen,
    collapseToPopup,
    contextPanelOpen,
    setContextPanelOpen,
  } = useCoDirectorSession();

  const subtitle = [uiContext.projectName, uiContext.sceneName].filter(Boolean).join(" · ");

  return (
    <header className="codirector-header">
      <div className="codirector-header-identity">
        <span className="codirector-avatar" aria-hidden>
          <IconCoDirector />
        </span>
        <div>
          <h2>Co-Director</h2>
          {subtitle ? <p className="codirector-subtitle">{subtitle}</p> : null}
        </div>
      </div>
      <div className="codirector-header-actions">
        {mode === "fullscreen" && (
          <button
            type="button"
            className="codirector-icon-btn"
            aria-pressed={contextPanelOpen}
            aria-label={contextPanelOpen ? "Hide context panel" : "Show context panel"}
            title="Context"
            onClick={() => setContextPanelOpen(!contextPanelOpen)}
          >
            <IconCollapse />
          </button>
        )}
        <button
          type="button"
          className="codirector-icon-btn"
          aria-expanded={overflowPanel !== "none"}
          aria-haspopup="menu"
          aria-label="Co-Director menu"
          title="More"
          onClick={() => setOverflowPanel(overflowPanel === "none" ? "options" : "none")}
        >
          <IconOverflow />
        </button>
        {mode === "popup" ? (
          <button
            type="button"
            className="codirector-icon-btn"
            aria-label="Open full-screen Co-Director"
            title="Expand"
            onClick={() => expandToFullScreen()}
          >
            <IconExpand />
          </button>
        ) : (
          <button
            type="button"
            className="codirector-icon-btn"
            aria-label="Return to popup Co-Director"
            title="Collapse"
            onClick={() => collapseToPopup()}
          >
            <IconCollapse />
          </button>
        )}
        <button
          type="button"
          className="codirector-icon-btn"
          aria-label="Close Co-Director"
          title="Close"
          onClick={onClose}
        >
          <IconClose />
        </button>
      </div>
    </header>
  );
}
