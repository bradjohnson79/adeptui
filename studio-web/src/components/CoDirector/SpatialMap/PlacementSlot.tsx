/**
 * PlacementSlot — Character or Prop slot.
 *
 * ADD ≠ PLACE: Add binds a saved entity. Place/Move enter map-placement mode.
 * No typing. Saved dropdown is the identity mechanism.
 */
import { useState } from "react";
import { api } from "../../../api";
import { cellLabel } from "./gridGeometry";
import {
  SLOT_COLORS,
  type SavedOption,
  type SlotDef,
  type SpatialCharacterPlacement,
  type SpatialPropPlacement,
} from "./types";

type Props = {
  slot: SlotDef;
  placement: SpatialCharacterPlacement | SpatialPropPlacement | null;
  active: boolean;
  savedOptions: SavedOption[];
  placing: boolean;
  onSelect: () => void;
  onAdd: (option: SavedOption) => void;
  onPlace: () => void;
  onMove: () => void;
  onRemove: () => void;
  onUpdateMiniPrompt: (text: string) => void;
  visible?: boolean;
  onToggleVisible?: () => void;
};

export function PlacementSlot({
  slot,
  placement,
  active,
  savedOptions,
  placing,
  onSelect,
  onAdd,
  onPlace,
  onMove,
  onRemove,
  onUpdateMiniPrompt,
  visible,
  onToggleVisible,
}: Props) {
  const [expanded, setExpanded] = useState(false);
  const [miniDraft, setMiniDraft] = useState(placement?.miniPrompt || "");
  const [pickedId, setPickedId] = useState("");

  const color = SLOT_COLORS[slot.colorKey];
  const isCharacter = slot.kind === "character";
  const isAssigned = !!placement;
  const isPlaced = !!(
    placement &&
    ((typeof placement.normalizedX === "number" && typeof placement.normalizedY === "number") ||
      (placement.gridRow >= 0 && placement.gridColumn >= 0))
  );
  const location =
    isPlaced && placement!.gridRow >= 0 && placement!.gridColumn >= 0
      ? cellLabel(placement!.gridColumn, placement!.gridRow)
      : "";
  const displayName = placement?.label || placement?.tag || "";
  const picked = savedOptions.find((o) => o.id === pickedId) || null;
  const thumbUrl = placement?.assetId ? api.assetUrl(placement.assetId) : null;

  return (
    <div
      className={`spatial-map__slot-card${active ? " is-active" : ""}${placing ? " is-placing" : ""}`}
      data-testid={`spatial-map-slot-${slot.kind}-${slot.index}`}
      onClick={onSelect}
      role="button"
      tabIndex={0}
      aria-pressed={active}
      aria-current={active && isAssigned ? "true" : undefined}
      aria-label={`${slot.label}${isAssigned ? `, assigned ${displayName}` : ", empty"}${active && isAssigned ? ", active" : ""}`}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect();
        }
      }}
    >
      <div className="spatial-map__slot-head">
        {active && isAssigned ? (
          <span className="spatial-map__active-badge" data-testid={`slot-active-badge-${slot.kind}-${slot.index}`}>
            ACTIVE
          </span>
        ) : null}
        <span className="spatial-map__slot-swatch" style={{ background: color }} aria-hidden="true" />
        <span className="spatial-map__slot-label">{slot.label}</span>
      </div>

      {!isAssigned ? (
        <div className="spatial-map__slot-assign" onClick={(e) => e.stopPropagation()}>
          <select
            className="spatial-map__slot-select"
            value={pickedId}
            onChange={(e) => setPickedId(e.target.value)}
            aria-label={`Select saved ${isCharacter ? "character" : "prop"} for ${slot.label}`}
            data-testid={`${slot.kind}-select-${slot.index}`}
          >
            <option value="">{isCharacter ? "Select Saved Character" : "Select Saved Prop"}</option>
            {savedOptions.map((option) => (
              <option key={option.id} value={option.id}>
                {option.name}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="spatial-map__slot-add"
            disabled={!picked}
            title={!picked ? `Select a saved ${isCharacter ? "character" : "prop"} first` : undefined}
            onClick={() => picked && onAdd(picked)}
            aria-label={`Add ${picked?.name || (isCharacter ? "character" : "prop")} to ${slot.label}`}
            data-testid={`${slot.kind}-add-${slot.index}`}
          >
            Add
          </button>
        </div>
      ) : (
        <div className="spatial-map__slot-assigned">
          <div className="spatial-map__slot-assigned-tag">
            {thumbUrl ? (
              <img
                src={thumbUrl}
                alt=""
                style={{ width: "1.1rem", height: "1.1rem", objectFit: "cover", borderRadius: "0.2rem", verticalAlign: "middle", marginRight: "0.3rem" }}
                loading="lazy"
              />
            ) : null}
            {displayName}
          </div>
          {location ? <div className="spatial-map__slot-assigned-loc">Cell {location}</div> : null}
          <div className="spatial-map__slot-actions">
          {isAssigned && onToggleVisible ? (
            <button
              type="button"
              className="spatial-map__slot-action"
              aria-label={`Toggle visibility of ${displayName || (isCharacter ? "character" : "prop")} on ${slot.label}`}
              aria-pressed={(visible ?? placement?.visible) !== false}
              data-testid={`${slot.kind}-visible-${slot.index}`}
              onClick={(e) => {
                e.stopPropagation();
                onToggleVisible();
              }}
            >
              Visible
            </button>
          ) : null}
            {!isPlaced ? (
              <button
                type="button"
                className="spatial-map__slot-action"
                onClick={(e) => {
                  e.stopPropagation();
                  onPlace();
                }}
                aria-label={`Place ${displayName || (isCharacter ? "character" : "prop")} on ${slot.label}`}
                data-testid={`${slot.kind}-place-${slot.index}`}
              >
                Place
              </button>
            ) : (
              <button
                type="button"
                className="spatial-map__slot-action"
                onClick={(e) => {
                  e.stopPropagation();
                  onMove();
                }}
                aria-label={`Move ${displayName || (isCharacter ? "character" : "prop")} on ${slot.label}`}
                data-testid={`${slot.kind}-move-${slot.index}`}
              >
                Move
              </button>
            )}
            <button
              type="button"
              className="spatial-map__slot-action danger"
              onClick={(e) => {
                e.stopPropagation();
                if (window.confirm(`Remove ${displayName || "this placement"} from ${slot.label}? The saved ${isCharacter ? "character" : "prop"} is kept.`)) {
                  onRemove();
                }
              }}
              aria-label={`Remove ${displayName || (isCharacter ? "character" : "prop")} from ${slot.label}`}
              data-testid={`${slot.kind}-remove-${slot.index}`}
            >
              Remove
            </button>
          </div>
          <button
            type="button"
            className="spatial-map__slot-more"
            onClick={(e) => {
              e.stopPropagation();
              setExpanded((v) => {
                if (!v) setMiniDraft(placement?.miniPrompt || "");
                return !v;
              });
            }}
          >
            {expanded ? "Hide note" : "More"}
          </button>
          {expanded ? (
            <>
              <textarea
                className="spatial-map__slot-mini-input"
                value={miniDraft}
                onChange={(e) => setMiniDraft(e.target.value)}
                rows={2}
                aria-label={`Note for ${slot.label}`}
                onClick={(e) => e.stopPropagation()}
              />
              <div className="spatial-map__slot-actions">
                <button
                  type="button"
                  className="spatial-map__slot-action"
                  onClick={(e) => {
                    e.stopPropagation();
                    onUpdateMiniPrompt(miniDraft.trim());
                    setExpanded(false);
                  }}
                >
                  Save
                </button>
              </div>
            </>
          ) : null}
        </div>
      )}
    </div>
  );
}
