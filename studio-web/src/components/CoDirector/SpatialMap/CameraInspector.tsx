/**
 * CameraInspector — compact controls for a selected camera.
 */
import { useEffect, useState } from "react";
import { rotateOrientation } from "./gridGeometry";
import type { SpatialCamera } from "./types";

function normalizeFovPreset(value: string | null | undefined): "narrow" | "medium" | "wide" {
  const v = String(value || "medium").trim().toLowerCase();
  return v === "narrow" || v === "wide" ? v : "medium";
}

type Props = {
  camera: SpatialCamera;
  onRotate: (orientation: string) => void;
  onFovChange: (fovPreset: string) => void;
  onMove: () => void;
  onRemove: () => void;
};

export function CameraInspector({ camera, onRotate, onFovChange, onMove, onRemove }: Props) {
  const orientation = camera.orientation || "N";
  const savedFov = normalizeFovPreset(camera.fovPreset);
  const [pendingFov, setPendingFov] = useState<"narrow" | "medium" | "wide" | null>(null);
  const fov = pendingFov || savedFov;
  const label = camera.cameraSlot >= 0 ? `C${camera.cameraSlot + 1}` : camera.label;

  useEffect(() => {
    setPendingFov(null);
  }, [camera.id]);

  useEffect(() => {
    if (pendingFov && pendingFov === savedFov) setPendingFov(null);
  }, [pendingFov, savedFov]);

  return (
    <div className="spatial-map__camera-inspector" data-testid="camera-inspector">
      <p className="spatial-map__camera-inspector-title">{label}</p>
      <div className="spatial-map__camera-inspector-row">
        <span className="spatial-map__camera-inspector-label">Direction</span>
        <span className="spatial-map__camera-inspector-value" data-testid="camera-inspector-direction">
          {orientation}
        </span>
        <button
          type="button"
          className="spatial-map__camera-inspector-btn"
          aria-label={`Rotate ${label} left`}
          onClick={() => onRotate(rotateOrientation(orientation, -1))}
          data-testid="camera-rotate-left"
        >
          ↺
        </button>
        <button
          type="button"
          className="spatial-map__camera-inspector-btn"
          aria-label={`Rotate ${label} right`}
          onClick={() => onRotate(rotateOrientation(orientation, 1))}
          data-testid="camera-rotate-right"
        >
          ↻
        </button>
      </div>
      <div className="spatial-map__camera-inspector-row">
        <span className="spatial-map__camera-inspector-label">Field of View</span>
        {["narrow", "medium", "wide"].map((preset) => (
          <button
            key={preset}
            type="button"
            className={`spatial-map__camera-inspector-btn spatial-map__fov-btn${fov === preset ? " is-active" : ""}`}
            aria-label={`Set ${label} FOV to ${preset}`}
            aria-pressed={fov === preset}
            onClick={() => {
              setPendingFov(preset as "narrow" | "medium" | "wide");
              onFovChange(preset);
            }}
            data-testid={`camera-fov-${preset}`}
          >
            {preset[0].toUpperCase() + preset.slice(1)}
          </button>
        ))}
      </div>
      <div className="spatial-map__camera-inspector-row">
        <button
          type="button"
          className="spatial-map__camera-inspector-btn"
          aria-label={`Move ${label}`}
          onClick={onMove}
          data-testid="camera-move"
        >
          Move
        </button>
        <button
          type="button"
          className="spatial-map__camera-inspector-btn spatial-map__camera-inspector-btn--danger"
          aria-label={`Remove ${label}`}
          onClick={onRemove}
          data-testid="camera-remove"
        >
          Remove
        </button>
      </div>
    </div>
  );
}
