/**
 * Scene Creator Cinematographer — four cameras, structured commands, preview/lock/final.
 */
import { api } from "../../../../api";
import type { useSceneCreator } from "../useSceneCreator";
import {
  CAMERA_OPERATIONS,
  canLockCamera,
  lockIsValid,
  previewIsStale,
  type SceneCameraRecord,
} from "./cameraCommandEngine";

type Props = { sc: ReturnType<typeof useSceneCreator> };

function cameraLabel(record: SceneCameraRecord): string {
  return record.label || `Camera ${record.cameraSlot + 1}`;
}

function statusLine(record: SceneCameraRecord): string {
  const lin = record.lineage || {};
  if (lockIsValid(record)) {
    if (!lin.previewAssetId) return "Locked — preview unavailable";
    return "Locked";
  }
  if (lin.previewStatus === "generating") return "Preview in progress";
  if (lin.previewStatus === "failed") return lin.previewError || "Preview failed";
  if (previewIsStale(record) && lin.previewStatus === "stale") return "Preview out of date";
  if (lin.previewStatus === "ready") return "Preview ready";
  return "No preview yet";
}

export function CinematographerPanel({ sc }: Props) {
  const pack = sc.cinematographer;
  const cameras = pack?.cameras || [];
  const selected = cameras.find((c) => c.cameraId === sc.selectedCameraId) || cameras[0] || null;
  const chars = sc.workspace?.characters || [];
  const props = sc.workspace?.props || [];

  return (
    <section className="cine-panel" data-testid="scene-creator-cinematographer">
      <p className="scene-creator-core__label">Cinematographer</p>
      <div className="cine-monitor" data-testid="cine-monitor-grid">
        {[0, 1, 2, 3].map((slot) => {
          const rec = cameras.find((c) => c.cameraSlot === slot);
          if (!rec || !rec.enabled) {
            return (
              <div key={slot} className="cine-tile is-off">
                <span>Camera {slot + 1}</span>
                <span className="muted">Off</span>
              </div>
            );
          }
          const selectedTile = rec.cameraId === selected?.cameraId;
          const previewId = rec.lineage?.previewAssetId;
          return (
            <button
              key={rec.cameraId}
              type="button"
              className={selectedTile ? "cine-tile is-on" : "cine-tile"}
              data-testid={`cine-tile-c${slot + 1}`}
              onClick={() => sc.selectCinematographerCamera(rec.cameraId)}
            >
              <span>
                Camera {slot + 1}
                {lockIsValid(rec) ? " · Locked" : ""}
              </span>
              {previewId ? (
                <img src={api.assetUrl(previewId)} alt={`Camera ${slot + 1} preview`} />
              ) : (
                <span className="muted">{statusLine(rec)}</span>
              )}
              <span className="muted">
                {(rec.current.shotType || "medium").replace(/_/g, " ")}
                {rec.current.targetEntityId ? ` · ${rec.current.targetEntityType || "target"}` : ""}
              </span>
            </button>
          );
        })}
      </div>

      <div className="scene-creator-core__row cine-command-row" data-testid="cine-command-row">
        <select
          data-testid="cine-camera-select"
          value={selected?.cameraId || ""}
          onChange={(e) => sc.selectCinematographerCamera(e.target.value)}
        >
          {cameras.filter((c) => c.enabled).map((cam) => (
            <option key={cam.cameraId} value={cam.cameraId}>
              {cameraLabel(cam)}
            </option>
          ))}
        </select>
        <select
          data-testid="cine-shot-select"
          value={sc.cineOperation}
          onChange={(e) => sc.setCineOperation(e.target.value)}
        >
          {CAMERA_OPERATIONS.map((op) => (
            <option key={op.id} value={op.id}>
              {op.label}
            </option>
          ))}
        </select>
        <select
          data-testid="cine-character-select"
          value={sc.cineCharacterId}
          onChange={(e) => sc.setCineCharacterId(e.target.value)}
        >
          <option value="">Skip</option>
          {chars.map((c, index) => {
            const slot = (c.slot_index != null && c.slot_index >= 0 ? c.slot_index : index) + 1;
            return (
              <option key={c.character_id} value={c.character_id}>
                Character {slot} — {c.name}
              </option>
            );
          })}
        </select>
        <select
          data-testid="cine-prop-select"
          value={sc.cinePropId}
          onChange={(e) => sc.setCinePropId(e.target.value)}
        >
          <option value="">Skip</option>
          {props.map((p, index) => {
            if (!p.prop_id) return null;
            const slot = (p.slot_index != null && p.slot_index >= 0 ? p.slot_index : index) + 1;
            return (
              <option key={p.prop_id} value={p.prop_id}>
                Prop {slot} — {p.display_label}
              </option>
            );
          })}
        </select>
        <button
          type="button"
          className="primary"
          data-testid="cine-enter"
          disabled={!selected || sc.busy}
          onClick={() => void sc.enterCameraCommand()}
        >
          Enter
        </button>
      </div>

      <textarea
        className="scene-creator-core__prompt"
        data-testid="cine-instruction"
        value={selected ? sc.cineInstruction : ""}
        onChange={(e) => sc.setCineInstruction(e.target.value)}
        onBlur={() => void sc.saveCineDelta()}
        placeholder="Camera instruction appears here. You can add a note without changing the camera setup."
      />

      {selected ? (
        <p className="muted" data-testid="cine-state-line">
          {statusLine(selected)} · v{selected.cameraStateVersion}
          {selected.current.physicalStepOffset?.forwardBack
            ? ` · ${selected.current.physicalStepOffset.forwardBack} step forward/back`
            : ""}
          {selected.current.opticalZoomStep
            ? ` · zoom ${selected.current.opticalZoomStep > 0 ? "+" : ""}${selected.current.opticalZoomStep}`
            : ""}
        </p>
      ) : (
        <p className="muted">Turn on cameras in Spatial Map to use Cinematographer.</p>
      )}

      <div className="scene-creator-core__row">
        <button type="button" className="ghost" data-testid="cine-undo" disabled={!selected || sc.busy} onClick={() => void sc.undoCamera()}>
          Undo Camera Step
        </button>
        <button type="button" className="ghost" data-testid="cine-reset" disabled={!selected || sc.busy} onClick={() => void sc.resetCamera()}>
          Reset Camera
        </button>
        <button
          type="button"
          className="ghost"
          data-testid="cine-preview"
          disabled={!selected || sc.busy || !sc.intent.trim() || (!sc.localEnabled && (!sc.apiEnabled || !sc.apiModel))}
          onClick={() => void sc.previewCamera()}
        >
          Generate Low-Res Preview
        </button>
        <button
          type="button"
          className="ghost"
          data-testid="cine-lock"
          disabled={!selected || sc.busy || !canLockCamera(selected)}
          onClick={() => void sc.lockCamera()}
        >
          Approve / Lock Camera
        </button>
        <button
          type="button"
          className="primary"
          data-testid="scene-creator-generate"
          disabled={!selected || sc.busy || !lockIsValid(selected) || Boolean(sc.approved)}
          onClick={() => void sc.finalRender()}
        >
          {sc.generating ? "Rendering…" : "Final Quality Render"}
        </button>
      </div>
    </section>
  );
}
