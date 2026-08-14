/**
 * CharacterInspector — attached prop list + Attach Prop for a selected character.
 */
import {
  characterSlotTag,
  formatAttachedPropSummary,
  type AssignedCharacterOption,
} from "./attachmentUi";
import type { SpatialCharacterPlacement, SpatialPropPlacement } from "./types";

type Props = {
  character: SpatialCharacterPlacement;
  assigned: AssignedCharacterOption | null;
  attached: SpatialPropPlacement[];
  onAttachProp: () => void;
  onEditAttachment: (prop: SpatialPropPlacement) => void;
  onDetachAndPlace: (prop: SpatialPropPlacement) => void;
};

export function CharacterInspector({
  character,
  assigned,
  attached,
  onAttachProp,
  onEditAttachment,
  onDetachAndPlace,
}: Props) {
  const name = character.label || character.tag || "Character";
  const slotTag = assigned ? characterSlotTag(assigned.slot) : character.slotIndex >= 0 ? `C${character.slotIndex + 1}` : "";

  return (
    <div className="spatial-map__character-inspector" data-testid="character-inspector">
      <p className="spatial-map__camera-inspector-title">
        {slotTag ? `${slotTag} — ${name}` : name}
      </p>
      <div className="spatial-map__attach-list" data-testid="character-attached-list">
        {attached.length === 0 ? (
          <p className="spatial-map__attach-empty">No attached props</p>
        ) : (
          attached.map((prop) => (
            <div key={prop.id} className="spatial-map__attach-row" data-testid={`character-attached-${prop.id}`}>
              <span className="spatial-map__attach-row-label">{formatAttachedPropSummary(prop)}</span>
              <div className="spatial-map__slot-actions">
                <button
                  type="button"
                  className="spatial-map__slot-action"
                  onClick={() => onEditAttachment(prop)}
                  data-testid={`character-edit-attachment-${prop.slotIndex}`}
                >
                  Edit
                </button>
                <button
                  type="button"
                  className="spatial-map__slot-action"
                  onClick={() => onDetachAndPlace(prop)}
                  data-testid={`character-detach-place-${prop.slotIndex}`}
                >
                  Detach &amp; Place
                </button>
              </div>
            </div>
          ))
        )}
      </div>
      <button
        type="button"
        className="spatial-map__slot-action"
        onClick={onAttachProp}
        data-testid="character-attach-prop"
      >
        + Attach Prop
      </button>
    </div>
  );
}
