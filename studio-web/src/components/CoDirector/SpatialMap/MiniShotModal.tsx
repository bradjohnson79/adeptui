/**
 * Scene Creator Mini shot modal — preview, inpaint mask, approve.
 */
import { useEffect, useRef, useState, type PointerEvent } from "react";
import { api } from "../../../api";
import { lightingMoodLabel, lensLabel } from "./cameraOptics";
import type { MiniResult } from "./sceneCreatorMiniApi";

export const MINI_SHOT_CAPTION =
  "Shot not looking right? Consider adjusting your cameras in the Spatial Map, save then retry.";
export const MINI_ROOM_VIEW_CAPTION =
  "Room view not looking right? Retry this view after you save the Spatial Map.";

type Props = {
  open: boolean;
  result: MiniResult | null;
  cameraLabel: string;
  generatorLabel: string;
  busy?: boolean;
  onClose: () => void;
  onInpaint: (prompt: string, maskPngBase64: string) => void;
  onApprove: () => void;
  onRevert: () => void;
};

export function MiniShotModal({
  open,
  result,
  cameraLabel,
  generatorLabel,
  busy = false,
  onClose,
  onInpaint,
  onApprove,
  onRevert,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const strokes = useRef<ImageData[]>([]);
  const drawing = useRef(false);
  const [mode, setMode] = useState<"add" | "remove">("add");
  const [prompt, setPrompt] = useState("");
  const [inpaintOpen, setInpaintOpen] = useState(false);

  useEffect(() => {
    if (!open) {
      setPrompt("");
      setInpaintOpen(false);
      setMode("add");
      strokes.current = [];
    }
  }, [open, result?.id, result?.revision]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onClose, open]);

  if (!open || !result) return null;

  const approved = Boolean(result.approved || result.inLibrary);
  const canInpaint = Boolean(result.assetId) && !busy && !approved;
  const canApprove = Boolean(result.assetId) && !busy && !approved;
  const canRevert = Boolean((result.revisionHistory || []).length) && !busy;

  const syncCanvas = () => {
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!canvas || !img) return;
    canvas.width = img.clientWidth || img.naturalWidth || 640;
    canvas.height = img.clientHeight || img.naturalHeight || 360;
  };

  const paint = (clientX: number, clientY: number) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.fillStyle = mode === "add" ? "rgba(255, 80, 80, 0.45)" : "rgba(0,0,0,1)";
    ctx.globalCompositeOperation = mode === "add" ? "source-over" : "destination-out";
    ctx.beginPath();
    ctx.arc(clientX - rect.left, clientY - rect.top, 14, 0, Math.PI * 2);
    ctx.fill();
  };

  const beginStroke = (e: PointerEvent<HTMLCanvasElement>) => {
    if (!inpaintOpen) return;
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (canvas && ctx) {
      strokes.current.push(ctx.getImageData(0, 0, canvas.width, canvas.height));
    }
    drawing.current = true;
    paint(e.clientX, e.clientY);
  };

  const exportMask = (): string => {
    const canvas = canvasRef.current;
    if (!canvas) return "";
    const src = canvas.getContext("2d");
    if (!src) return "";
    const raw = src.getImageData(0, 0, canvas.width, canvas.height);
    const out = document.createElement("canvas");
    out.width = canvas.width;
    out.height = canvas.height;
    const dst = out.getContext("2d");
    if (!dst) return "";
    const data = dst.createImageData(canvas.width, canvas.height);
    for (let i = 0; i < raw.data.length; i += 4) {
      const on = raw.data[i + 3] > 8;
      data.data[i] = on ? 255 : 0;
      data.data[i + 1] = on ? 255 : 0;
      data.data[i + 2] = on ? 255 : 0;
      data.data[i + 3] = 255;
    }
    dst.putImageData(data, 0, 0);
    return out.toDataURL("image/png");
  };

  const distance =
    result.distanceMeters == null || Number.isNaN(Number(result.distanceMeters))
      ? "—"
      : `${result.distanceMeters} m`;

  return (
    <div
      className="ds-dialog-backdrop"
      role="presentation"
      data-testid="mini-shot-modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && !busy) onClose();
      }}
    >
      <div
        className="ds-dialog"
        role="dialog"
        aria-modal="true"
        aria-label={`${cameraLabel} shot`}
        data-testid="mini-shot-modal"
      >
        <h2 className="ds-dialog__title">
          {cameraLabel} · Variation {result.variation}
        </h2>
        <div className="ds-dialog__body">
          <div className="spatial-map__mini-modal-figure">
            {result.assetId ? (
              <img
                ref={imgRef}
                src={api.assetUrl(result.assetId)}
                alt={`${cameraLabel} ${result.variation}`}
                onLoad={syncCanvas}
              />
            ) : (
              <p>This shot is not ready yet.</p>
            )}
            {inpaintOpen ? (
              <canvas
                ref={canvasRef}
                className="spatial-map__mini-mask"
                data-testid="mini-shot-mask"
                onPointerDown={beginStroke}
                onPointerMove={(e) => {
                  if (drawing.current) paint(e.clientX, e.clientY);
                }}
                onPointerUp={() => {
                  drawing.current = false;
                }}
                onPointerLeave={() => {
                  drawing.current = false;
                }}
              />
            ) : null}
          </div>
          <p className="spatial-map__mini-caption" data-testid="mini-shot-caption">
            {result.shotKind === "world_view" ? MINI_ROOM_VIEW_CAPTION : MINI_SHOT_CAPTION}
          </p>
          <dl className="spatial-map__mini-facts" data-testid="mini-shot-facts">
            <span>{result.shotKind === "world_view" ? "Room view" : "Camera"} {cameraLabel}</span>
            <span>Direction {result.orientation || "—"}</span>
            <span>Shot size {result.shotSize || "auto"}</span>
            <span>Lens {lensLabel(result.lens)}</span>
            <span>Lighting {lightingMoodLabel(result.lightingMood)}</span>
            <span>Subject {result.primarySubjectName || result.primarySubject || "—"}</span>
            <span>Distance {distance}</span>
            <span>Generator {generatorLabel}</span>
            <span>Revision {result.revision ?? 0}</span>
          </dl>
          {inpaintOpen ? (
            <div className="spatial-map__mini-inpaint" data-testid="mini-inpaint-panel">
              <div className="spatial-map__mini-inpaint-tools">
                <button type="button" className="ui-btn ui-btn--secondary" onClick={() => setMode("add")} aria-pressed={mode === "add"}>
                  Add mask
                </button>
                <button type="button" className="ui-btn ui-btn--secondary" onClick={() => setMode("remove")} aria-pressed={mode === "remove"}>
                  Remove mask
                </button>
                <button
                  type="button"
                  className="ui-btn ui-btn--secondary"
                  onClick={() => {
                    const canvas = canvasRef.current;
                    const prev = strokes.current.pop();
                    const ctx = canvas?.getContext("2d");
                    if (canvas && ctx && prev) ctx.putImageData(prev, 0, 0);
                  }}
                  data-testid="mini-mask-undo"
                >
                  Undo mask
                </button>
                {canRevert ? (
                  <button type="button" className="ui-btn ui-btn--secondary" onClick={onRevert} data-testid="mini-revision-revert">
                    Revert image
                  </button>
                ) : null}
              </div>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Describe the correction"
                data-testid="mini-inpaint-prompt"
                aria-label="Inpaint correction"
              />
              <button
                type="button"
                className="ui-btn ui-btn--primary"
                disabled={busy || !prompt.trim()}
                data-testid="mini-apply-inpaint"
                onClick={() => onInpaint(prompt.trim(), exportMask())}
              >
                Apply Inpaint
              </button>
            </div>
          ) : null}
        </div>
        <div className="ds-dialog__actions">
          <button type="button" className="ui-btn ui-btn--secondary" disabled={busy} onClick={onClose}>
            Close
          </button>
          <button
            type="button"
            className="ui-btn ui-btn--secondary"
            disabled={!canInpaint}
            data-testid="mini-inpaint"
            onClick={() => setInpaintOpen(true)}
          >
            Inpaint / Correct
          </button>
          <button
            type="button"
            className="ui-btn ui-btn--primary"
            disabled={!canApprove}
            data-testid="mini-approve"
            onClick={onApprove}
          >
            {approved ? "Approved" : "Approve"}
          </button>
        </div>
      </div>
    </div>
  );
}
