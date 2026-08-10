import { useEffect, useMemo, useState } from "react";
import { HelpTip, PanelHeading } from "../HelpTip";
import { Button } from "../ui";
import type { Project } from "../../types";
import type {
  SpatialCameraUpdateBody,
  SpatialCharacterPlacementUpdateBody,
  SpatialMapDocument,
  SpatialPropPlacementUpdateBody,
} from "../../contracts/spatialMapM411";

type PlacementKind = "character" | "prop" | "camera";

type CameraInspectorProps = {
  project: Project;
  document: SpatialMapDocument;
  selectedId: string | null;
  onSelect: (placementId: string | null) => void;
  onUpdateCharacter: (placementId: string, body: SpatialCharacterPlacementUpdateBody) => void;
  onUpdateProp: (placementId: string, body: SpatialPropPlacementUpdateBody) => void;
  onUpdateCamera: (cameraId: string, body: SpatialCameraUpdateBody) => void;
  onRemove: (kind: PlacementKind, placementId: string) => void;
};

const CREATIVE_NOTES = ["Foreground", "Midground", "Background", "Stage Left", "Stage Right", "Center Frame"];

function depthLabel(document: SpatialMapDocument, z: number) {
  const span = Math.max(0.001, document.bounds.maxZ - document.bounds.minZ);
  const ratio = (z - document.bounds.minZ) / span;
  if (ratio < 0.34) return "Foreground";
  if (ratio < 0.67) return "Midground";
  return "Background";
}

function clampNumber(value: string, fallback: number) {
  const next = Number(value);
  return Number.isFinite(next) ? next : fallback;
}

export function CameraInspector({
  project,
  document,
  selectedId,
  onSelect,
  onUpdateCharacter,
  onUpdateProp,
  onUpdateCamera,
  onRemove,
}: CameraInspectorProps) {
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const selected = useMemo(() => {
    const character = document.characters.find((item) => item.id === selectedId);
    if (character) return { kind: "character" as const, item: character };
    const prop = document.props.find((item) => item.id === selectedId);
    if (prop) return { kind: "prop" as const, item: prop };
    const camera = document.cameras.find((item) => item.id === selectedId);
    if (camera) return { kind: "camera" as const, item: camera };
    return null;
  }, [document, selectedId]);
  const [labelDraft, setLabelDraft] = useState("");
  const [notesDraft, setNotesDraft] = useState("");
  const [poseDraft, setPoseDraft] = useState("");
  const [expressionDraft, setExpressionDraft] = useState("");
  const [eyeLineDraft, setEyeLineDraft] = useState("");
  const [categoryDraft, setCategoryDraft] = useState("");
  const [stateDraft, setStateDraft] = useState("");
  const [shotTypeDraft, setShotTypeDraft] = useState("");

  useEffect(() => {
    if (!selected) return;
    setLabelDraft(selected.item.label || "");
    setNotesDraft(selected.kind === "camera" ? "" : selected.item.notes || "");
    setPoseDraft(selected.kind === "character" ? selected.item.pose : "");
    setExpressionDraft(selected.kind === "character" ? selected.item.expression : "");
    setEyeLineDraft(selected.kind === "character" ? selected.item.eyeLine : "");
    setCategoryDraft(selected.kind === "prop" ? selected.item.category : "");
    setStateDraft(selected.kind === "prop" ? selected.item.state : "");
    setShotTypeDraft(selected.kind === "camera" ? selected.item.shotType : "");
  }, [selected]);

  if (!selected) {
    return (
      <aside className="spatial-inspector spatial-map-inspector">
        <PanelHeading
          title="Inspector"
          tip="Select a performer, prop, or camera to refine the staging."
        />
        <p className="empty">Select something on the map to shape the scene.</p>
      </aside>
    );
  }

  const imageAssets = project.assets.filter((asset) => asset.kind === "image" || asset.kind === "environment");
  const allItems = [
    ...document.characters.map((item) => ({ id: item.id, label: item.label })),
    ...document.props.map((item) => ({ id: item.id, label: item.label })),
    ...document.cameras.map((item) => ({ id: item.id, label: item.label })),
  ];

  const updateSelected = (body: Record<string, unknown>) => {
    if (selected.kind === "character") onUpdateCharacter(selected.item.id, body as SpatialCharacterPlacementUpdateBody);
    else if (selected.kind === "prop") onUpdateProp(selected.item.id, body as SpatialPropPlacementUpdateBody);
    else onUpdateCamera(selected.item.id, body as SpatialCameraUpdateBody);
  };

  return (
    <aside className="spatial-inspector spatial-map-inspector">
      <PanelHeading
        title={selected.kind === "camera" ? "Camera Inspector" : "Placement Inspector"}
        tip="Keep the canvas as the main staging surface. Use this panel for names, notes, and fine adjustments."
      />

      <div className="spatial-map-inspector-summary">
        <strong>{selected.item.label || "Untitled placement"}</strong>
        <span className="pill">{selected.kind === "camera" ? "Camera View" : selected.kind}</span>
        <span className="pill">{depthLabel(document, selected.item.z)}</span>
      </div>

      <div className="field">
        <label>Name</label>
        <input
          value={labelDraft}
          onChange={(event) => setLabelDraft(event.target.value)}
          onBlur={() => updateSelected({ label: labelDraft })}
        />
      </div>

      {selected.kind !== "camera" ? (
        <>
          <div className="field">
            <label>
              Creative Note
              <HelpTip text="Use plain language your crew would understand at a glance." />
            </label>
            <div className="spatial-map-chip-row">
              {CREATIVE_NOTES.map((note) => (
                <button
                  key={note}
                  type="button"
                  className={`pill spatial-map-chip${notesDraft.includes(note) ? " spatial-map-chip--active" : ""}`}
                  onClick={() => {
                    const next = notesDraft ? `${notesDraft.trim()} · ${note}` : note;
                    setNotesDraft(next);
                    updateSelected({ notes: next });
                  }}
                >
                  {note}
                </button>
              ))}
            </div>
            <textarea
              rows={3}
              value={notesDraft}
              placeholder="Foreground by the window, ready for the hero entrance."
              onChange={(event) => setNotesDraft(event.target.value)}
              onBlur={() => updateSelected({ notes: notesDraft })}
            />
          </div>

          <div className="field">
            <label>Reference Image</label>
            <select
              value={selected.item.assetId || ""}
              onChange={(event) => updateSelected({ assetId: event.target.value || null })}
            >
              <option value="">None yet</option>
              {imageAssets.map((asset) => (
                <option key={asset.id} value={asset.id}>
                  {asset.tag || asset.filename}
                </option>
              ))}
            </select>
          </div>
        </>
      ) : null}

      {selected.kind === "character" ? (
        <>
          <div className="field">
            <label>Pose</label>
            <input
              value={poseDraft}
              onChange={(event) => setPoseDraft(event.target.value)}
              onBlur={() => updateSelected({ pose: poseDraft })}
              placeholder="Relaxed lean"
            />
          </div>
          <div className="field">
            <label>Expression</label>
            <input
              value={expressionDraft}
              onChange={(event) => setExpressionDraft(event.target.value)}
              onBlur={() => updateSelected({ expression: expressionDraft })}
              placeholder="Quiet confidence"
            />
          </div>
          <div className="field">
            <label>Eye Line</label>
            <input
              value={eyeLineDraft}
              onChange={(event) => setEyeLineDraft(event.target.value)}
              onBlur={() => updateSelected({ eyeLine: eyeLineDraft })}
              placeholder="Toward the door"
            />
          </div>
        </>
      ) : null}

      {selected.kind === "prop" ? (
        <>
          <div className="field">
            <label>Prop Type</label>
            <input
              value={categoryDraft}
              onChange={(event) => setCategoryDraft(event.target.value)}
              onBlur={() => updateSelected({ category: categoryDraft })}
              placeholder="Table lamp"
            />
          </div>
          <div className="field">
            <label>Current State</label>
            <input
              value={stateDraft}
              onChange={(event) => setStateDraft(event.target.value)}
              onBlur={() => updateSelected({ state: stateDraft })}
              placeholder="Lit and steady"
            />
          </div>
        </>
      ) : null}

      {selected.kind === "camera" ? (
        <section className="spatial-map-inspector-camera">
          <h3>Camera Feel</h3>
          <div className="field">
            <label>Shot Feel</label>
            <input
              value={shotTypeDraft}
              onChange={(event) => setShotTypeDraft(event.target.value)}
              onBlur={() => updateSelected({ shotType: shotTypeDraft })}
              placeholder="Medium close-up"
            />
          </div>
          <div className="field">
            <label>Lead Performer</label>
            <select
              value={selected.item.targetCharacterIds[0] || ""}
              onChange={(event) =>
                updateSelected({
                  targetCharacterIds: event.target.value ? [event.target.value] : [],
                })
              }
            >
              <option value="">No performer linked</option>
              {document.characters.map((character) => (
                <option key={character.id} value={character.characterId}>
                  {character.label}
                </option>
              ))}
            </select>
          </div>
          <label className="field">
            <span>Hero Angle</span>
            <input
              type="checkbox"
              checked={selected.item.hero}
              onChange={(event) => updateSelected({ hero: event.target.checked })}
            />
          </label>
          <label className="field">
            <span>Keep for 360</span>
            <input
              type="checkbox"
              checked={selected.item.lockedFor360}
              onChange={(event) => updateSelected({ lockedFor360: event.target.checked })}
            />
          </label>
        </section>
      ) : null}

      <div className="spatial-map-inspector-actions">
        <Button
          variant="secondary"
          data-testid="spatial-advanced-toggle"
          onClick={() => setAdvancedOpen((open) => !open)}
        >
          {advancedOpen ? "Hide Advanced" : "Advanced"}
        </Button>
        <Button variant="danger" onClick={() => onRemove(selected.kind, selected.item.id)}>
          Remove
        </Button>
      </div>

      {advancedOpen ? (
        <section className="spatial-map-advanced">
          <div className="field">
            <label>X Position</label>
            <input
              type="number"
              step="0.1"
              value={selected.item.x}
              onChange={(event) => updateSelected({ x: clampNumber(event.target.value, selected.item.x) })}
            />
          </div>
          <div className="field">
            <label>Y Height</label>
            <input
              type="number"
              step="0.1"
              value={selected.item.y}
              onChange={(event) => updateSelected({ y: clampNumber(event.target.value, selected.item.y) })}
            />
          </div>
          <div className="field">
            <label>Z Position</label>
            <input
              type="number"
              step="0.1"
              value={selected.item.z}
              onChange={(event) => updateSelected({ z: clampNumber(event.target.value, selected.item.z) })}
            />
          </div>
          <div className="field">
            <label>Yaw Degrees</label>
            <input
              type="number"
              step="1"
              value={selected.item.yawDegrees}
              onChange={(event) => updateSelected({ yawDegrees: clampNumber(event.target.value, selected.item.yawDegrees) })}
            />
          </div>
          <div className="field">
            <label>Pitch Degrees</label>
            <input
              type="number"
              step="1"
              value={selected.item.pitchDegrees}
              onChange={(event) => updateSelected({ pitchDegrees: clampNumber(event.target.value, selected.item.pitchDegrees) })}
            />
          </div>
          <div className="field">
            <label>Roll Degrees</label>
            <input
              type="number"
              step="1"
              value={selected.item.rollDegrees}
              onChange={(event) => updateSelected({ rollDegrees: clampNumber(event.target.value, selected.item.rollDegrees) })}
            />
          </div>
          {selected.kind !== "camera" ? (
            <div className="field">
              <label>Scale</label>
              <input
                type="number"
                step="0.1"
                value={selected.item.scale}
                onChange={(event) => updateSelected({ scale: clampNumber(event.target.value, selected.item.scale) })}
              />
            </div>
          ) : null}
          {selected.kind === "camera" ? (
            <>
              <div className="field">
                <label>Lens (mm)</label>
                <input
                  type="number"
                  step="1"
                  value={selected.item.lensMm}
                  onChange={(event) => updateSelected({ lensMm: clampNumber(event.target.value, selected.item.lensMm) })}
                />
              </div>
              <div className="field">
                <label>Camera Height</label>
                <input
                  type="number"
                  step="0.1"
                  value={selected.item.heightMeters}
                  onChange={(event) =>
                    updateSelected({ heightMeters: clampNumber(event.target.value, selected.item.heightMeters) })
                  }
                />
              </div>
            </>
          ) : null}
          <div className="field">
            <label>Quick Jump</label>
            <select value={selected.item.id} onChange={(event) => onSelect(event.target.value || null)}>
              {allItems.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>
        </section>
      ) : null}
    </aside>
  );
}
