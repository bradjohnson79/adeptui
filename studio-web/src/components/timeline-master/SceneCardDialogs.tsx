import { useState } from "react";
import { createPortal } from "react-dom";
import { SCENE_NAME_MAX, normalizeSceneName } from "../../sceneLifecycle";
import { useTimelineEditorModal } from "./useTimelineEditorModal";

export function SceneRenameDialog({
  currentName,
  busy,
  error,
  onCancel,
  onConfirm,
}: {
  currentName: string;
  busy: boolean;
  error?: string | null;
  onCancel: () => void;
  onConfirm: (name: string) => void;
}) {
  const [value, setValue] = useState(currentName);
  const { dialogRef, stopHotkeys } = useTimelineEditorModal(true, onCancel, "input");
  const parsed = normalizeSceneName(value);
  const canSave = parsed.ok && !busy;

  return createPortal(
    <div className="codirector-modal-backdrop" role="presentation" onClick={onCancel} onKeyDown={stopHotkeys}>
      <div
        ref={dialogRef}
        className="codirector-modal card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="scene-rename-title"
        data-testid="scene-rename-dialog"
        onClick={(event) => event.stopPropagation()}
        onKeyDown={(event) => {
          stopHotkeys(event);
          if (event.key === "Enter") {
            event.preventDefault();
            if (canSave) onConfirm(parsed.name);
          }
        }}
      >
        <div className="codirector-modal-head">
          <h2 id="scene-rename-title">Rename Scene</h2>
        </div>
        <label className="field">
          <span className="sr-only">Scene name</span>
          <input
            data-testid="scene-rename-input"
            value={value}
            maxLength={SCENE_NAME_MAX}
            disabled={busy}
            onChange={(event) => setValue(event.target.value)}
          />
        </label>
        {error ? (
          <p className="scene-meta" data-testid="scene-rename-error">
            {error}
          </p>
        ) : null}
        <div className="codirector-modal-actions">
          <button type="button" data-testid="scene-rename-cancel" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
          <button
            type="button"
            className="primary"
            data-testid="scene-rename-confirm"
            disabled={!canSave}
            onClick={() => {
              if (parsed.ok) onConfirm(parsed.name);
            }}
          >
            {busy ? "Renaming…" : "Rename"}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

export function SceneRemoveDialog({
  sceneName,
  busy,
  working,
  error,
  onCancel,
  onConfirm,
}: {
  sceneName: string;
  busy: boolean;
  working?: boolean;
  error?: string | null;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const { dialogRef, stopHotkeys } = useTimelineEditorModal(true, onCancel, "[data-testid='scene-remove-cancel']");

  return createPortal(
    <div className="codirector-modal-backdrop" role="presentation" onClick={onCancel} onKeyDown={stopHotkeys}>
      <div
        ref={dialogRef}
        className="codirector-modal card"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="scene-remove-title"
        aria-describedby="scene-remove-copy"
        data-testid="scene-remove-dialog"
        onClick={(event) => event.stopPropagation()}
        onKeyDown={stopHotkeys}
      >
        <div className="codirector-modal-head">
          <h2 id="scene-remove-title">Remove scene?</h2>
        </div>
        <p id="scene-remove-copy" className="scene-meta">
          “{sceneName}” and its Timeline scene data will be removed from this project.
          Shared Library assets stay in the project. This cannot be undone.
          {working ? " Generation still running on this scene will be stopped." : ""}
        </p>
        {error ? (
          <p className="scene-meta" data-testid="scene-remove-error">
            {error}
          </p>
        ) : null}
        <div className="codirector-modal-actions">
          <button type="button" data-testid="scene-remove-cancel" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
          <button
            type="button"
            className="danger"
            data-testid="scene-remove-confirm"
            disabled={busy}
            onClick={onConfirm}
          >
            {busy ? "Removing…" : "Remove Scene"}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
