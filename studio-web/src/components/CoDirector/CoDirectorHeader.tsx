import { forwardRef, type ReactNode } from "react";
import { IconButton } from "../ui";
import { IconClose, IconCollapse, IconExpand, IconMenu, IconOverflow } from "./icons";
import { useCoDirectorSession } from "./CoDirectorSession";
import {
  LAYOUT_PRESET_LABELS,
  LAYOUT_PRESET_ORDER,
  type CoDirectorLayoutPreset,
} from "./layoutPresets";
import type { CoDirectorRuntimeState } from "./runtimeState";
import type { CoDirectorDisplayMode } from "./types";

export const CoDirectorHeader = forwardRef<
  HTMLButtonElement,
  {
    mode: CoDirectorDisplayMode;
    onClose: () => void;
    onOpenNav: () => void;
    ready?: boolean;
    runtimeChip?: string;
    runtimeState?: CoDirectorRuntimeState;
    layoutPreset?: CoDirectorLayoutPreset;
    onLayoutPreset?: (preset: CoDirectorLayoutPreset) => void;
    fullscreenControls?: ReactNode;
  }
>(function CoDirectorHeader(
  {
    mode,
    onClose,
    onOpenNav,
    ready = false,
    runtimeChip,
    runtimeState,
    layoutPreset,
    onLayoutPreset,
    fullscreenControls,
  },
  menuBtnRef,
) {
  const {
    overflowPanel,
    setOverflowPanel,
    expandToFullScreen,
    collapseToPopup,
    contextPanelOpen,
    setContextPanelOpen,
    uiContext,
    openStatusPanel,
    statusChecking,
    statusLatestRun,
  } = useCoDirectorSession();

  const showDegraded =
    runtimeState === "Degraded" || runtimeState === "Tool Execution Unavailable";
  const projectLabel = uiContext.projectName?.trim() || "No Project Selected";
  const statusIndicator = statusChecking
    ? "Checking"
    : statusLatestRun?.summary.statusIndicator || "Not Checked";
  const statusTone =
    statusIndicator === "Operational"
      ? ""
      : statusIndicator === "Blocked"
        ? " is-degraded"
        : " is-degraded";

  return (
    <header className="codirector-header" data-testid="codirector-header">
      <div className="codirector-header-identity">
        <IconButton
          ref={menuBtnRef}
          aria-label="Open Co-Director menu"
          title="Menu"
          data-testid="codirector-menu-button"
          onClick={onOpenNav}
        >
          <IconMenu />
        </IconButton>
        <div className="codirector-header-titles">
          <h2>Co-Director</h2>
          <p className="codirector-header-project" data-testid="codirector-header-project" title={projectLabel}>
            {projectLabel}
          </p>
        </div>
      </div>
      <div className="codirector-header-actions">
        {runtimeChip ? (
          <span
            className={`codirector-runtime-chip${showDegraded ? " is-degraded" : ""}`}
            data-testid="codirector-runtime-chip"
            data-runtime-state={runtimeState || ""}
            title={runtimeChip}
          >
            {ready ? <span className="codirector-ready-dot" aria-hidden /> : null}
            {runtimeChip}
          </span>
        ) : ready ? (
          <span className="codirector-ready" data-testid="codirector-ready">
            <span className="codirector-ready-dot" aria-hidden />
            Ready
          </span>
        ) : null}
        <button
          type="button"
          className={`codirector-runtime-chip codirector-status-chip${statusTone}`}
          data-testid="codirector-status-chip"
          onClick={openStatusPanel}
          title={
            statusIndicator === "Not Checked"
              ? "Production Assurance cross-check not run yet (not an intelligence failure). Open status."
              : "Open Co-Director status"
          }
        >
          {statusIndicator}
        </button>
        {mode === "fullscreen" && onLayoutPreset ? (
          <div
            className="codirector-layout-presets"
            role="group"
            aria-label="Layout presets"
            data-testid="codirector-layout-presets"
          >
            {LAYOUT_PRESET_ORDER.map((preset) => (
              <button
                key={preset}
                type="button"
                className={layoutPreset === preset ? "is-active" : undefined}
                aria-pressed={layoutPreset === preset}
                data-testid={`codirector-layout-${preset}`}
                title={LAYOUT_PRESET_LABELS[preset]}
                onClick={() => onLayoutPreset(preset)}
              >
                {LAYOUT_PRESET_LABELS[preset]}
              </button>
            ))}
          </div>
        ) : null}
        {mode === "fullscreen" && (
          <IconButton
            aria-pressed={contextPanelOpen}
            aria-label={contextPanelOpen ? "Hide project content" : "Show project content"}
            title="Project content"
            data-testid="codirector-toggle-content"
            onClick={() => setContextPanelOpen(!contextPanelOpen)}
          >
            <IconCollapse />
          </IconButton>
        )}
        <IconButton
          aria-expanded={overflowPanel !== "none"}
          aria-haspopup="menu"
          aria-label="Co-Director more options"
          title="More"
          data-testid="codirector-overflow-button"
          onClick={() => setOverflowPanel(overflowPanel === "none" ? "options" : "none")}
        >
          <IconOverflow />
        </IconButton>
        {fullscreenControls}
        {mode === "popup" ? (
          <IconButton
            aria-label="Expand workspace"
            title="Expand workspace"
            data-testid="codirector-expand-button"
            onClick={() => expandToFullScreen()}
          >
            <IconExpand />
          </IconButton>
        ) : (
          <IconButton
            aria-label="Return to popup Co-Director"
            title="Collapse"
            data-testid="codirector-collapse-button"
            onClick={() => collapseToPopup()}
          >
            <IconCollapse />
          </IconButton>
        )}
        <IconButton
          aria-label="Close Co-Director"
          title="Close"
          data-testid="codirector-close-button"
          onClick={onClose}
        >
          <IconClose />
        </IconButton>
      </div>
    </header>
  );
});
