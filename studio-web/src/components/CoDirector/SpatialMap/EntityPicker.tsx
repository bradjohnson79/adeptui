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
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../../../api";
import {
  getCardPreviewUrl,
  isImageAsset,
  type LibraryAsset,
} from "../library/assetModel";
import { characterTag, type SlotDef } from "./types";

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
      kind: "environment";
      projectId: string;
      title?: string;
      onClose: () => void;
      onConfirm: (assetId: string) => void;
    };

const FOCUSABLE_SELECTOR =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function EntityPicker(props: Props) {
  const { kind, projectId, onClose } = props;
  const slot = "slot" in props ? props.slot : undefined;
  const title = "title" in props && props.title ? props.title : undefined;
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    previouslyFocusedRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    panelRef.current?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key !== "Tab") return;
      const root = panelRef.current;
      if (!root) return;
      const nodes = Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR));
      if (nodes.length === 0) {
        e.preventDefault();
        root.focus();
        return;
      }
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      const active = document.activeElement;
      if (e.shiftKey && (active === first || active === root)) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      previouslyFocusedRef.current?.focus();
    };
  }, [onClose]);

  const ariaLabel = kind === "environment" ? (title || "Select Spatial Map Image") : `${slot?.label || kind} picker`;

  return createPortal(
    <div className="spatial-map__picker" role="dialog" aria-modal="true" aria-labelledby={titleId} aria-label={ariaLabel}>
      <div className="spatial-map__picker-panel" ref={panelRef} tabIndex={-1}>
        <button type="button" className="spatial-map__picker-close" aria-label="Close" onClick={onClose}>×</button>
        <h3 className="spatial-map__picker-title" id={titleId}>
          {kind === "character" ? "Choose a Character" : title || "Select Spatial Map Image"}
        </h3>
        {kind === "character" ? (
          <CharacterPickerBody
            projectId={projectId}
            onConfirm={(tag, characterId, name) => props.onConfirm(tag, characterId, name)}
          />
        ) : kind === "environment" ? (
          <EnvironmentPickerBody
            projectId={projectId}
            onClose={onClose}
            onConfirm={(assetId) => (props.onConfirm as (assetId: string) => void)(assetId)}
          />
        ) : null}
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
        <button
          type="button"
          className="ui-btn ui-btn--primary"
          disabled={!canConfirm}
          title={!canConfirm ? "Select or type a saved character first" : undefined}
          onClick={handleConfirm}
        >
          Confirm
        </button>
      </div>
    </>
  );
}

function EnvironmentPickerBody({
  projectId,
  onConfirm,
  onClose,
}: {
  projectId: string;
  onConfirm: (assetId: string) => void;
  onClose: () => void;
}) {
  const [assets, setAssets] = useState<LibraryAsset[]>([]);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedAsset, setSelectedAsset] = useState<LibraryAsset | null>(null);
  const [query, setQuery] = useState("");

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

  const filteredAssets = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return assets;
    return assets.filter((a) => {
      const tag = (a.tag || "").toLowerCase();
      const filename = (a.filename || "").toLowerCase();
      return tag.includes(q) || filename.includes(q);
    });
  }, [assets, query]);

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
        <>
          <div className="spatial-map__picker-row">
            <input
              type="search"
              className="spatial-map__picker-input"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search images"
              aria-label="Search library images"
              data-testid="environment-picker-search"
            />
          </div>
          {filteredAssets.length === 0 ? (
            <p className="spatial-map__hint">No images match that search.</p>
          ) : (
            <div className="spatial-map__picker-grid" role="list" data-testid="environment-picker-grid">
              {filteredAssets.map((a) => {
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
        </>
      )}
      <div className="spatial-map__picker-row" style={{ justifyContent: "flex-end" }}>
        <button
          type="button"
          className="ui-btn ui-btn--secondary"
          onClick={onClose}
          data-testid="environment-picker-cancel"
        >
          Cancel
        </button>
        <button
          type="button"
          className="ui-btn ui-btn--primary"
          disabled={!canConfirm}
          title={!canConfirm ? "Select an Atlas Shot or environment image first" : undefined}
          onClick={handleConfirm}
          data-testid="environment-picker-confirm"
        >
          Select
        </button>
      </div>
    </>
  );
}
