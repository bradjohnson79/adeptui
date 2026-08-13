/**
 * SpatialGrid — circular/radial overlay with click-to-place.
 *
 * The grid is authoritative: clicking a ring/spoke cell sets the placement's
 * (gridRow, gridColumn) coordinate. The grid scale only changes the visual
 * radius of the rings and the size of markers; the stored coordinate never
 * drifts.
 *
 * Characters render as compact squares. Cameras render via SpatialCameraMarker +
 * SpatialCameraFovCone. Atlas North = top edge.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  cellLabel,
  cellToNormalized,
  normalizedToCell,
  normalizedToPixel,
  outerRingRadiusPx,
  pixelToNormalized,
  RING_COUNT,
  SPOKE_COUNT,
  SPOKE_LABELS,
  spokeLabel,
  type GridScale,
} from "./gridGeometry";
import { CameraFovCone } from "./CameraFovCone";
import { CameraMarker } from "./CameraMarker";
import { SLOT_COLORS } from "./types";
import type { SpatialCamera, SpatialCharacterPlacement, SpatialPropPlacement, SlotColorKey } from "./types";

export type GridPlacement = {
  id: string;
  tag: string;
  colorKey: SlotColorKey;
  gridRow: number;
  gridColumn: number;
  slotIndex: number;
  kind: "character" | "prop";
};

type Props = {
  backgroundAssetId: string;
  imageUrl: string;
  placements: GridPlacement[];
  cameras: SpatialCamera[];
  selectedPlacementId: string | null;
  selectedCameraId: string | null;
  activeSlotColorKey: SlotColorKey | null;
  occupiedMessage: string | null;
  gridScale: GridScale;
  onCellClick: (ring: number, spoke: number) => void;
  onSelectPlacement: (placementId: string | null) => void;
  onSelectCamera: (cameraId: string | null) => void;
};

export function toGridPlacements(
  characters: SpatialCharacterPlacement[],
  props: SpatialPropPlacement[],
): GridPlacement[] {
  return [
    ...characters.map((c) => ({
      id: c.id,
      tag: c.tag || c.label,
      colorKey: (c.colorKey as SlotColorKey) || "red",
      gridRow: c.gridRow,
      gridColumn: c.gridColumn,
      slotIndex: c.slotIndex,
      kind: "character" as const,
    })),
    ...props.map((p) => ({
      id: p.id,
      tag: p.tag || p.label,
      colorKey: (p.colorKey as SlotColorKey) || "purple",
      gridRow: p.gridRow,
      gridColumn: p.gridColumn,
      slotIndex: p.slotIndex,
      kind: "prop" as const,
    })),
  ];
}

export function SpatialGrid({
  imageUrl,
  placements,
  cameras,
  selectedPlacementId,
  selectedCameraId,
  activeSlotColorKey,
  occupiedMessage,
  gridScale,
  onCellClick,
  onSelectPlacement,
  onSelectCamera,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState(512);
  const [hover, setHover] = useState<{ ring: number; spoke: number } | null>(null);

  useEffect(() => {
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const cr = entry.contentRect;
        const s = Math.min(cr.width, cr.height);
        if (s > 0) setSize(s);
      }
    });
    if (containerRef.current) ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  const radius = outerRingRadiusPx(size, gridScale);
  const markerSize = Math.max(14, Math.round((size / RING_COUNT) * 0.18 * (1 + gridScale * 0.05)));
  const cameraSize = Math.round(markerSize * 0.7);

  const center = { x: size / 2, y: size / 2 };

  const rings = useMemo(() => Array.from({ length: RING_COUNT }, (_, i) => i + 1), []);
  const spokes = useMemo(() => Array.from({ length: SPOKE_COUNT }, (_, i) => i), []);

  const handleClick = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const px = e.clientX - rect.left;
      const py = e.clientY - rect.top;
      const norm = pixelToNormalized(px, py, size);
      const { ring, spoke } = normalizedToCell(norm.x, norm.z);
      onCellClick(ring, spoke);
    },
    [onCellClick, size],
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const px = e.clientX - rect.left;
      const py = e.clientY - rect.top;
      const norm = pixelToNormalized(px, py, size);
      setHover(normalizedToCell(norm.x, norm.z));
    },
    [size],
  );

  const placedPlacements = placements.filter((p) => p.gridRow >= 0 && p.gridColumn >= 0);
  const placedCameras = cameras.filter((c) => c.gridRow >= 0 && c.gridColumn >= 0 || (c.x !== 0 || c.z !== 0));

  return (
    <div className="spatial-map__grid-wrap" ref={containerRef}>
      <svg
        className="spatial-map__grid-svg"
        viewBox={`0 0 ${size} ${size}`}
        onClick={handleClick}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHover(null)}
        role="img"
        aria-label="Circular spatial map grid"
      >
        {/* Background image */}
        <image href={imageUrl} x="0" y="0" width={size} height={size} preserveAspectRatio="xMidYMid slice" />

        {/* Concentric rings */}
        {rings.map((r) => (
          <circle
            key={`ring-${r}`}
            cx={center.x}
            cy={center.y}
            r={(radius * r) / RING_COUNT}
            className="spatial-map__grid-ring"
          />
        ))}

        {/* Radial spokes */}
        {spokes.map((s) => {
          const angle = (s / SPOKE_COUNT) * Math.PI * 2 - Math.PI / 2;
          return (
            <line
              key={`spoke-${s}`}
              x1={center.x}
              y1={center.y}
              x2={center.x + radius * Math.cos(angle)}
              y2={center.y + radius * Math.sin(angle)}
              className="spatial-map__grid-spoke"
            />
          );
        })}

        {/* Hover highlight */}
        {hover ? (() => {
          const pos = cellToNormalized(hover.ring, hover.spoke);
          const px = normalizedToPixel(pos.x, pos.z, size);
          return (
            <circle
              cx={px.px}
              cy={px.py}
              r={markerSize * 0.6}
              className="spatial-map__hover-cell"
              opacity={0.35}
            />
          );
        })() : null}

        {/* Placement markers (characters + props) as compact squares */}
        {placedPlacements.map((p) => {
          const pos = cellToNormalized(p.gridRow, p.gridColumn);
          const px = normalizedToPixel(pos.x, pos.z, size);
          const isSelected = selectedPlacementId === p.id;
          return (
            <g
              key={p.id}
              className={`spatial-map__marker${isSelected ? " is-selected" : ""}`}
              transform={`translate(${px.px}, ${px.py})`}
              onClick={(e) => {
                e.stopPropagation();
                onSelectPlacement(isSelected ? null : p.id);
              }}
              style={{ cursor: "pointer" }}
              data-testid={`placement-marker-${p.id}`}
            >
              <rect
                x={-markerSize / 2}
                y={-markerSize / 2}
                width={markerSize}
                height={markerSize}
                rx={2}
                fill={SLOT_COLORS[p.colorKey] || "#fff"}
                stroke="rgba(255,255,255,0.85)"
                strokeWidth={2}
              />
              {isSelected ? (
                <rect
                  x={-markerSize / 2 - 3}
                  y={-markerSize / 2 - 3}
                  width={markerSize + 6}
                  height={markerSize + 6}
                  rx={4}
                  fill="none"
                  stroke="#fff"
                  strokeWidth={2}
                  strokeDasharray="4 2"
                />
              ) : null}
            </g>
          );
        })}

        {/* Camera markers and FOV cones */}
        {placedCameras.map((c) => {
          const pos = cellToNormalized(c.gridRow >= 0 ? c.gridRow : 0, c.gridColumn >= 0 ? c.gridColumn : 0);
          // If camera has x/z, use it as normalized override; otherwise fall back to cell.
          const px = normalizedToPixel(c.x || pos.x, c.z || pos.z, size);
          const isSelected = selectedCameraId === c.id;
          return (
            <g
              key={c.id}
              className={`spatial-map__camera${isSelected ? " is-selected" : ""}`}
              transform={`translate(${px.px}, ${px.py})`}
              onClick={(e) => {
                e.stopPropagation();
                onSelectCamera(isSelected ? null : c.id);
              }}
              style={{ cursor: "pointer" }}
              data-testid={`camera-marker-${c.id}`}
            >
              <CameraFovCone
                orientation={c.orientation || "N"}
                fovPreset={c.fovPreset || "medium"}
                radius={cameraSize * 3}
                selected={isSelected}
              />
              <CameraMarker size={cameraSize} label={c.cameraSlot >= 0 ? `C${c.cameraSlot + 1}` : c.label} />
            </g>
          );
        })}

        {/* Spoke labels at the outer edge */}
        {spokes.map((s) => {
          const angle = (s / SPOKE_COUNT) * Math.PI * 2 - Math.PI / 2;
          const lx = center.x + (radius + 14) * Math.cos(angle);
          const ly = center.y + (radius + 14) * Math.sin(angle);
          return (
            <text key={`label-${s}`} x={lx} y={ly} className="spatial-map__grid-label" textAnchor="middle" dominantBaseline="middle">
              {spokeLabel(s)}
            </text>
          );
        })}
      </svg>

      {occupiedMessage ? <p className="spatial-map__occupied-message">{occupiedMessage}</p> : null}
    </div>
  );
}
