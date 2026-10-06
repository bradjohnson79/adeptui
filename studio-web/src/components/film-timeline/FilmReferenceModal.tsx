import { useEffect, useMemo, useState } from "react";
import { api } from "../../api";
import type { Asset } from "../../types";
import { explicitLibraryAssetsForTab, referencePresentation, type ReferenceTab } from "./referenceRole";
import {
  emptyReferenceGroups,
  groupReferenceOptions,
  loadEntityOptions,
  type EntityKind,
  type ReferenceOption,
  type ReferenceOptionGroups,
} from "./referenceEntities";
import { storyboardEnvironmentSaves, type StoryboardReferenceSave } from "./storyboardEnvironmentReference";

export type FilmReference = {
  id: string;
  type: string;
  label: string;
  assetId: string;
  tag?: string;
  source?: string;
  role?: string;
  inherited?: boolean;
};

export type FilmReferenceSave = {
  assetId: string;
  type: string;
  label: string;
  tag: string;
  source?: string;
  role?: string;
  referenceId?: string;
  frames?: StoryboardReferenceSave[];
};

const TYPES = [
  ["character", "Character", "@"],
  ["environment", "Environment", "#"],
  ["prop", "Prop", "%"],
  ["video", "Video", "*"],
  ["audio", "Audio", "&"],
] as const;

type Kind = (typeof TYPES)[number][0];

const GROUP_HEADINGS: Array<[keyof ReferenceOptionGroups, string]> = [
  ["project", "PROJECT"],
  ["storyboard", "STORYBOARD"],
  ["global", "GLOBAL"],
  ["library", "LIBRARY REFERENCES"],
];

function tabForAsset(asset: Asset | undefined, editingType: string | undefined): Kind {
  if (editingType && TYPES.some((row) => row[0] === editingType)) return editingType as Kind;
  const role = referencePresentation(asset || { kind: "" }).effectiveRole;
  if (role && TYPES.some((row) => row[0] === role)) return role;
  return "character";
}

function isEntityKind(kind: Kind): kind is EntityKind {
  return kind === "character" || kind === "prop" || kind === "environment";
}

function mediaDisplayName(asset: Asset) {
  const tag = (asset.tag || "").trim();
  const file = (asset.filename || "").replace(/\.[A-Za-z0-9]{2,5}$/, "").trim();
  if (tag && tag !== "character_reference") return tag;
  return file || tag || "Image";
}

export function FilmReferenceModal({
  assets,
  references,
  projectId,
  initialAssetId,
  editId,
  onClose,
  onSave,
}: {
  assets: Asset[];
  references: FilmReference[];
  projectId: string;
  initialAssetId?: string;
  editId?: string;
  onClose: () => void;
  onSave: (body: FilmReferenceSave) => Promise<void>;
}) {
  const editing = references.find((item) => item.id === editId) || null;
  const starter = assets.find((item) => item.id === (editing?.assetId || initialAssetId)) || null;
  const [kind, setKind] = useState<Kind>(tabForAsset(starter || undefined, editing?.type));
  const [groups, setGroups] = useState<ReferenceOptionGroups>(emptyReferenceGroups());
  const [loadingEntities, setLoadingEntities] = useState(false);
  // Per-reference alias map. Each bound/selected reference owns its own Name.
  // Keyed by the option key so switching selection restores that reference's alias.
  const [aliases, setAliases] = useState<Record<string, string>>({});
  // Per-tab selection memory. Each tab remembers its own last selected option
  // for the lifetime of the open modal, so switching tabs and back restores it.
  const [selectedByTab, setSelectedByTab] = useState<Record<Kind, string>>({
    character: "",
    environment: "",
    prop: "",
    video: "",
    audio: "",
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const selectedKey = selectedByTab[kind] || "";
  const setSelectedKey = (key: string) => setSelectedByTab((current) => ({ ...current, [kind]: key }));

  // Media tabs (video/audio) keep the V1 media-kind listing. Image tabs source
  // saved entities from the creator registries plus explicit library images.
  const mediaChoices = useMemo(() => {
    if (isEntityKind(kind)) return [];
    return assets.filter((asset) => referencePresentation(asset).effectiveRole === (kind as ReferenceTab));
  }, [assets, kind]);

  const libraryChoices = useMemo(() => {
    if (!isEntityKind(kind)) return [];
    return explicitLibraryAssetsForTab(assets, kind as ReferenceTab);
  }, [assets, kind]);

  // Load saved creator entities for the active image tab (V1 wiring).
  useEffect(() => {
    if (!isEntityKind(kind)) {
      setGroups(emptyReferenceGroups());
      return;
    }
    let cancelled = false;
    setLoadingEntities(true);
    void loadEntityOptions(projectId, kind)
      .then((entities) => {
        if (cancelled) return;
        setGroups(groupReferenceOptions(entities, libraryChoices, kind));
      })
      .catch(() => {
        if (!cancelled) setGroups(groupReferenceOptions([], libraryChoices, kind));
      })
      .finally(() => {
        if (!cancelled) setLoadingEntities(false);
      });
    return () => {
      cancelled = true;
    };
  }, [kind, projectId, libraryChoices]);

  const allOptions = useMemo(
    () => [...groups.project, ...groups.storyboard, ...groups.global, ...groups.library],
    [groups],
  );

  const selectedOption = allOptions.find((option) => option.key === selectedKey) || null;
  const selectedMedia = !isEntityKind(kind)
    ? mediaChoices.find((asset) => asset.id === selectedKey) || null
    : null;

  // Initialize selection + alias when editing an existing reference or when an
  // initial asset is supplied. The alias belongs to THIS reference only.
  // Initialization targets the tab that owns the editing/initial asset and only
  // seeds a tab that has no selection yet, so it never clobbers per-tab memory.
  useEffect(() => {
    if (editing) {
      const targetTab = tabForAsset(undefined, editing.type);
      const match = allOptions.find((option) => option.assetId === editing.assetId);
      const key = isEntityKind(targetTab) ? match?.key || `library:${editing.assetId}` : editing.assetId;
      setSelectedByTab((current) => (current[targetTab] ? current : { ...current, [targetTab]: key }));
      const alias = (editing.tag || editing.label || "").replace(/^[@#%*&~]+/, "");
      setAliases((current) => ({ ...current, [key]: alias }));
      return;
    }
    if (initialAssetId) {
      const targetTab = tabForAsset(
        assets.find((item) => item.id === initialAssetId),
        undefined,
      );
      const match = allOptions.find((option) => option.assetId === initialAssetId);
      if (match) {
        setSelectedByTab((current) => (current[targetTab] ? current : { ...current, [targetTab]: match.key }));
        setAliases((current) =>
          current[match.key] !== undefined ? current : { ...current, [match.key]: match.defaultAlias },
        );
        return;
      }
      if (!isEntityKind(targetTab)) {
        setSelectedByTab((current) => (current[targetTab] ? current : { ...current, [targetTab]: initialAssetId }));
        const asset = assets.find((item) => item.id === initialAssetId);
        const alias = asset ? mediaDisplayName(asset) : "";
        setAliases((current) =>
          current[initialAssetId] !== undefined ? current : { ...current, [initialAssetId]: alias },
        );
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editing?.id, initialAssetId, allOptions.length]);

  function choose(option: ReferenceOption) {
    setSelectedKey(option.key);
    setAliases((current) =>
      current[option.key] !== undefined ? current : { ...current, [option.key]: option.defaultAlias },
    );
  }

  function chooseMedia(asset: Asset) {
    setSelectedKey(asset.id);
    setAliases((current) =>
      current[asset.id] !== undefined ? current : { ...current, [asset.id]: mediaDisplayName(asset) },
    );
  }

  // Switching tabs changes the option set. Selection is stored per tab
  // (selectedByTab), so leaving a tab retains its selection and returning
  // restores it. Aliases are kept per option key, so each reference's own
  // Name is restored with its selection. No cross-tab leakage.
  function switchKind(next: Kind) {
    if (next === kind) return;
    setKind(next);
    setError("");
  }

  const name = aliases[selectedKey] ?? "";
  const prefix = TYPES.find((row) => row[0] === kind)?.[2] || "@";
  const preview = name.trim() ? `${prefix}${name.replace(/^[@#%*&~]+/, "")}` : "";

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function save() {
    const assetId = isEntityKind(kind) ? selectedOption?.assetId || "" : selectedMedia?.id || "";
    if (!assetId) {
      setError("Choose a reference.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      if (selectedOption?.frames?.length) {
        const frames = storyboardEnvironmentSaves({
          documentId: selectedOption.storyboardId || "",
          projectId,
          title: selectedOption.name,
          aspectRatio: "16:9",
          frames: selectedOption.frames,
        });
        await onSave({ ...frames[0], frames });
        return;
      }
      await onSave({
        assetId,
        type: kind,
        label: name.trim() || selectedOption?.name || (selectedMedia ? mediaDisplayName(selectedMedia) : "") || editing?.label || "",
        tag: name,
        referenceId: editing?.id,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "That reference could not be saved.");
      setBusy(false);
    }
  }

  function optionButton(option: ReferenceOption) {
    return (
      <button
        key={option.key}
        type="button"
        className={option.key === selectedKey ? "is-selected" : ""}
        data-testid={option.storyboardId ? `film-reference-choice-storyboard-${option.storyboardId}` : `film-reference-choice-${option.assetId}`}
        data-frames={(option.frames || []).map((frame) => frame.assetId).join(",")}
        onClick={() => choose(option)}
      >
        {option.thumbReady === false || !option.thumbAssetId ? null : (
          <img
            src={api.assetThumbUrl(option.thumbAssetId, option.thumbProjectId || projectId)}
            alt=""
          />
        )}
        <span>{option.name}</span>
      </button>
    );
  }

  const emptyMessage = isEntityKind(kind)
    ? `Nothing saved as ${TYPES.find((row) => row[0] === kind)?.[1]} yet.`
    : `No ${TYPES.find((row) => row[0] === kind)?.[1]} assets yet.`;

  return (
    <div className="prompt-guide" role="presentation">
      <button type="button" className="prompt-guide__backdrop" aria-label="Close" onClick={onClose} />
      <div className="prompt-guide__panel" role="dialog" aria-modal="true" aria-label="References" data-testid="film-reference-modal">
        <header>
          <h2>References</h2>
          <button type="button" aria-label="Close" data-testid="film-reference-close" onClick={onClose}>
            X
          </button>
        </header>
        <div className="prompt-guide__body">
          <div className="film-reference__types" role="tablist">
            {TYPES.map(([id, label]) => (
              <button key={id} type="button" className={kind === id ? "is-selected" : ""} onClick={() => switchKind(id)}>
                {label}
              </button>
            ))}
          </div>
          <div className="film-reference__choices" data-testid="film-reference-asset">
            {isEntityKind(kind) ? (
              loadingEntities && allOptions.length === 0 ? (
                <p className="film-reference__empty">Loading…</p>
              ) : allOptions.length === 0 ? (
                <p className="film-reference__empty">{emptyMessage}</p>
              ) : (
                GROUP_HEADINGS.map(([groupKey, heading]) => {
                  const rows = groups[groupKey];
                  if (!rows.length) return null;
                  const label = kind === "environment" && groupKey === "project" ? "ENVIRONMENT CREATOR" : heading;
                  return (
                    <div key={groupKey} className="film-reference__group">
                      <p className="film-reference__group-head">{label}</p>
                      {rows.map(optionButton)}
                    </div>
                  );
                })
              )
            ) : mediaChoices.length === 0 ? (
              <p className="film-reference__empty">{emptyMessage}</p>
            ) : (
              mediaChoices.map((asset) => (
                <button
                  key={asset.id}
                  type="button"
                  className={asset.id === selectedKey ? "is-selected" : ""}
                  data-testid={`film-reference-choice-${asset.id}`}
                  onClick={() => chooseMedia(asset)}
                >
                  <img src={api.assetThumbUrl(asset.id, projectId) || api.assetUrl(asset.id, null, projectId)} alt="" />
                  <span>{mediaDisplayName(asset)}</span>
                </button>
              ))
            )}
          </div>
          <label className="film-timeline__field">
            Name
            <input
              value={name}
              data-testid="film-reference-tag"
              onChange={(event) =>
                setAliases((current) => ({ ...current, [selectedKey]: event.target.value }))
              }
              placeholder={kind === "environment" ? "Stars" : "Cade"}
            />
          </label>
          <p className="film-reference__resolved" data-testid="film-reference-resolved">
            {preview && (selectedOption || selectedMedia) ? `${preview}` : "Resolved reference"}
          </p>
          {error ? <p className="film-timeline__error">{error}</p> : null}
        </div>
        <footer>
          <span>{editing ? "Update this reference" : "Add this reference"}</span>
          <button type="button" data-testid="film-reference-save" disabled={busy} onClick={() => void save()}>
            {editing ? "Update Reference" : "Add Reference"}
          </button>
        </footer>
      </div>
    </div>
  );
}
