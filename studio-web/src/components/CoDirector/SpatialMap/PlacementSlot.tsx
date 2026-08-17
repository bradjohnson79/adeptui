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
  characterSlotTag,
  formatAttachmentPointLabel,
  formatRelationshipLabel,
  isAttachedProp,
  type AssignedCharacterOption,
} from "./attachmentUi";
import {
  ENTITY_ENABLED_SWITCH_LABEL,
  isEntityEnabled,
  placementSwitchAriaLabel,
  slotPlacementBadge,
} from "./placementArm";
import { PropAttachmentEditor, type PropAttachmentApply } from "./PropAttachmentEditor";
import {
  PROP_BOUND_TO_APPROVED_MESSAGE,
  PROP_BOUND_UNAPPROVED_MESSAGE,
  PROP_MAP_ONLY_WARNING,
  SLOT_COLORS,
  propOptionPropagatesToSceneCreator,
  propPlacementIsBoundApproved,
  propSourceGroupLabel,
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
  onBindProp?: (option: SavedOption) => void;
  onPlace: () => void;
  onMove: () => void;
  onRemove: () => void;
  onUpdateMiniPrompt: (text: string) => void;
  visible?: boolean;
  onToggleVisible?: () => void;
  onAttach?: () => void;
  onEditAttachment?: () => void;
  onDetachAndPlace?: () => void;
  assignedCharacters?: AssignedCharacterOption[];
  onApplyAttachment?: (payload: PropAttachmentApply) => void;
};

export function PlacementSlot({
  slot,
  placement,
  active,
  savedOptions,
  placing,
  onSelect,
  onAdd,
  onBindProp,
  onPlace,
  onMove,
  onRemove,
  onUpdateMiniPrompt,
  visible,
  onToggleVisible,
  onAttach,
  onEditAttachment,
  onDetachAndPlace,
  assignedCharacters,
  onApplyAttachment,
}: Props) {
  const [expanded, setExpanded] = useState(false);
  const [miniDraft, setMiniDraft] = useState(placement?.miniPrompt || "");
  const [pickedId, setPickedId] = useState("");
  const [pickedSource, setPickedSource] = useState<SavedOption["source"] | undefined>(undefined);

  const color = SLOT_COLORS[slot.colorKey];
  const isCharacter = slot.kind === "character";
  const isAssigned = !!placement;
  const propPlacement = !isCharacter && placement ? (placement as SpatialPropPlacement) : null;
  const attached = !!(propPlacement && isAttachedProp(propPlacement));
  const isPlaced = !!(
    placement &&
    !attached &&
    ((typeof placement.normalizedX === "number" && typeof placement.normalizedY === "number") ||
      (placement.gridRow >= 0 && placement.gridColumn >= 0))
  );
  const location =
    isPlaced && placement!.gridRow >= 0 && placement!.gridColumn >= 0
      ? cellLabel(placement!.gridColumn, placement!.gridRow)
      : "";
  const displayName = placement?.label || placement?.tag || "";
  const thumbUrl = placement?.assetId ? api.assetUrl(placement.assetId) : null;
  const enabled = isAssigned && isEntityEnabled(visible ?? placement?.visible);

  return (
    <div
      className={`spatial-map__entity-card spatial-map__slot-card${active ? " is-active" : ""}${placing ? " is-placing" : ""}${attached ? " is-attached" : ""}`}
      data-testid={`spatial-map-slot-${slot.kind}-${slot.index}`}
      data-placement-mode={propPlacement ? (attached ? "attached" : "independent") : undefined}
      onClick={onSelect}
      role="button"
      tabIndex={0}
      aria-pressed={active}
      aria-current={active && isAssigned ? "true" : undefined}
      aria-label={`${slot.label}${isAssigned ? `, assigned ${displayName}` : ", empty"}${active && isAssigned ? ", active" : ""}${attached ? ", attached" : ""}`}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect();
        }
      }}
    >
      <div className="spatial-map__slot-head">
        {slotPlacementBadge(placing) ? (
          <span className="spatial-map__active-badge is-placement-active" data-testid={`slot-active-badge-${slot.kind}-${slot.index}`}>
            {slotPlacementBadge(placing)}
          </span>
        ) : null}
        <span className="spatial-map__slot-swatch" style={{ background: color }} aria-hidden="true" />
        <span className="spatial-map__slot-label">{slot.label}</span>
        <div className="spatial-map__placement-arm">
          <span
            className={`spatial-map__placement-active-label${enabled ? " is-on" : ""}`}
            data-testid={`${slot.kind}-enabled-label-${slot.index}`}
          >
            {ENTITY_ENABLED_SWITCH_LABEL}
          </span>
          <button
            type="button"
            role="switch"
            className={`spatial-map__slot-toggle${enabled ? " is-on" : ""}${!isAssigned ? " is-disabled" : ""}`}
            aria-checked={enabled}
            aria-disabled={!isAssigned}
            disabled={!isAssigned}
            aria-label={placementSwitchAriaLabel(slot.label, enabled, { assigned: isAssigned, attached })}
            data-testid={`${slot.kind}-online-${slot.index}`}
            onClick={(e) => {
              e.stopPropagation();
              if (!isAssigned) return;
              onToggleVisible?.();
            }}
          >
            <span className="spatial-map__slot-toggle-thumb" aria-hidden="true" />
          </button>
        </div>
      </div>

      {!isAssigned ? (
        <div className="spatial-map__slot-assign" onClick={(e) => e.stopPropagation()}>
          <select
            className="spatial-map__slot-select"
            value={pickedId}
            onChange={(e) => {
              const id = e.target.value;
              setPickedId(id);
              const option = savedOptions.find((o) => o.id === id);
              setPickedSource(option?.source);
              if (option) onAdd(option);
            }}
            aria-label={`Select saved ${isCharacter ? "character" : "prop"} for ${slot.label}`}
            data-testid={`${slot.kind}-select-${slot.index}`}
          >
            <option value="">{isCharacter ? "Select Saved Character" : "Select Saved Prop"}</option>
            {isCharacter
              ? savedOptions.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.name}
                  </option>
                ))
              : (["project", "character", "library"] as const).map((source) => {
                  const group = savedOptions.filter((o) => (o.source || "library") === source);
                  if (!group.length) return null;
                  return (
                    <optgroup key={source} label={propSourceGroupLabel(source)}>
                      {group.map((option) => (
                        <option key={`${option.source || "library"}:${option.id}`} value={option.id}>
                          {option.name}
                        </option>
                      ))}
                    </optgroup>
                  );
                })}
          </select>
          {!isCharacter && !propOptionPropagatesToSceneCreator({ source: pickedSource }) ? (
            <p
              className="spatial-map__maponly-note"
              role="status"
              data-testid={`${slot.kind}-maponly-note-${slot.index}`}
            >
              {PROP_MAP_ONLY_WARNING}
            </p>
          ) : null}
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
            {!isCharacter && propPlacement && !propPlacement.propId ? (
              <span
                className="spatial-map__maponly-badge"
                title={PROP_MAP_ONLY_WARNING}
                data-testid={`prop-maponly-badge-${slot.index}`}
              >
                Map only
              </span>
            ) : null}
            {!isCharacter && propPlacement && propPlacement.propId && propPlacementIsBoundApproved(propPlacement, savedOptions) ? (
              <span
                className="spatial-map__bound-badge"
                data-testid={`prop-bound-approved-${slot.index}`}
              >
                Bound
              </span>
            ) : null}
            {!isCharacter && propPlacement && propPlacement.propId && !propPlacementIsBoundApproved(propPlacement, savedOptions) ? (
              <span
                className="spatial-map__maponly-badge"
                data-testid={`prop-bound-unapproved-${slot.index}`}
              >
                Not approved
              </span>
            ) : null}
          </div>
          {!isCharacter && propPlacement && !propPlacement.propId && onBindProp ? (
            <div
              className="spatial-map__slot-bind"
              onClick={(e) => e.stopPropagation()}
              data-testid={`prop-bind-${slot.index}`}
            >
              <p className="spatial-map__maponly-note" role="status" data-testid={`prop-maponly-note-${slot.index}`}>
                {PROP_MAP_ONLY_WARNING}
              </p>
              <select
                className="spatial-map__slot-select"
                value=""
                aria-label={`Bind ${displayName || "prop"} to an approved Project Prop`}
                data-testid={`prop-bind-select-${slot.index}`}
                onChange={(e) => {
                  const id = e.target.value;
                  if (!id) return;
                  const option = savedOptions.find((o) => o.id === id);
                  if (option) onBindProp(option);
                }}
              >
                <option value="">Select Saved Prop</option>
                {savedOptions
                  .filter((o) => (o.source || "library") === "project")
                  .map((option) => (
                    <option key={option.id} value={option.id}>
                      {option.name}
                    </option>
                  ))}
              </select>
            </div>
          ) : null}
          {!isCharacter && propPlacement && propPlacement.propId && propPlacementIsBoundApproved(propPlacement, savedOptions) ? (
            <p
              className="spatial-map__bound-note"
              role="status"
              data-testid={`prop-bound-note-${slot.index}`}
            >
              {PROP_BOUND_TO_APPROVED_MESSAGE}
            </p>
          ) : null}
          {!isCharacter && propPlacement && propPlacement.propId && !propPlacementIsBoundApproved(propPlacement, savedOptions) ? (
            <p
              className="spatial-map__maponly-note"
              role="status"
              data-testid={`prop-unapproved-note-${slot.index}`}
            >
              {PROP_BOUND_UNAPPROVED_MESSAGE}
            </p>
          ) : null}
          {attached && propPlacement ? (
            <div className="spatial-map__entity-card-meta spatial-map__attach-tags" data-testid={`prop-attach-tags-${slot.index}`}>
              {characterSlotTag(propPlacement.attachedCharacterSlot) ? (
                <span className="spatial-map__attach-tag" data-testid={`prop-attach-tag-slot-${slot.index}`}>
                  {characterSlotTag(propPlacement.attachedCharacterSlot)}
                </span>
              ) : null}
              {propPlacement.relationship ? (
                <span className="spatial-map__attach-tag" data-testid={`prop-attach-tag-rel-${slot.index}`}>
                  {formatRelationshipLabel(propPlacement.relationship)}
                </span>
              ) : null}
              {propPlacement.attachmentPoint ? (
                <span className="spatial-map__attach-tag" data-testid={`prop-attach-tag-point-${slot.index}`}>
                  {formatAttachmentPointLabel(propPlacement.attachmentPoint)}
                </span>
              ) : null}
            </div>
          ) : location ? (
            <div className="spatial-map__slot-assigned-loc">Cell {location}</div>
          ) : null}
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
            {attached ? (
              <>
                <button
                  type="button"
                  className="spatial-map__slot-action"
                  onClick={(e) => {
                    e.stopPropagation();
                    onEditAttachment?.();
                  }}
                  aria-label={`Edit attachment for ${displayName || "prop"}`}
                  data-testid={`prop-edit-attachment-${slot.index}`}
                >
                  Edit
                </button>
                <button
                  type="button"
                  className="spatial-map__slot-action"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDetachAndPlace?.();
                  }}
                  aria-label={`Detach and place ${displayName || "prop"}`}
                  data-testid={`prop-detach-place-${slot.index}`}
                >
                  Detach & Place
                </button>
              </>
            ) : (
              <>
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
                {!isCharacter && onAttach ? (
                  <button
                    type="button"
                    className="spatial-map__slot-action"
                    onClick={(e) => {
                      e.stopPropagation();
                      onAttach();
                    }}
                    aria-label={`Attach ${displayName || "prop"} to character`}
                    data-testid={`prop-attach-${slot.index}`}
                  >
                    Attach to Character
                  </button>
                ) : null}
              </>
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
            {expanded ? "Hide" : "More"}
          </button>
          {expanded ? (
            <>
              {!isCharacter && onApplyAttachment ? (
                <div
                  className="spatial-map__slot-association"
                  data-testid={`slot-association-${slot.index}`}
                  onClick={(e) => e.stopPropagation()}
                >
                  <p className="spatial-map__slot-assigned-tag">Association</p>
                  <PropAttachmentEditor
                    characters={assignedCharacters || []}
                    initial={{
                      propPlacementId: propPlacement?.id,
                      attachedCharacterSlot: propPlacement?.attachedCharacterSlot || null,
                      attachedCharacterId: propPlacement?.attachedCharacterId || null,
                      relationship: propPlacement?.relationship || "held",
                      attachmentPoint: propPlacement?.attachmentPoint || "right_hand",
                    }}
                    onCancel={() => setExpanded(false)}
                    onApply={(payload) => {
                      onApplyAttachment(payload);
                      setExpanded(false);
                    }}
                  />
                  {attached && onDetachAndPlace ? (
                    <div className="spatial-map__slot-actions">
                      <button
                        type="button"
                        className="spatial-map__slot-action"
                        onClick={(e) => {
                          e.stopPropagation();
                          onDetachAndPlace();
                          setExpanded(false);
                        }}
                        aria-label={`Detach and place ${displayName || "prop"}`}
                        data-testid={`prop-detach-place-more-${slot.index}`}
                      >
                        Detach & Place
                      </button>
                    </div>
                  ) : null}
                </div>
              ) : null}
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
