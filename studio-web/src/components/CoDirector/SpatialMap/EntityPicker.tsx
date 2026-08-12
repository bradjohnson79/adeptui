/**
 * Entity picker — reusable picker for character + prop slots.
 *
 * Character picker: lists saved project characters (reuses api.listCharacterProfiles).
 * Validates typed names against saved characters (amendment #5 — real names with
 * spaces/apostrophes/hyphens). UI pickers preferred over regex guessing.
 *
 * Prop picker: mandatory Library image + tag input that normalizes to #prop-tag
 * (e.g. "Coffee Cup" → #coffee-cup). Reuses the Library asset list endpoint.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../../../api";
import {
  getCardPreviewUrl,
  isImageAsset,
  type LibraryAsset,
} from "../library/assetModel";
import { characterTag, normalizePropTag, type SlotDef } from "./types";

type CharacterProfileLite = {
  id: string;
  name: string;
};

type Props =
  | {
      kind: "character";
      projectId: string;
      slot: SlotDef;
      onClose: () => void;
      onConfirm: (tag: string, characterId: string, characterName: string) => void;
    }
  | {
      kind: "prop";
      projectId: string;
      slot: SlotDef;
      onClose: () => void;
      onConfirm: (tag: string, assetId: string, displayLabel: string) => void;
    }
  | {
      kind: "environment";
      projectId: string;
      title?: string;
      onClose: () => void;
      onConfirm: (assetId: string) => void;
    };

export function EntityPicker(props: Props) {
  const { kind, projectId, onClose } = props;
  const slot = "slot" in props ? props.slot : undefined;
  const title = "title" in props && props.title ? props.title : undefined;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const ariaLabel = kind === "environment" ? (title || "Select Spatial Map Image") : `${slot?.label || kind} picker`;

  return createPortal(
    <div className="spatial-map__picker" role="dialog" aria-modal="true" aria-label={ariaLabel}>
      <div className="spatial-map__picker-panel">
        <button type="button" className="spatial-map__picker-close" aria-label="Close" onClick={onClose}>×</button>
        <h3 className="spatial-map__picker-title">
          {kind === "character" ? "Choose a Character" :
           kind === "environment" ? (title || "Select Spatial Map Image") :
           "Add a Prop"}
        </h3>
        {kind === "character" ? (
          <CharacterPickerBody
            projectId={projectId}
            onConfirm={(tag, characterId, name) => props.onConfirm(tag, characterId, name)}
          />
        ) : kind === "environment" ? (
          <EnvironmentPickerBody
            projectId={projectId}
            onConfirm={(assetId) => (props.onConfirm as (assetId: string) => void)(assetId)}
          />
        ) : (
          <PropPickerBody
            projectId={projectId}
            onConfirm={(tag, assetId, label) => props.onConfirm(tag, assetId, label)}
          />
        )}
      </div>
    </div>,
    document.body,
  );
}

function CharacterPickerBody({
  projectId,
  onConfirm,
}: {
  projectId: string;
  onConfirm: (tag: string, characterId: string, name: string) => void;
}) {
  const [characters, setCharacters] = useState<CharacterProfileLite[]>([]);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string>("");
  const [typedName, setTypedName] = useState("");

  const refresh = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const result = (await api.listCharacterProfiles(projectId)) as { items?: CharacterProfileLite[] };
      const list = Array.isArray(result?.items) ? result.items : [];
      setCharacters(list);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [projectId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const selectedCharacter = useMemo(
    () => characters.find((c) => c.id === selectedId) || null,
    [characters, selectedId],
  );

  const resolvedName = selectedCharacter?.name || typedName.trim();
  const resolvedTag = characterTag(resolvedName);
  // Validate typed name against saved characters (amendment #5).
  const typedValid = !typedName.trim() || characters.some((c) => c.name.toLowerCase() === typedName.trim().toLowerCase());
  const canConfirm = resolvedName.length > 0 && (selectedCharacter ? true : typedValid);

  const handleConfirm = useCallback(() => {
    if (!canConfirm || !resolvedName) return;
    const characterId = selectedCharacter?.id || "";
    onConfirm(resolvedTag, characterId, resolvedName);
  }, [canConfirm, resolvedName, selectedCharacter, onConfirm]);

  if (busy) return <p className="spatial-map__busy">Loading characters…</p>;
  if (error) {
    return (
      <>
        <p className="spatial-map__hint error">{error}</p>
        <button type="button" className="ui-btn ui-btn--secondary" onClick={() => void refresh()}>Retry</button>
      </>
    );
  }

  return (
    <>
      {characters.length === 0 ? (
        <p className="spatial-map__hint">No saved characters yet. Create characters in the Character Creator first.</p>
      ) : (
        <div className="spatial-map__picker-grid" role="list">
          {characters.map((c) => (
            <button
              key={c.id}
              type="button"
              className={`spatial-map__picker-card${selectedId === c.id ? " is-selected" : ""}`}
              onClick={() => {
                setSelectedId(c.id);
                setTypedName("");
              }}
              aria-pressed={selectedId === c.id}
            >
              <span className="spatial-map__picker-name">{c.name}</span>
            </button>
          ))}
        </div>
      )}
      <p className="spatial-map__hint">Or type a character name to validate against saved characters:</p>
      <div className="spatial-map__picker-row">
        <input
          type="text"
          className="spatial-map__picker-input"
          placeholder="e.g. Korri O'Brien-Smith"
          value={typedName}
          onChange={(e) => {
            setTypedName(e.target.value);
            setSelectedId("");
          }}
          aria-label="Character name"
        />
        <span className="spatial-map__hint">
          {resolvedTag ? `Tag: ${resolvedTag}` : "Tag will appear here"}
        </span>
      </div>
      {typedName.trim() && !typedValid ? (
        <p className="spatial-map__hint error">
          "{typedName.trim()}" doesn't match a saved character. Pick from the list above or create it first.
        </p>
      ) : null}
      <div className="spatial-map__picker-row" style={{ justifyContent: "flex-end" }}>
        <button type="button" className="ui-btn ui-btn--primary" disabled={!canConfirm} onClick={handleConfirm}>
          Confirm
        </button>
      </div>
    </>
  );
}

function PropPickerBody({
  projectId,
  onConfirm,
}: {
  projectId: string;
  onConfirm: (tag: string, assetId: string, displayLabel: string) => void;
}) {
  const [assets, setAssets] = useState<LibraryAsset[]>([]);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedAsset, setSelectedAsset] = useState<LibraryAsset | null>(null);
  const [labelInput, setLabelInput] = useState("");

  const refresh = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const payload = await api.library(projectId, {});
      const items = Array.isArray(payload?.items) ? (payload.items as LibraryAsset[]) : [];
      // Show only images — props are anchored by a Library image asset.
      setAssets(items.filter(isImageAsset));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [projectId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const normalizedTag = useMemo(() => {
    const t = normalizePropTag(labelInput);
    return t ? `#${t}` : "";
  }, [labelInput]);

  const canConfirm = !!selectedAsset && !!labelInput.trim() && !!normalizedTag;

  const handleConfirm = useCallback(() => {
    if (!canConfirm || !selectedAsset) return;
    onConfirm(normalizedTag, selectedAsset.id, labelInput.trim());
  }, [canConfirm, selectedAsset, normalizedTag, labelInput, onConfirm]);

  if (busy) return <p className="spatial-map__busy">Loading Library images…</p>;
  if (error) {
    return (
      <>
        <p className="spatial-map__hint error">{error}</p>
        <button type="button" className="ui-btn ui-btn--secondary" onClick={() => void refresh()}>Retry</button>
      </>
    );
  }

  return (
    <>
      <p className="spatial-map__hint">Step 1 — choose a Library image (anchors the prop's visual identity):</p>
      {assets.length === 0 ? (
        <p className="spatial-map__hint">No images in the Library yet. Generate or upload an image first.</p>
      ) : (
        <div className="spatial-map__picker-grid" role="list">
          {assets.map((a) => (
            <button
              key={a.id}
              type="button"
              className={`spatial-map__picker-card${selectedAsset?.id === a.id ? " is-selected" : ""}`}
              onClick={() => setSelectedAsset(a)}
              aria-pressed={selectedAsset?.id === a.id}
            >
              {getCardPreviewUrl(a) ? (
                <img className="spatial-map__picker-thumb" src={getCardPreviewUrl(a)!} alt={a.tag || a.filename || "asset"} loading="lazy" />
              ) : (
                <div className="spatial-map__picker-thumb" />
              )}
              <span className="spatial-map__picker-name">{a.tag || a.filename || "Untitled"}</span>
            </button>
          ))}
        </div>
      )}
      <p className="spatial-map__hint">Step 2 — name this prop (normalizes to a #tag):</p>
      <div className="spatial-map__picker-row">
        <input
          type="text"
          className="spatial-map__picker-input"
          placeholder="e.g. Coffee Cup"
          value={labelInput}
          onChange={(e) => setLabelInput(e.target.value)}
          aria-label="Prop label"
        />
        <span className="spatial-map__hint">{normalizedTag ? `Tag: ${normalizedTag}` : "Tag will appear here"}</span>
      </div>
      <div className="spatial-map__picker-row" style={{ justifyContent: "flex-end" }}>
        <button type="button" className="ui-btn ui-btn--primary" disabled={!canConfirm} onClick={handleConfirm}>
          Confirm
        </button>
      </div>
    </>
  );
}

function EnvironmentPickerBody({
  projectId,
  onConfirm,
}: {
  projectId: string;
  onConfirm: (assetId: string) => void;
}) {
  const [assets, setAssets] = useState<LibraryAsset[]>([]);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedAsset, setSelectedAsset] = useState<LibraryAsset | null>(null);

  const refresh = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const payload = await api.library(projectId, {});
      const items = Array.isArray(payload?.items) ? (payload.items as LibraryAsset[]) : [];
      setAssets(items.filter(isImageAsset));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [projectId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const canConfirm = !!selectedAsset;

  const handleConfirm = useCallback(() => {
    if (!canConfirm || !selectedAsset) return;
    onConfirm(selectedAsset.id);
  }, [canConfirm, selectedAsset, onConfirm]);

  if (busy) return <p className="spatial-map__busy">Loading Library images…</p>;
  if (error) {
    return (
      <>
        <p className="spatial-map__hint error">{error}</p>
        <button type="button" className="ui-btn ui-btn--secondary" onClick={() => void refresh()}>Retry</button>
      </>
    );
  }

  return (
    <>
      <p className="spatial-map__hint">
        Choose an Atlas Shot or Master Environment Image from your Library.
      </p>
      <p className="spatial-map__hint">
        Atlas Shots provide the clearest spatial reference, but a normal Master Environment Image can also be used.
      </p>
      {assets.length === 0 ? (
        <p className="spatial-map__hint">No images in the Library yet. Generate or upload an image first.</p>
      ) : (
        <div className="spatial-map__picker-grid" role="list" data-testid="environment-picker-grid">
          {assets.map((a) => {
            const isAtlas = (a.tag || "").toLowerCase().includes("atlas");
            return (
              <button
                key={a.id}
                type="button"
                className={`spatial-map__picker-card${selectedAsset?.id === a.id ? " is-selected" : ""}`}
                onClick={() => setSelectedAsset(a)}
                aria-pressed={selectedAsset?.id === a.id}
                data-testid={`environment-asset-${a.id}`}
              >
                {getCardPreviewUrl(a) ? (
                  <img className="spatial-map__picker-thumb" src={getCardPreviewUrl(a)!} alt={a.tag || a.filename || "asset"} loading="lazy" />
                ) : (
                  <div className="spatial-map__picker-thumb" />
                )}
                <span className="spatial-map__picker-name">{a.tag || a.filename || "Untitled"}</span>
                {isAtlas && <span className="spatial-map__atlas-badge" data-testid={`atlas-badge-${a.id}`}>Atlas Shot</span>}
              </button>
            );
          })}
        </div>
      )}
      <div className="spatial-map__picker-row" style={{ justifyContent: "flex-end" }}>
        <button
          type="button"
          className="ui-btn ui-btn--primary"
          disabled={!canConfirm}
          onClick={handleConfirm}
          data-testid="environment-picker-confirm"
        >
          Use as Spatial Map Image
        </button>
      </div>
    </>
  );
}
