import { useCallback, useEffect, useRef, useState } from "react";
import { SplitPane } from "../ui";
import { CoDirectorHeader } from "./CoDirectorHeader";
import { CoDirectorConversation } from "./CoDirectorConversation";
import { CoDirectorComposer } from "./CoDirectorComposer";
import { CoDirectorOverflowMenu } from "./CoDirectorOverflowMenu";
import { CoDirectorAssetPicker } from "./CoDirectorAssetPicker";
import { CoDirectorNavDrawer, type ContentTab } from "./CoDirectorNavDrawer";
import { CoDirectorProjectContent } from "./CoDirectorProjectContent";
import { CoDirectorStageStrip } from "./CoDirectorStageStrip";
import { CoDirectorSpecialistStrip } from "./CoDirectorSpecialistStrip";
import { useCoDirectorSession } from "./CoDirectorSession";
import { isConnectedLike } from "./runtimeState";
import {
  CODIRECTOR_SPLIT_STORAGE_KEY,
  LAYOUT_PRESET_RATIOS,
  loadLayoutPreset,
  saveLayoutPreset,
  type CoDirectorLayoutPreset,
} from "./layoutPresets";
import {
  WorkspaceFullscreenBanner,
  WorkspaceFullscreenControls,
  useWorkspaceFullscreen,
} from "../../workspace/fullscreen";
import type { CoDirectorDisplayMode } from "./types";
import "./codirector-cinematic.css";

const CONTENT_TAB_STORAGE_KEY = "adept_codirector_content_tab";

function normalizeContentTab(value: string | null | undefined): ContentTab {
  if (value === "overview") return "wiki";
  if (
    value === "wiki" ||
    value === "notes" ||
    value === "casting" ||
    value === "library" ||
    value === "plans" ||
    value === "bible" ||
    value === "approvals" ||
    value === "jobs" ||
    value === "vision" ||
    value === "pitch" ||
    value === "scriptwriter" ||
    value === "development" ||
    value === "production" ||
    value === "story" ||
    value === "script" ||
    value === "characters" ||
    value === "prop_creator" ||
    value === "spatial_map" ||
    value === "scene_creator"
  ) {
    return value as ContentTab;
  }
  return "wiki";
}

function loadContentTab(): ContentTab {
  try {
    return normalizeContentTab(localStorage.getItem(CONTENT_TAB_STORAGE_KEY));
  } catch {
    return "wiki";
  }
}

function persistContentTab(tab: ContentTab) {
  try {
    localStorage.setItem(CONTENT_TAB_STORAGE_KEY, normalizeContentTab(tab));
  } catch {
    /* ignore */
  }
}

export function CoDirectorShell({
  mode,
  onClose,
}: {
  mode: CoDirectorDisplayMode;
  onClose: () => void;
  /** retained for API compatibility — context panel replaced by Project Content */
  showContextPanel?: boolean;
}) {
  const {
    contextPanelOpen,
    setContextPanelOpen,
    expandToFullScreen,
    runtimeState,
    runtimeChip,
    productionCapable,
    selectProject,
    createProject,
    resumeSuggestedProject,
    lastBoundProjectSuggestion,
    showReconnectAction,
    reconnect,
    uiContext,
    setActiveContentTab,
  } = useCoDirectorSession();
  const [navOpen, setNavOpen] = useState(false);
  const [contentTabState, setContentTabState] = useState<ContentTab>(() => loadContentTab());
  const [layoutPreset, setLayoutPreset] = useState<CoDirectorLayoutPreset>(() => loadLayoutPreset());
  const [primarySizeRequest, setPrimarySizeRequest] = useState<{ size: number; token: number } | null>(
    null,
  );
  const menuBtnRef = useRef<HTMLButtonElement>(null);
  const workspaceRef = useRef<HTMLDivElement>(null);
  const sizeRequestToken = useRef(0);
  const initializedContentTabRef = useRef(false);
  const viewportMode = mode === "fullscreen" ? "EXPANDED" : "STANDARD";
  const workspaceFs = useWorkspaceFullscreen({
    workspaceId: "codirector",
    viewMode: viewportMode,
    onRestoreViewMode: (restore) => {
      if (restore === "EXPANDED" && mode !== "fullscreen") expandToFullScreen();
      if (restore === "STANDARD" && mode === "fullscreen") {
        /* keep expanded route if user was already in fullscreen route; true FS exit only */
      }
    },
  });

  const showContent = mode === "fullscreen" && contextPanelOpen;
  const ready = isConnectedLike(runtimeState) && runtimeState === "Connected";
  const showSpecialistStrip =
    mode === "fullscreen" && Boolean(uiContext.selectedCharacterIds?.[0]);

  const setContentTab = useCallback((tab: ContentTab) => {
    const normalized = normalizeContentTab(tab);
    setContentTabState(normalized);
    persistContentTab(normalized);
  }, []);

  useEffect(() => {
    if (!initializedContentTabRef.current) {
      initializedContentTabRef.current = true;
      setContentTab("wiki");
    }
  }, [setContentTab]);

  useEffect(() => {
    setContentTab("wiki");
  }, [uiContext.projectId, setContentTab]);

  const contentTab = contentTabState;

  // Push the active Project Content tab into the Co-Director session as a
  // contextual pillar hint (story/script/notes/wiki/...). This is a HINT only —
  // Co-Director still uses its own judgment. Sent to the backend in the chat
  // request body and surfaced in the session-context contract.
  useEffect(() => {
    setActiveContentTab(contentTab);
  }, [contentTab, setActiveContentTab]);

  const applyLayoutPreset = useCallback(
    (preset: CoDirectorLayoutPreset) => {
      const apply = () => {
        const width = workspaceRef.current?.getBoundingClientRect().width ?? window.innerWidth * 0.9;
        const usable = Math.max(560, width - 6);
        const raw = Math.round(usable * LAYOUT_PRESET_RATIOS[preset]);
        const size = Math.min(Math.max(raw, 280), Math.max(280, usable - 280));
        sizeRequestToken.current += 1;
        setPrimarySizeRequest({ size, token: sizeRequestToken.current });
        setLayoutPreset(preset);
        saveLayoutPreset(preset);
        try {
          localStorage.setItem(CODIRECTOR_SPLIT_STORAGE_KEY, String(size));
        } catch {
          /* ignore */
        }
      };
      if (!contextPanelOpen) setContextPanelOpen(true);
      requestAnimationFrame(() => requestAnimationFrame(apply));
    },
    [contextPanelOpen, setContextPanelOpen],
  );

  const chatPane = (
    <div className="codirector-workspace-chat">
      <div className="codirector-main" style={{ flex: 1, minHeight: 0 }}>
        <CoDirectorConversation />
        {/* Progressive disclosure: StageStrip returns null when no active plan stage */}
        <CoDirectorStageStrip
          onOpenProduction={() => {
            setContentTab("production");
            setContextPanelOpen(true);
          }}
        />
        {showSpecialistStrip ? <CoDirectorSpecialistStrip /> : null}
        <CoDirectorComposer />
      </div>
    </div>
  );

  return (
    <div
      ref={(node) => {
        workspaceFs.containerRef.current = node;
        workspaceRef.current = node;
      }}
      className={`codirector-shell mode-${mode} cinematic`}
      data-testid={mode === "fullscreen" ? "codirector-fullscreen-shell" : "codirector-shell"}
      data-mode={mode}
      data-runtime-state={runtimeState}
      data-layout-preset={mode === "fullscreen" ? layoutPreset : undefined}
    >
      <WorkspaceFullscreenBanner visible={workspaceFs.showBanner} />
      <CoDirectorHeader
        ref={menuBtnRef}
        mode={mode}
        onClose={onClose}
        onOpenNav={() => setNavOpen(true)}
        ready={ready}
        runtimeChip={runtimeChip}
        runtimeState={runtimeState}
        layoutPreset={layoutPreset}
        onLayoutPreset={mode === "fullscreen" ? applyLayoutPreset : undefined}
        fullscreenControls={
          <WorkspaceFullscreenControls fs={workspaceFs} showExpand={false} />
        }
      />
      {!productionCapable && (
        <div className="codirector-no-project-banner" data-testid="codirector-no-project-banner">
          <span>No Project Selected — general chat only. Production tools are disabled.</span>
          <span className="codirector-no-project-actions">
            <button type="button" data-testid="codirector-select-project" onClick={selectProject}>
              Select Project
            </button>
            <button type="button" data-testid="codirector-create-project" onClick={createProject}>
              Create Project
            </button>
            {lastBoundProjectSuggestion?.projectId ? (
              <button type="button" data-testid="codirector-resume-project" onClick={resumeSuggestedProject}>
                Resume Project
              </button>
            ) : null}
          </span>
        </div>
      )}
      {showReconnectAction && (
        <div className="codirector-reconnect-banner" data-testid="codirector-reconnect-banner">
          <span>Connection lost. Conversation preserved.</span>
          <button type="button" data-testid="codirector-reconnect" onClick={() => void reconnect()}>
            Reconnect
          </button>
        </div>
      )}
      <CoDirectorOverflowMenu />
      <CoDirectorNavDrawer
        open={navOpen}
        onClose={() => setNavOpen(false)}
        returnFocusRef={menuBtnRef}
        mode={mode}
        expandToFullScreen={expandToFullScreen}
        onSelectContent={(tab) => {
          setContentTab(tab);
          setContextPanelOpen(true);
        }}
      />

      {mode === "popup" ? (
        <div className="codirector-body">
          <div className="codirector-main">
            {/* Progressive disclosure: compact default = conversation + composer only */}
            <CoDirectorConversation compactWelcome />
            <CoDirectorComposer />
          </div>
        </div>
      ) : (
        <div
          ref={workspaceRef}
          className={`codirector-workspace ${showContent ? "" : "content-collapsed"}`}
          data-testid="codirector-workspace"
        >
          <SplitPane
            className="codirector-split"
            storageKey={CODIRECTOR_SPLIT_STORAGE_KEY}
            initialPrimarySize={Math.round(
              (typeof window !== "undefined" ? window.innerWidth * 0.85 : 1200) *
                LAYOUT_PRESET_RATIOS[layoutPreset],
            )}
            minPrimary={280}
            minSecondary={280}
            secondaryCollapsed={!showContent}
            primarySizeRequest={primarySizeRequest}
            primary={chatPane}
            secondary={<CoDirectorProjectContent tab={contentTab} onTabChange={setContentTab} onGoTab={uiContext.onGoTab} />}
          />
        </div>
      )}
      <CoDirectorAssetPicker />
    </div>
  );
}
