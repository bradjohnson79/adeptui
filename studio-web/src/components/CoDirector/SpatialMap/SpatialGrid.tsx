/**
 * SpatialGrid — 10x10 grid overlay + click-to-place.
 *
 * Cells labeled A1-J10 (column letter A-J + row number 1-10). Subtle grid lines
 * that don't obscure the image. Cell coordinate visible on hover. Markers
 * rendered for each character/prop placement. Keyboard navigable (arrow keys
 * move selection, Enter to place).
 *
 * Amendment #3 (Spatial Authority): the map is authoritative. Clicking a cell
 * does NOT mutate image state — it only sets gridRow/gridColumn on a placement.
 * Amendment #4 (Orientation): Atlas North = top edge.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  cellLabel,
  GRID_SIZE,
  SLOT_COLORS,
  type SlotColorKey,
  type SpatialCharacterPlacement,
  type SpatialPropPlacement,
} from "./types";

export type GridPlacement = {
  id: string;
  tag: string;
  colorKey: SlotColorKey;
  gridRow: number;
  gridColumn: number;
  kind: "character" | "prop";
};

type Props = {
  backgroundAssetId: string;
  imageUrl: string;
  placements: GridPlacement[];
  selectedPlacementId: string | null;
  activeSlotColorKey: SlotColorKey | null;
  occupiedMessage: string | null;
  onCellClick: (row: number, column: number) => void;
  onSelectPlacement: (placementId: string | null) => void;
};

export function SpatialGrid({
  imageUrl,
  placements,
  selectedPlacementId,
  activeSlotColorKey,
  occupiedMessage,
  onCellClick,
  onSelectPlacement,
}: Props) {
  const [cursor, setCursor] = useState<{ row: number; column: number } | null>(null);
  const gridRef = useRef<HTMLDivElement>(null);

  // Occupancy map — amendment: do NOT silently overwrite (Occupancy Law).
  const occupancy = useMemo(() => {
    const map = new Map<string, GridPlacement>();
    for (const p of placements) {
      if (p.gridRow >= 0 && p.gridColumn >= 0) {
        map.set(`${p.gridRow}:${p.gridColumn}`, p);
      }
    }
    return map;
  }, [placements]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!cursor) {
        setCursor({ row: 0, column: 0 });
        return;
      }
      let { row, column } = cursor;
      let moved = false;
      if (e.key === "ArrowRight") { column = Math.min(GRID_SIZE - 1, column + 1); moved = true; }
      if (e.key === "ArrowLeft") { column = Math.max(0, column - 1); moved = true; }
      if (e.key === "ArrowDown") { row = Math.min(GRID_SIZE - 1, row + 1); moved = true; }
      if (e.key === "ArrowUp") { row = Math.max(0, row - 1); moved = true; }
      if (moved) {
        e.preventDefault();
        setCursor({ row, column });
      }
      if (e.key === "Enter") {
        e.preventDefault();
        onCellClick(row, column);
      }
    },
    [cursor, onCellClick],
  );

  // Move focus into grid when clicked.
  useEffect(() => {
    if (selectedPlacementId === null && !cursor && gridRef.current) {
      // no-op; cursor set on first key press
    }
  }, [selectedPlacementId, cursor]);

  return (
    <div
      className="spatial-map__map-wrap"
      data-testid="spatial-map-grid"
      role="grid"
      aria-label="Spatial map grid"
      tabIndex={0}
      ref={gridRef}
      onKeyDown={handleKeyDown}
    >
      <img className="spatial-map__bg-img" src={imageUrl} alt="Atlas Shot environment reference" loading="lazy" />
      <div className="spatial-map__grid-overlay">
        {Array.from({ length: GRID_SIZE * GRID_SIZE }).map((_, idx) => {
          const row = Math.floor(idx / GRID_SIZE);
          const column = idx % GRID_SIZE;
          const key = `${row}:${column}`;
          const occupied = occupancy.get(key);
          const isCursor = cursor?.row === row && cursor?.column === column;
          const isSelectedTarget =
            selectedPlacementId && occupied?.id === selectedPlacementId;
          const canPlace = !!activeSlotColorKey && !occupied;
          return (
            <button
              type="button"
              key={key}
              className={`spatial-map__cell${occupied ? " is-occupied" : ""}${isSelectedTarget ? " is-selected-target" : ""}`}
              data-testid={`spatial-map-cell-${cellLabel(row, column)}`}
              aria-label={
                occupied
                  ? `Cell ${cellLabel(row, column)}, occupied by ${occupied.tag}`
                  : `Cell ${cellLabel(row, column)}${canPlace ? ", empty, click to place" : ", empty"}`
              }
              onClick={() => {
                if (occupied) {
                  onSelectPlacement(occupied.id);
                } else {
                  onCellClick(row, column);
                }
              }}
              onMouseEnter={() => setCursor({ row, column })}
              style={isCursor && !occupied ? { boxShadow: "inset 0 0 0 1px var(--accent, #2dd4bf)" } : undefined}
            >
              <span className="spatial-map__cell-label">{cellLabel(row, column)}</span>
              {occupied ? (
                <div className="spatial-map__marker" aria-hidden="true">
                  <div
                    className="spatial-map__marker-dot"
                    style={{ background: SLOT_COLORS[occupied.colorKey] || "#fff" }}
                  />
                  <span className="spatial-map__marker-tag">{occupied.tag}</span>
                </div>
              ) : null}
            </button>
          );
        })}
      </div>
      {occupiedMessage ? (
        <div
          style={{
            position: "absolute",
            bottom: 8,
            left: 8,
            zIndex: 4,
            background: "rgba(248, 113, 113, 0.92)",
            color: "#fff",
            padding: "0.35rem 0.55rem",
            borderRadius: "0.35rem",
            fontSize: "0.78rem",
            maxWidth: "calc(100% - 16px)",
          }}
          role="status"
        >
          {occupiedMessage}
        </div>
      ) : null}
    </div>
  );
}

/** Build a GridPlacement list from the document's character + prop placements. */
export function toGridPlacements(
  characters: SpatialCharacterPlacement[],
  props: SpatialPropPlacement[],
): GridPlacement[] {
  const cps: GridPlacement[] = characters.map((p) => ({
    id: p.id,
    tag: p.tag || p.label || "@character",
    colorKey: (p.colorKey as SlotColorKey) || "red",
    gridRow: p.gridRow,
    gridColumn: p.gridColumn,
    kind: "character",
  }));
  const pps: GridPlacement[] = props.map((p) => ({
    id: p.id,
    tag: p.tag || p.label || "#prop",
    colorKey: (p.colorKey as SlotColorKey) || "purple",
    gridRow: p.gridRow,
    gridColumn: p.gridColumn,
    kind: "prop",
  }));
  return [...cps, ...pps];
}
