import { CoDirectorHeader } from "./CoDirectorHeader";
import { CoDirectorConversation } from "./CoDirectorConversation";
import { CoDirectorComposer } from "./CoDirectorComposer";
import { CoDirectorOverflowMenu } from "./CoDirectorOverflowMenu";
import { CoDirectorAssetPicker } from "./CoDirectorAssetPicker";
import { useCoDirectorSession } from "./CoDirectorSession";
import type { CoDirectorDisplayMode } from "./types";
import { UnifiedExperienceWorkspace } from "./UnifiedExperienceWorkspace";
import "./m214-unified.css";

export function CoDirectorShell({
  mode,
  onClose,
  showContextPanel = false,
}: {
  mode: CoDirectorDisplayMode;
  onClose: () => void;
  showContextPanel?: boolean;
}) {
  const { contextPanelOpen, uiContext, plan, attachments, unifiedExperienceEnabled } = useCoDirectorSession();

  return (
    <div className={`codirector-shell mode-${mode}`}>
      <CoDirectorHeader mode={mode} onClose={onClose} />
      <CoDirectorOverflowMenu />
      <div className={`codirector-body ${showContextPanel && contextPanelOpen ? "with-context" : ""}`}>
        <div className="codirector-main">
          {unifiedExperienceEnabled ? (
            <UnifiedExperienceWorkspace
              projectId={uiContext.projectId || uiContext.projectName || "default"}
              enabled={Boolean(unifiedExperienceEnabled)}
            />
          ) : (
            <>
              <CoDirectorConversation compactWelcome={mode === "popup"} />
              <CoDirectorComposer />
            </>
          )}
        </div>
        {showContextPanel && contextPanelOpen && (
          <aside className="codirector-context-panel" aria-label="Co-Director context">
            <p className="eyebrow">Context</p>
            <dl className="codirector-context-list">
              <div>
                <dt>Project</dt>
                <dd>{uiContext.projectName || "—"}</dd>
              </div>
              <div>
                <dt>Scene</dt>
                <dd>{uiContext.sceneName || "—"}</dd>
              </div>
              <div>
                <dt>Workspace</dt>
                <dd>{uiContext.workspaceId || "—"}</dd>
              </div>
              <div>
                <dt>Attachments</dt>
                <dd>{attachments.length}</dd>
              </div>
              <div>
                <dt>Active plan</dt>
                <dd>{plan?.title || "None"}</dd>
              </div>
            </dl>
          </aside>
        )}
      </div>
      <CoDirectorAssetPicker />
    </div>
  );
}
