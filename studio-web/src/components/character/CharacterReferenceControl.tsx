/**
 * CharacterReferenceControl — shared reference-image control.
 * Thumbnail + Upload / Add from Library / Change / Remove, plus the explicit
 * "Use as Character Identity" action. Reuse of CharacterReferenceAssetPicker.
 *
 * Use as Character Identity is a CANDIDATE path, not auto-approve:
 * reference → mark as identity candidate → user explicitly approves → hero_identity.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../api";
import { CharacterReferenceAssetPicker } from "../CoDirector/characters/CharacterReferenceAssetPicker";
import type { LibraryAsset } from "../CoDirector/library/assetModel";
import type { CharacterReference } from "./types";
import { getReferenceImage } from "./useCharacterProfile";

type Props = {
  projectId: string;
  characterId: string;
  references: CharacterReference[];
  disabled?: boolean;
  onChanged: () => void | Promise<void>;
  /** Called when user chooses to use the reference as the identity candidate. */
  onUseAsIdentity?: (assetId: string, sourceType: "upload" | "library") => void | Promise<void>;
};

export function CharacterReferenceControl({
  projectId,
  characterId,
  references,
  disabled,
  onChanged,
  onUseAsIdentity,
}: Props) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [useAsIdentity, setUseAsIdentity] = useState(false);
  const fileRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    setUseAsIdentity(false);
  }, [characterId]);

  const referenceImage = useMemo(() => getReferenceImage(references), [references]);
  const refAssetId = referenceImage?.asset_id ?? null;
  const previewSrc = refAssetId ? api.assetUrl(refAssetId) : "";

  const attach = async (assetId: string, sourceType: "upload" | "library") => {
    setBusy(true);
    setError(null);
    try {
      await api.attachCharacterReference(projectId, characterId, {
        asset_id: assetId,
        reference_role: "reference_image",
        source_type: sourceType,
        canonical: false,
      });
      await onChanged();
      if (useAsIdentity && onUseAsIdentity) {
        await onUseAsIdentity(assetId, sourceType);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Attach failed");
    } finally {
      setBusy(false);
    }
  };

  const handleUpload = async (file: File) => {
    setBusy(true);
    setError(null);
    try {
      const asset = await api.uploadAsset(projectId, file, "character_reference", "image");
      await attach(asset.id, "upload");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
      setBusy(false);
    }
  };

  const handleRemove = async () => {
    if (!refAssetId) return;
    setBusy(true);
    setError(null);
    try {
      await api.detachCharacterReference(projectId, characterId, refAssetId);
      await onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Remove failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="character-core__reference">
      <span className="character-core__label">
        Character Reference <span className="character-core__optional">(optional)</span>
      </span>

      {previewSrc ? (
        <div className="character-core__reference-preview" data-testid="character-reference-preview">
          <img src={previewSrc} alt="Character reference" />
        </div>
      ) : (
        <p className="character-core__hint" data-testid="character-reference-empty">
          No reference yet. Add one to guide the character's look.
        </p>
      )}

      <div className="character-core__reference-actions">
        <button
          type="button"
          className="character-core__button"
          data-testid="character-reference-upload"
          disabled={disabled || busy}
          onClick={() => fileRef.current?.click()}
        >
          {refAssetId ? "Change" : "Upload"}
        </button>
        <button
          type="button"
          className="character-core__button"
          data-testid="character-reference-library"
          disabled={disabled || busy}
          onClick={() => setPickerOpen(true)}
        >
          Add from Library
        </button>
        {refAssetId ? (
          <button
            type="button"
            className="character-core__button"
            data-testid="character-reference-remove"
            disabled={disabled || busy}
            onClick={() => void handleRemove()}
          >
            Remove
          </button>
        ) : null}
      </div>

      <label className="character-core__checkbox">
        <input
          type="checkbox"
          data-testid="character-use-as-identity"
          checked={useAsIdentity}
          disabled={disabled}
          onChange={(e) => setUseAsIdentity(e.target.checked)}
        />
        <span>
          Use as Character Identity{" "}
          <span className="character-core__tip" title="Use this image directly as the character's look, without AI generation. You'll confirm it before it's set.">
            (?)
          </span>
        </span>
      </label>

      {error ? (
        <p className="character-core__hint" style={{ color: "#f08787" }} data-testid="character-reference-error">
          {error}
        </p>
      ) : null}

      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        hidden
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) void handleUpload(f);
          e.target.value = "";
        }}
      />

      <CharacterReferenceAssetPicker
        projectId={projectId}
        currentAssetId={refAssetId}
        open={pickerOpen}
        busy={busy}
        onCancel={() => setPickerOpen(false)}
        onConfirm={(asset: LibraryAsset) => {
          setPickerOpen(false);
          void attach(asset.id, "library");
        }}
      />
    </div>
  );
}
