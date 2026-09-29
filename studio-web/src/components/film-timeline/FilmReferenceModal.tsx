import { useEffect, useMemo, useState } from "react";
import type { Asset } from "../../types";

export type FilmReference = {
  id: string;
  type: string;
  label: string;
  assetId: string;
  tag?: string;
  inherited?: boolean;
};

const TYPES = [
  ["character", "Character", "@"],
  ["environment", "Environment", "#"],
  ["prop", "Prop", "%"],
  ["video", "Video", "*"],
  ["audio", "Audio", "&"],
] as const;

type Kind = (typeof TYPES)[number][0];

function kindForAsset(asset: Asset | undefined): Kind {
  const kind = String(asset?.kind || "").toLowerCase();
  if (kind === "video") return "video";
  if (kind === "audio") return "audio";
  return "character";
}

export function FilmReferenceModal({
  assets,
  references,
  initialAssetId,
  editId,
  onClose,
  onSave,
}: {
  assets: Asset[];
  references: FilmReference[];
  initialAssetId?: string;
  editId?: string;
  onClose: () => void;
  onSave: (body: { assetId: string; type: string; label: string; tag: string; referenceId?: string }) => Promise<void>;
}) {
  const editing = references.find((item) => item.id === editId) || null;
  const starter = assets.find((item) => item.id === (editing?.assetId || initialAssetId)) || null;
  const [kind, setKind] = useState<Kind>(editing?.type && TYPES.some((row) => row[0] === editing.type) ? (editing.type as Kind) : kindForAsset(starter || undefined));
  const [assetId, setAssetId] = useState(editing?.assetId || initialAssetId || "");
  const [name, setName] = useState(editing?.tag || editing?.label || "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const choices = useMemo(() => {
    return assets.filter((asset) => {
      const media = String(asset.kind || "").toLowerCase();
      if (kind === "video") return media === "video";
      if (kind === "audio") return media === "audio";
      return media === "image" || media === "";
    });
  }, [assets, kind]);
  const selected = assets.find((item) => item.id === assetId) || null;
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
    if (!assetId) {
      setError("Choose an asset.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await onSave({
        assetId,
        type: kind,
        label: name.trim() || selected?.filename || editing?.label || "",
        tag: name,
        referenceId: editing?.id,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "That reference could not be saved.");
      setBusy(false);
    }
  }

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
              <button key={id} type="button" className={kind === id ? "is-selected" : ""} onClick={() => setKind(id)}>
                {label}
              </button>
            ))}
          </div>
          <label className="film-timeline__field">
            Asset
            <select value={assetId} data-testid="film-reference-asset" onChange={(event) => setAssetId(event.target.value)}>
              <option value="">Choose an asset</option>
              {choices.map((asset) => (
                <option key={asset.id} value={asset.id}>
                  {asset.filename || asset.id}
                </option>
              ))}
            </select>
          </label>
          <label className="film-timeline__field">
            Name
            <input value={name} data-testid="film-reference-tag" onChange={(event) => setName(event.target.value)} placeholder={kind === "environment" ? "Stars" : "Cade"} />
          </label>
          <p className="film-reference__resolved" data-testid="film-reference-resolved">
            {preview && selected ? `${preview}` : "Resolved reference"}
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
