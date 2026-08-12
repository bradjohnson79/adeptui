/**
 * PlacementSlot — one character/prop slot card.
 *
 * Shows a color swatch + accessible label ("Character 1 (Red)"), and either the
 * assigned entity (@Name or #tag) with a compact expandable mini-prompt card,
 * or a "+ Add" button. Mini-prompts use compact expandable cards (amendment
 * #25), NOT 8 large empty textareas. Accessible labels in addition to color
 * (amendment #12, #13, #69).
 */
import { useState } from "react";
import { api } from "../../../api";
import {
  cellLabel,
  SLOT_COLORS,
  type SlotDef,
  type SpatialCharacterPlacement,
  type SpatialPropPlacement,
} from "./types";

type Props = {
  slot: SlotDef;
  placement: SpatialCharacterPlacement | SpatialPropPlacement | null;
  active: boolean;
  onSelect: () => void;
  onAdd: () => void;
  onRemove: () => void;
  onUpdateMiniPrompt: (text: string) => void;
};

export function PlacementSlot({
  slot,
  placement,
  active,
  onSelect,
  onAdd,
  onRemove,
  onUpdateMiniPrompt,
}: Props) {
  const [expanded, setExpanded] = useState(false);
  const [miniDraft, setMiniDraft] = useState(placement?.miniPrompt || "");

  // Keep draft synced when placement changes externally.
  if (placement && placement.miniPrompt !== miniDraft && !expanded) {
    // non-effect sync — only when collapsed to avoid clobbering edits
  }

  const color = SLOT_COLORS[slot.colorKey];
  const isCharacter = slot.kind === "character";
  const isAssigned = !!placement;
  const location = placement && placement.gridRow >= 0 && placement.gridColumn >= 0
    ? cellLabel(placement.gridRow, placement.gridColumn)
    : "";

  const handleToggleExpand = () => {
    if (!isAssigned) return;
    setExpanded((v) => {
      if (!v) setMiniDraft(placement?.miniPrompt || "");
      return !v;
    });
  };

  const handleSaveMini = () => {
    onUpdateMiniPrompt(miniDraft.trim());
    setExpanded(false);
  };

  const thumbUrl = placement?.assetId ? api.assetUrl(placement.assetId) : null;

  return (
    <div
      className={`spatial-map__slot-card${active ? " is-active" : ""}`}
      data-testid={`spatial-map-slot-${slot.kind}-${slot.index}`}
      onClick={onSelect}
      role="button"
      tabIndex={0}
      aria-pressed={active}
      aria-label={`${slot.label}${isAssigned ? `, assigned ${placement?.tag || ""}` : ", empty"}`}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect();
        }
      }}
    >
      <div className="spatial-map__slot-head">
        <span className="spatial-map__slot-swatch" style={{ background: color }} aria-hidden="true" />
        <span className="spatial-map__slot-label">{slot.label}</span>
      </div>

      {!isAssigned ? (
        <button
          type="button"
          className="spatial-map__slot-add"
          onClick={(e) => {
            e.stopPropagation();
            onAdd();
          }}
          aria-label={`Add ${isCharacter ? "character" : "prop"} to ${slot.label}`}
        >
          + Add {isCharacter ? "Character" : "Prop"}
        </button>
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
            {placement?.tag || "(unnamed)"}
          </div>
          {location ? <div className="spatial-map__slot-assigned-loc">Cell {location}</div> : null}
          {!expanded ? (
            <div className="spatial-map__slot-mini" onClick={handleToggleExpand} role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === "Enter") handleToggleExpand(); }}>
              {placement?.miniPrompt ? placement.miniPrompt : "Add a mini prompt…"}
            </div>
          ) : (
            <>
              <textarea
                className="spatial-map__slot-mini-input"
                value={miniDraft}
                onChange={(e) => setMiniDraft(e.target.value)}
                placeholder={
                  isCharacter
                    ? `e.g. ${placement?.tag || "@Korri"} is standing behind the Barista bar.`
                    : `e.g. ${placement?.tag || "#coffee-cup"} sits on the counter.`
                }
                rows={2}
                aria-label={`Mini prompt for ${slot.label}`}
                onClick={(e) => e.stopPropagation()}
              />
              <div className="spatial-map__slot-actions">
                <button type="button" className="spatial-map__slot-action" onClick={(e) => { e.stopPropagation(); handleSaveMini(); }}>
                  Save
                </button>
                <button type="button" className="spatial-map__slot-action" onClick={(e) => { e.stopPropagation(); setExpanded(false); }}>
                  Cancel
                </button>
              </div>
            </>
          )}
          <div className="spatial-map__slot-actions">
            {placement && !expanded ? (
              <button type="button" className="spatial-map__slot-action" onClick={(e) => { e.stopPropagation(); handleToggleExpand(); }}>
                Edit mini prompt
              </button>
            ) : null}
            <button
              type="button"
              className="spatial-map__slot-action danger"
              onClick={(e) => {
                e.stopPropagation();
                if (window.confirm(`Remove ${placement?.tag || "this placement"} from ${slot.label}?`)) {
                  onRemove();
                }
              }}
            >
              Remove
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
