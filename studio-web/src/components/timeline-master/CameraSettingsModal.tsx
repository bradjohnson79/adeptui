import { useEffect, useMemo, useState } from "react";
import { api, type DirectorTimelineCameraCatalog } from "../../api";
import {
  CAMERA_FOCUS_ENVIRONMENT_ID,
  CAMERA_LENS_IDS,
  CAMERA_LENS_LABELS,
  CAMERA_SHOT_IDS,
  CAMERA_SHOT_LABELS,
  LIGHTING_PRESET_IDS,
  LIGHTING_PRESET_LABELS,
} from "../../cinematography";
import type { CameraClip } from "../DirectorTracks";
import { TimeStepperField } from "./TimeStepperField";
import { useTimelineEditorModal } from "./useTimelineEditorModal";

type FocusOption = { id: string; name: string };

type Draft = {
  start: number;
  length: number;
  shotId: string;
  lensId: string;
  focusId: string;
  lightingId: string;
  motionId: string;
};

function resolveCatalogMotion(catalog: DirectorTimelineCameraCatalog | null, value: string | null | undefined) {
  const key = (value || "").trim().toLowerCase().replace(/-/g, "_");
  if (!key || !catalog) return null;
  return (
    catalog.motions.find((entry) => entry.id === key) ||
    catalog.motions.find((entry) => entry.aliases.some((alias) => alias.trim().toLowerCase().replace(/-/g, "_") === key)) ||
    null
  );
}

export function CameraSettingsModal({
  clip,
  projectId,
  onCancel,
  onCommit,
}: {
  clip: CameraClip;
  projectId: string;
  onCancel: () => void;
  onCommit: (patch: Partial<CameraClip>) => void | Promise<void>;
}) {
  const [draft, setDraft] = useState<Draft>(() => ({
    start: clip.start,
    length: clip.length,
    shotId: clip.shot_id || "auto",
    lensId: clip.lens_id || "auto",
    focusId: clip.focus_id || CAMERA_FOCUS_ENVIRONMENT_ID,
    lightingId: clip.lighting_id || "auto",
    motionId: clip.motion_id || clip.motion_type || "",
  }));
  const [catalog, setCatalog] = useState<DirectorTimelineCameraCatalog | null>(null);
  const [characters, setCharacters] = useState<FocusOption[]>([]);
  const [charactersUnavailable, setCharactersUnavailable] = useState(false);
  const { dialogRef, stopHotkeys } = useTimelineEditorModal(true, onCancel, "select, input, button");

  useEffect(() => {
    let alive = true;
    void api
      .directorTimelineCameraCatalog()
      .then((result) => {
        if (!alive) return;
        setCatalog(result);
      })
      .catch(() => {
        if (alive) setCatalog(null);
      });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    let alive = true;
    void api
      .listCharacterProfiles(projectId)
      .then((res) => {
        if (!alive) return;
        const items = (res.items || [])
          .map((profile: { id?: string; name?: string }) => ({
            id: String(profile.id || "").trim(),
            name: String(profile.name || "").trim(),
          }))
          .filter((row: FocusOption) => row.id && row.name);
        setCharacters(items);
        setCharactersUnavailable(false);
      })
      .catch(() => {
        if (!alive) return;
        setCharacters([]);
        setCharactersUnavailable(true);
      });
    return () => {
      alive = false;
    };
  }, [projectId]);

  const motionOptions = catalog?.motions || [];
  const focusOptions = useMemo(
    () => [{ id: CAMERA_FOCUS_ENVIRONMENT_ID, name: "Environment" }, ...characters],
    [characters],
  );

  const commit = () => {
    const motion = resolveCatalogMotion(catalog, draft.motionId);
    const focus = focusOptions.find((row) => row.id === draft.focusId);
    const focusName =
      draft.focusId === CAMERA_FOCUS_ENVIRONMENT_ID
        ? "Environment"
        : (focus?.name || clip.focus_name || "").trim() || null;
    const patch: Partial<CameraClip> = {
      start: Math.max(0, draft.start),
      length: Math.max(0.15, draft.length),
      shot_id: draft.shotId || "auto",
      lens_id: draft.lensId || "auto",
      focus_id: draft.focusId || CAMERA_FOCUS_ENVIRONMENT_ID,
      focus_name: focusName,
      lighting_id: draft.lightingId || "auto",
    };
    if (draft.motionId) {
      patch.motion_id = draft.motionId;
      patch.motion_type =
        draft.motionId === "custom"
          ? clip.motion_type || "static"
          : motion?.native_motion_type || motion?.workflow_motion_type || draft.motionId;
      patch.custom_motion_label = draft.motionId === "custom" ? clip.custom_motion_label || "" : null;
    }
    void onCommit(patch);
  };

  return (
    <div className="codirector-modal-backdrop" role="presentation" onClick={onCancel} onKeyDown={stopHotkeys}>
      <div
        ref={dialogRef}
        className="codirector-modal card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="camera-settings-title"
        data-testid="timeline-camera-settings-modal"
        onClick={(event) => event.stopPropagation()}
        onKeyDown={stopHotkeys}
      >
        <div className="codirector-modal-head">
          <h2 id="camera-settings-title">Camera Settings</h2>
        </div>
        <label className="field">
          <span>Camera Shot</span>
          <select
            data-testid="timeline-camera-shot"
            value={draft.shotId}
            onChange={(event) => setDraft((current) => ({ ...current, shotId: event.target.value }))}
          >
            {CAMERA_SHOT_IDS.map((id) => (
              <option key={id} value={id}>
                {CAMERA_SHOT_LABELS[id]}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Camera Lens</span>
          <select
            data-testid="timeline-camera-lens"
            value={draft.lensId}
            onChange={(event) => setDraft((current) => ({ ...current, lensId: event.target.value }))}
          >
            {CAMERA_LENS_IDS.map((id) => (
              <option key={id} value={id}>
                {CAMERA_LENS_LABELS[id]}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Camera Focus</span>
          <select
            data-testid="timeline-camera-focus"
            value={draft.focusId}
            onChange={(event) => setDraft((current) => ({ ...current, focusId: event.target.value }))}
          >
            <option value={CAMERA_FOCUS_ENVIRONMENT_ID}>Environment</option>
            {charactersUnavailable ? (
              <option value="" disabled>
                Characters unavailable
              </option>
            ) : (
              characters.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.name}
                </option>
              ))
            )}
          </select>
        </label>
        <label className="field">
          <span>Lighting Preset Theme</span>
          <select
            data-testid="timeline-camera-lighting"
            value={draft.lightingId}
            onChange={(event) => setDraft((current) => ({ ...current, lightingId: event.target.value }))}
          >
            {LIGHTING_PRESET_IDS.map((id) => (
              <option key={id} value={id}>
                {LIGHTING_PRESET_LABELS[id]}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Camera Movement</span>
          <select
            data-testid="timeline-camera-movement"
            value={draft.motionId}
            disabled={!catalog}
            onChange={(event) => setDraft((current) => ({ ...current, motionId: event.target.value }))}
          >
            {!catalog ? <option value={draft.motionId || ""}>Motion catalog unavailable</option> : null}
            {motionOptions.map((entry) => (
              <option key={entry.id} value={entry.id}>
                {entry.label}
              </option>
            ))}
          </select>
        </label>
        <TimeStepperField
          label="Start"
          value={draft.start}
          min={0}
          testId="timeline-camera-start"
          onChange={(start) => setDraft((current) => ({ ...current, start }))}
        />
        <TimeStepperField
          label="Length"
          value={draft.length}
          min={0.15}
          testId="timeline-camera-length"
          onChange={(length) => setDraft((current) => ({ ...current, length }))}
        />
        <div className="codirector-modal-actions">
          <button type="button" data-testid="timeline-camera-settings-cancel" onClick={onCancel}>
            Cancel
          </button>
          <button type="button" className="primary" data-testid="timeline-camera-settings-ok" onClick={commit}>
            OK
          </button>
        </div>
      </div>
    </div>
  );
}
