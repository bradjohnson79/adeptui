/**
 * PropAttachmentEditor — reusable attach/edit form.
 * Character dropdown lists ONLY Spatial Map assigned slots.
 */
import { useEffect, useMemo, useState } from "react";
import {
  attachmentPointsFor,
  formatAttachmentPointLabel,
  formatRelationshipLabel,
  type AssignedCharacterOption,
  type AssignedPropOption,
} from "./attachmentUi";
import {
  PROP_RELATIONSHIPS,
  validatePropAttachment,
  type AttachmentPoint,
  type AttachedCharacterSlot,
  type PropRelationship,
  type SpatialPropAttachmentFields,
} from "./types";

export type PropAttachmentApply = SpatialPropAttachmentFields & { propPlacementId?: string };

type Props = {
  characters: AssignedCharacterOption[];
  props?: AssignedPropOption[];
  initial?: Partial<SpatialPropAttachmentFields> & { propPlacementId?: string };
  lockCharacter?: boolean;
  requirePropChoice?: boolean;
  onCancel: () => void;
  onApply: (payload: PropAttachmentApply) => void;
};

export function PropAttachmentEditor({
  characters,
  props,
  initial,
  lockCharacter = false,
  requirePropChoice = false,
  onCancel,
  onApply,
}: Props) {
  const [propPlacementId, setPropPlacementId] = useState(initial?.propPlacementId || props?.[0]?.id || "");
  const [characterSlot, setCharacterSlot] = useState<AttachedCharacterSlot | "">(
    initial?.attachedCharacterSlot || characters[0]?.slot || "",
  );
  const [relationship, setRelationship] = useState<PropRelationship | "">(initial?.relationship || "held");
  const [attachmentPoint, setAttachmentPoint] = useState<AttachmentPoint | "">(
    initial?.attachmentPoint || "right_hand",
  );
  const [error, setError] = useState<string | null>(null);

  const points = useMemo(() => attachmentPointsFor(relationship || null), [relationship]);

  useEffect(() => {
    if (attachmentPoint && !points.includes(attachmentPoint)) {
      setAttachmentPoint(points[0] || "unspecified");
    }
  }, [points, attachmentPoint]);

  const selectedCharacter = characters.find((c) => c.slot === characterSlot) || null;
  const canApply =
    !!characterSlot &&
    !!relationship &&
    !!selectedCharacter &&
    (!requirePropChoice || !!propPlacementId);

  const handleApply = () => {
    if (!selectedCharacter || !relationship || !characterSlot) return;
    try {
      const payload = validatePropAttachment({
        placementMode: "attached" as const,
        attachedCharacterSlot: characterSlot,
        attachedCharacterId: selectedCharacter.id,
        relationship,
        attachmentPoint: attachmentPoint || null,
      });
      onApply({
        placementMode: "attached",
        attachedCharacterSlot: payload.attachedCharacterSlot as AttachedCharacterSlot,
        attachedCharacterId: payload.attachedCharacterId || selectedCharacter.id,
        relationship: payload.relationship as PropRelationship,
        attachmentPoint: (payload.attachmentPoint as AttachmentPoint | null) || null,
        propPlacementId: requirePropChoice ? propPlacementId : initial?.propPlacementId,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <div className="spatial-map__attach-editor" data-testid="prop-attachment-editor" onClick={(e) => e.stopPropagation()}>
      {requirePropChoice ? (
        <label className="spatial-map__attach-field">
          <span>Prop</span>
          <select
            value={propPlacementId}
            onChange={(e) => setPropPlacementId(e.target.value)}
            aria-label="Select prop to attach"
            data-testid="attach-prop-select"
          >
            <option value="">Select prop</option>
            {(props || []).map((p) => (
              <option key={p.id} value={p.id}>
                {`Prop ${p.slotIndex + 1} — ${p.name}`}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      <label className="spatial-map__attach-field">
        <span>Character</span>
        <select
          value={characterSlot}
          onChange={(e) => setCharacterSlot(Number(e.target.value) as AttachedCharacterSlot)}
          disabled={lockCharacter || characters.length === 0}
          aria-label="Select Spatial Map character"
          data-testid="attach-character-select"
        >
          {characters.length === 0 ? <option value="">No assigned characters</option> : null}
          {characters.map((c) => (
            <option key={c.slot} value={c.slot}>
              {`Character ${c.slot} — ${c.name}`}
            </option>
          ))}
        </select>
      </label>
      <label className="spatial-map__attach-field">
        <span>Relationship</span>
        <select
          value={relationship}
          onChange={(e) => setRelationship(e.target.value as PropRelationship)}
          aria-label="Select relationship"
          data-testid="attach-relationship-select"
        >
          {PROP_RELATIONSHIPS.map((rel) => (
            <option key={rel} value={rel}>
              {formatRelationshipLabel(rel)}
            </option>
          ))}
        </select>
      </label>
      <label className="spatial-map__attach-field">
        <span>Attachment</span>
        <select
          value={attachmentPoint}
          onChange={(e) => setAttachmentPoint(e.target.value as AttachmentPoint)}
          aria-label="Select attachment point"
          data-testid="attach-point-select"
        >
          {points.map((point) => (
            <option key={point} value={point}>
              {formatAttachmentPointLabel(point)}
            </option>
          ))}
        </select>
      </label>
      {error ? <p className="spatial-map__attach-error">{error}</p> : null}
      <div className="spatial-map__slot-actions">
        <button type="button" className="spatial-map__slot-action" onClick={onCancel} data-testid="attach-cancel">
          Cancel
        </button>
        <button
          type="button"
          className="spatial-map__slot-action"
          onClick={handleApply}
          disabled={!canApply}
          data-testid="attach-apply"
        >
          Apply
        </button>
      </div>
    </div>
  );
}
