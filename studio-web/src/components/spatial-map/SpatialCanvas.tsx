import { useMemo, useRef, type MouseEvent as ReactMouseEvent } from "react";
import { Button } from "../ui";
import type { SpatialMapDocument } from "../../contracts/spatialMapM411";

type PlacementKind = "character" | "prop" | "camera";

type SpatialCanvasProps = {
  document: SpatialMapDocument;
  backgroundUrl?: string | null;
  selectedId: string | null;
  placementMode: PlacementKind | null;
  onSelect: (placementId: string | null) => void;
  onPlace: (kind: PlacementKind, x: number, z: number) => void;
  onPreviewMove: (kind: PlacementKind, placementId: string, patch: { x?: number; z?: number }) => void;
  onCommitMove: (
    kind: PlacementKind,
    placementId: string,
    patch: { x?: number; z?: number; yawDegrees?: number }
  ) => void;
};

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function initialsOf(label: string) {
  const parts = label.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0] || ""}${parts[1][0] || ""}`.toUpperCase();
}

function colorFor(kind: PlacementKind) {
  if (kind === "camera") return "#2563eb";
  if (kind === "prop") return "#c45c26";
  return "#0f766e";
}

function tokenClass(kind: PlacementKind) {
  if (kind === "camera") return "avatar-shape avatar-camera";
  if (kind === "prop") return "avatar-shape avatar-square";
  return "avatar-shape avatar-circle";
}

function placeLeft(document: SpatialMapDocument, x: number) {
  const span = Math.max(0.001, document.bounds.maxX - document.bounds.minX);
  return ((x - document.bounds.minX) / span) * 100;
}

function placeTop(document: SpatialMapDocument, z: number) {
  const span = Math.max(0.001, document.bounds.maxZ - document.bounds.minZ);
  return ((document.bounds.maxZ - z) / span) * 100;
}

function canvasPoint(
  document: SpatialMapDocument,
  canvas: HTMLDivElement,
  event: MouseEvent | ReactMouseEvent<HTMLDivElement>
) {
  const rect = canvas.getBoundingClientRect();
  const xRatio = clamp((event.clientX - rect.left) / rect.width, 0, 1);
  const zRatio = clamp((event.clientY - rect.top) / rect.height, 0, 1);
  return {
    x: document.bounds.minX + xRatio * (document.bounds.maxX - document.bounds.minX),
    z: document.bounds.maxZ - zRatio * (document.bounds.maxZ - document.bounds.minZ),
  };
}

function placementGroups(document: SpatialMapDocument) {
  return [
    ...document.characters.map((item) => ({ ...item, kind: "character" as const })),
    ...document.props.map((item) => ({ ...item, kind: "prop" as const })),
    ...document.cameras.map((item) => ({ ...item, kind: "camera" as const })),
  ];
}

export function SpatialCanvas({
  document,
  backgroundUrl,
  selectedId,
  placementMode,
  onSelect,
  onPlace,
  onPreviewMove,
  onCommitMove,
}: SpatialCanvasProps) {
  const canvasRef = useRef<HTMLDivElement | null>(null);
  const dragRef = useRef<{ id: string; kind: PlacementKind } | null>(null);

  const placements = useMemo(() => placementGroups(document), [document]);
  const selected = useMemo(() => placements.find((item) => item.id === selectedId) || null, [placements, selectedId]);
  const depthBands = useMemo(
    () => [
      { label: "Background", top: 0, height: 33.33 },
      { label: "Midground", top: 33.33, height: 33.33 },
      { label: "Foreground", top: 66.66, height: 33.34 },
    ],
    []
  );

  const rotateSelected = (delta: number) => {
    if (!selected) return;
    onCommitMove(selected.kind, selected.id, { yawDegrees: selected.yawDegrees + delta });
  };

  return (
    <div className="spatial-map-canvas-shell">
      <div className="spatial-map-canvas-toolbar">
        <p className="scene-meta">
          {placementMode
            ? `Click the floor to place your ${placementMode === "camera" ? "camera" : placementMode}.`
            : "Drag to block the scene. Use the mouse wheel to turn the selected marker."}
        </p>
        {selected ? (
          <div className="spatial-map-canvas-quick-actions">
            <Button variant="compact" onClick={() => rotateSelected(-15)}>
              Turn Left
            </Button>
            <Button variant="compact" onClick={() => rotateSelected(15)}>
              Turn Right
            </Button>
          </div>
        ) : null}
      </div>

      <div
        ref={canvasRef}
        className="spatial-canvas spatial-map-canvas"
        data-testid="spatial-canvas"
        onClick={(event) => {
          const canvas = canvasRef.current;
          if (!canvas || !placementMode || dragRef.current) return;
          const point = canvasPoint(document, canvas, event);
          onPlace(placementMode, point.x, point.z);
        }}
      >
        {backgroundUrl ? <img className="spatial-bg" src={backgroundUrl} alt="" draggable={false} /> : null}

        <div className="spatial-map-canvas-grid" aria-hidden="true">
          {depthBands.map((zone) => (
            <div
              key={zone.label}
              className="spatial-map-depth-band"
              style={{ top: `${zone.top}%`, height: `${zone.height}%` }}
            >
              <span>{zone.label}</span>
            </div>
          ))}
          <div className="spatial-map-canvas-corner spatial-map-canvas-corner--window">Stage Left</div>
          <div className="spatial-map-canvas-corner spatial-map-canvas-corner--door">Stage Right</div>
        </div>

        {placements.map((item) => {
          const color = colorFor(item.kind);
          return (
            <button
              key={item.id}
              type="button"
              className={`spatial-avatar spatial-map-token${selectedId === item.id ? " selected" : ""}`}
              style={{
                left: `${placeLeft(document, item.x)}%`,
                top: `${placeTop(document, item.z)}%`,
                color,
              }}
              onClick={(event) => {
                event.stopPropagation();
                onSelect(item.id);
              }}
              onMouseDown={(event) => {
                event.stopPropagation();
                event.preventDefault();
                dragRef.current = { id: item.id, kind: item.kind };
                const onMove = (moveEvent: MouseEvent) => {
                  const canvas = canvasRef.current;
                  if (!canvas) return;
                  const point = canvasPoint(document, canvas, moveEvent);
                  onPreviewMove(item.kind, item.id, point);
                };
                const onUp = (upEvent: MouseEvent) => {
                  window.removeEventListener("mousemove", onMove);
                  window.removeEventListener("mouseup", onUp);
                  dragRef.current = null;
                  const canvas = canvasRef.current;
                  if (!canvas) return;
                  const point = canvasPoint(document, canvas, upEvent);
                  onCommitMove(item.kind, item.id, point);
                };
                window.addEventListener("mousemove", onMove);
                window.addEventListener("mouseup", onUp);
              }}
              onWheel={(event) => {
                event.preventDefault();
                event.stopPropagation();
                const delta = event.deltaY > 0 ? 15 : -15;
                onCommitMove(item.kind, item.id, { yawDegrees: item.yawDegrees + delta });
              }}
              aria-label={`${item.label} on spatial map`}
              title={`${item.label} · drag to move · wheel to turn`}
            >
              {item.kind === "camera" ? (
                <div
                  className="fov-cone"
                  style={{
                    transform: `translate(-50%, -100%) rotate(${item.yawDegrees}deg)`,
                    borderBottomColor: color,
                    ["--fov" as string]: `${Math.max(30, Math.min(80, 90 - (item.lensMm - 18)))}deg`,
                  }}
                />
              ) : null}
              <div className={tokenClass(item.kind)} style={{ borderColor: color, background: color }}>
                {initialsOf(item.label)}
              </div>
              <div
                className="facing-arrow"
                style={{
                  transform: `rotate(${item.yawDegrees}deg)`,
                  borderBottomColor: color,
                }}
              />
              <span className="spatial-map-token-label">{item.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
