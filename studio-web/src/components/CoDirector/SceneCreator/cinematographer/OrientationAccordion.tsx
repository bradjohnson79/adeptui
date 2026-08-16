/**
 * Left-sidebar 3D Camera Orientation accordion.
 * View/controller over SceneCinematographerPack — not a second camera store.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import type { useSceneCreator } from "../useSceneCreator";
import {
  formatCollapsedOrientationLine,
  formatOrientationSummary,
  lockIsValid,
  type OrientationPatch,
  type SceneCameraRecord,
} from "./cameraCommandEngine";
import { OrientationRig, type OrientationValue } from "./OrientationRig";
import {
  SNAP_PRESETS,
  clampPitch,
  clampRoll,
  clampZoom,
  getSnapPreset,
  wrapYaw,
  type AxisLocks,
} from "./orientationMath";
import {
  approvedLookBlocksFinal,
  compileRegionEditFinalPrompt,
  MODEL_GUARD_MESSAGE,
  shotWithSelectedFamily,
} from "../regionEdit/regionEdit";

type Draft = {
  yawDegrees: number;
  pitchDegrees: number;
  rollDegrees: number;
  zoom: number;
  enabled: boolean;
  targetLock: boolean;
  axisLocks: AxisLocks;
};

function readDraft(record: SceneCameraRecord): Draft {
  const pose = record.current;
  return {
    yawDegrees: pose.yawDegrees ?? 0,
    pitchDegrees: pose.pitchDegrees ?? 0,
    rollDegrees: pose.rollDegrees ?? 0,
    zoom: pose.orientation3d?.zoom ?? 1,
    enabled: pose.orientation3d?.enabled ?? false,
    targetLock: pose.orientation3d?.targetLock ?? true,
    axisLocks: { ...(pose.orientation3d?.axisLocks || {}) },
  };
}

function formatSigned(value: number, digits = 0): string {
  const rounded = Number(value.toFixed(digits));
  return rounded > 0 ? `+${rounded}` : `${rounded}`;
}

function targetValue(record: SceneCameraRecord): string {
  const pose = record.current;
  if (!pose.targetEntityId) return "";
  if (pose.targetEntityType === "prop") return `prop:${pose.targetEntityId}`;
  return `char:${pose.targetEntityId}`;
}

export function OrientationAccordion({ sc }: { sc: ReturnType<typeof useSceneCreator> }) {
  const cameras = (sc.cinematographer?.cameras || []).filter((cam) => cam.enabled);
  const selected = cameras.find((c) => c.cameraId === sc.selectedCameraId) || cameras[0] || null;
  const blocksFinal = approvedLookBlocksFinal(sc.shot);
  const liveShot = shotWithSelectedFamily(sc.shot, sc.localFamily);
  const inheritanceBlocked = Boolean(liveShot && compileRegionEditFinalPrompt(liveShot).visualInheritanceBlocked);
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<Draft>(() => (selected ? readDraft(selected) : {
    yawDegrees: 0,
    pitchDegrees: 0,
    rollDegrees: 0,
    zoom: 1,
    enabled: false,
    targetLock: true,
    axisLocks: {},
  }));
  const [snapId, setSnapId] = useState("");
  const draggingRef = useRef(false);
  const timerRef = useRef<number | null>(null);
  const pendingRef = useRef<OrientationPatch | null>(null);

  useEffect(() => {
    if (!selected || draggingRef.current) return;
    setDraft(readDraft(selected));
  }, [selected?.cameraId, selected?.cameraStateVersion, selected?.current]);

  useEffect(() => {
    return () => {
      if (timerRef.current != null) window.clearTimeout(timerRef.current);
    };
  }, []);

  const flush = useCallback(() => {
    if (timerRef.current != null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    const pending = pendingRef.current;
    pendingRef.current = null;
    if (!pending) return;
    void sc.applyOrientation({
      ...pending,
      source: draggingRef.current ? "gizmo" : pending.source || "discrete",
    });
  }, [sc]);

  const queue = useCallback(
    (patch: OrientationPatch, mode: "debounce" | "now") => {
      pendingRef.current = { ...pendingRef.current, ...patch };
      if (mode === "now") {
        flush();
        return;
      }
      if (timerRef.current != null) window.clearTimeout(timerRef.current);
      timerRef.current = window.setTimeout(flush, 120);
    },
    [flush],
  );

  if (!selected) {
    return (
      <details className="scene-creator-tool-accordion" data-testid="cine-orient-accordion">
        <summary>
          3D Camera Orientation
          <span className="muted cine-orient-collapsed-meta">Not applied</span>
        </summary>
        <p className="muted">Turn on cameras in Spatial Map to aim them here.</p>
      </details>
    );
  }

  const locked = lockIsValid(selected);
  const collapsed = formatCollapsedOrientationLine(selected);

  const onToggle = (event: React.SyntheticEvent<HTMLDetailsElement>) => {
    const nextOpen = event.currentTarget.open;
    setOpen(nextOpen);
    if (nextOpen && !draft.enabled) {
      setDraft((prev) => ({ ...prev, enabled: true }));
      void sc.applyOrientation({ enabled: true, source: "discrete" });
    }
  };

  const commitAxis = (key: "yawDegrees" | "pitchDegrees" | "rollDegrees" | "zoom", next: number) => {
    const clamped =
      key === "yawDegrees"
        ? wrapYaw(next)
        : key === "pitchDegrees"
          ? clampPitch(next)
          : key === "rollDegrees"
            ? clampRoll(next)
            : clampZoom(next);
    setDraft((prev) => ({ ...prev, [key]: clamped }));
    void sc.applyOrientation({ [key]: clamped, source: "discrete" });
  };

  const stepAxis = (key: "yawDegrees" | "pitchDegrees" | "rollDegrees" | "zoom", delta: number) => {
    if (draft.axisLocks[key === "yawDegrees" ? "yaw" : key === "pitchDegrees" ? "pitch" : key === "rollDegrees" ? "roll" : "zoom"]) {
      return;
    }
    commitAxis(key, draft[key] + delta);
  };

  const onRigChange = (value: OrientationValue) => {
    draggingRef.current = true;
    setDraft((prev) => ({ ...prev, ...value }));
    queue({ ...value, source: "gizmo" }, "debounce");
  };

  const onRigCommit = (value: OrientationValue) => {
    setDraft((prev) => ({ ...prev, ...value }));
    queue({ ...value, source: "gizmo" }, "now");
    draggingRef.current = false;
  };

  const chars = sc.workspace?.characters || [];
  const props = sc.workspace?.props || [];

  return (
    <details className="scene-creator-tool-accordion cine-orient-accordion" data-testid="cine-orient-accordion" onToggle={onToggle}>
      <summary>
        3D Camera Orientation
        <span className="muted cine-orient-collapsed-meta" data-testid="cine-orient-collapsed-line">
          {collapsed}
        </span>
      </summary>
      <div className="cine-orient-body">
        {locked ? (
          <p className="muted" data-testid="cine-orient-locked">
            Camera {(selected.cameraSlot ?? 0) + 1} · LOCKED
          </p>
        ) : null}
        <label className="scene-creator-core__label">
          Camera
          <select
            data-testid="cine-orient-camera-select"
            value={selected.cameraId}
            onChange={(e) => sc.selectCinematographerCamera(e.target.value)}
          >
            {cameras.map((cam) => (
              <option key={cam.cameraId} value={cam.cameraId}>
                C{(cam.cameraSlot ?? 0) + 1}
              </option>
            ))}
          </select>
        </label>
        <label className="scene-creator-core__label">
          Target
          <select
            data-testid="cine-orient-target-select"
            value={targetValue(selected)}
            onChange={(e) => {
              const raw = e.target.value;
              if (raw.startsWith("prop:")) {
                void sc.applyOrientation({ targetLock: true, propId: raw.slice(5), source: "discrete" });
              } else if (raw.startsWith("char:")) {
                void sc.applyOrientation({ targetLock: true, characterId: raw.slice(5), source: "discrete" });
              }
            }}
          >
            <option value="">the scene</option>
            {chars.map((c) => (
              <option key={c.character_id} value={`char:${c.character_id}`}>
                {c.name}
              </option>
            ))}
            {props.map((p) =>
              p.prop_id ? (
                <option key={p.prop_id} value={`prop:${p.prop_id}`}>
                  {p.display_label}
                </option>
              ) : null,
            )}
          </select>
        </label>
        <label className="cine-orient-check" title="Keep the camera pointed at this person or prop.">
          Target Lock
          <button
            type="button"
            className={draft.targetLock ? "ghost cine-orient-lock is-on" : "ghost cine-orient-lock"}
            data-testid="cine-orient-lock-target"
            aria-pressed={draft.targetLock}
            onClick={() => {
              const targetLock = !draft.targetLock;
              setDraft((prev) => ({ ...prev, targetLock }));
              void sc.applyOrientation({ targetLock, source: "discrete" });
            }}
          >
            {draft.targetLock ? "ON" : "OFF"}
          </button>
        </label>
        <OrientationRig
          compact
          active={open}
          yawDegrees={draft.yawDegrees}
          pitchDegrees={draft.pitchDegrees}
          rollDegrees={draft.rollDegrees}
          zoom={draft.zoom}
          targetLock={draft.targetLock}
          axisLocks={draft.axisLocks}
          onChange={onRigChange}
          onCommit={onRigCommit}
        />
        <div className="cine-orient-steppers">
          <AxisStepper
            label="Yaw"
            testId="cine-orient-yaw"
            display={`${formatSigned(draft.yawDegrees)}°`}
            disabled={Boolean(draft.axisLocks.yaw)}
            onMinus={() => stepAxis("yawDegrees", -5)}
            onPlus={() => stepAxis("yawDegrees", 5)}
            numericValue={Math.round(draft.yawDegrees * 10) / 10}
            onNumeric={(raw) => commitAxis("yawDegrees", Number(raw))}
          />
          <AxisStepper
            label="Pitch"
            testId="cine-orient-pitch"
            display={`${formatSigned(draft.pitchDegrees)}°`}
            disabled={Boolean(draft.axisLocks.pitch)}
            onMinus={() => stepAxis("pitchDegrees", -3)}
            onPlus={() => stepAxis("pitchDegrees", 3)}
            numericValue={Math.round(draft.pitchDegrees * 10) / 10}
            onNumeric={(raw) => commitAxis("pitchDegrees", Number(raw))}
          />
          <AxisStepper
            label="Roll"
            testId="cine-orient-roll"
            display={`${formatSigned(draft.rollDegrees)}°`}
            disabled={Boolean(draft.axisLocks.roll)}
            onMinus={() => stepAxis("rollDegrees", -1)}
            onPlus={() => stepAxis("rollDegrees", 1)}
            numericValue={Math.round(draft.rollDegrees * 10) / 10}
            onNumeric={(raw) => commitAxis("rollDegrees", Number(raw))}
          />
          <AxisStepper
            label="Zoom"
            testId="cine-orient-zoom"
            display={`${draft.zoom.toFixed(2)}x`}
            disabled={Boolean(draft.axisLocks.zoom)}
            onMinus={() => stepAxis("zoom", -0.05)}
            onPlus={() => stepAxis("zoom", 0.05)}
            numericValue={Math.round(draft.zoom * 100) / 100}
            onNumeric={(raw) => commitAxis("zoom", Number(raw))}
          />
        </div>
        <label className="cine-orient-snap-label" title="Jump to a familiar camera view.">
          Snap View
          <select
            data-testid="cine-orient-snap"
            value={snapId}
            onChange={(event) => {
              const id = event.target.value;
              setSnapId(id);
              const preset = getSnapPreset(id);
              if (!preset) return;
              const next = {
                yawDegrees: draft.axisLocks.yaw ? draft.yawDegrees : preset.yawDegrees,
                pitchDegrees: draft.axisLocks.pitch ? draft.pitchDegrees : preset.pitchDegrees,
                rollDegrees: draft.axisLocks.roll ? draft.rollDegrees : preset.rollDegrees,
              };
              setDraft((prev) => ({ ...prev, ...next }));
              void sc.applyOrientation({ ...next, snapId: id, source: "discrete" });
            }}
          >
            <option value="">Choose a view</option>
            {SNAP_PRESETS.map((preset) => (
              <option key={preset.id} value={preset.id}>
                {preset.label}
              </option>
            ))}
          </select>
        </label>
        <div className="scene-creator-core__row">
          <button type="button" className="ghost" disabled={sc.busy} onClick={() => void sc.undoCamera()}>
            Undo
          </button>
          <button
            type="button"
            className="ghost"
            data-testid="cine-orient-reset"
            disabled={sc.busy}
            onClick={() => void sc.resetOrientation()}
          >
            Reset
          </button>
        </div>
        {draft.enabled ? (
          <p className="muted">{formatOrientationSummary({
              yawDegrees: draft.yawDegrees,
              pitchDegrees: draft.pitchDegrees,
              rollDegrees: draft.rollDegrees,
              orientation3d: { enabled: true, targetLock: draft.targetLock, zoom: draft.zoom },
            })}</p>
        ) : null}
        <div className="scene-creator-core__row cine-orient-generate" data-testid="cine-orient-generate">
          <button
            type="button"
            className="ghost"
            data-testid="cine-orient-preview"
            disabled={!selected || sc.busy || !sc.intent.trim() || (!sc.localEnabled && (!sc.apiEnabled || !sc.apiModel))}
            onClick={() => void sc.previewCamera()}
          >
            {sc.busy || selected?.lineage?.previewStatus === "generating" ? "Generating preview…" : "Generate Low-Res Camera Preview"}
          </button>
          <button
            type="button"
            className="primary"
            data-testid="cine-orient-final"
            disabled={!selected || sc.busy || !lockIsValid(selected) || blocksFinal || inheritanceBlocked}
            onClick={() => void sc.finalRender()}
          >
            {sc.generating || sc.busy ? "Final rendering…" : "Final Quality Render"}
          </button>
        </div>
        {inheritanceBlocked ? (
          <p className="muted">
            {MODEL_GUARD_MESSAGE} Choose Z-Image or FLUX.
          </p>
        ) : null}
      </div>
    </details>
  );
}

function AxisStepper({
  label,
  testId,
  display,
  disabled,
  onMinus,
  onPlus,
  numericValue,
  onNumeric,
}: {
  label: string;
  testId: string;
  display: string;
  disabled: boolean;
  onMinus: () => void;
  onPlus: () => void;
  numericValue: number;
  onNumeric: (raw: string) => void;
}) {
  return (
    <div className="cine-orient-stepper">
      <span>{label}</span>
      <button type="button" className="ghost" disabled={disabled} onClick={onMinus} aria-label={`${label} down`}>
        −
      </button>
      <span className="cine-orient-stepper__value">{display}</span>
      <button type="button" className="ghost" disabled={disabled} onClick={onPlus} aria-label={`${label} up`}>
        +
      </button>
      <input
        type="number"
        data-testid={testId}
        key={numericValue}
        defaultValue={numericValue}
        disabled={disabled}
        onBlur={(event) => onNumeric(event.target.value)}
        aria-label={label}
      />
    </div>
  );
}
