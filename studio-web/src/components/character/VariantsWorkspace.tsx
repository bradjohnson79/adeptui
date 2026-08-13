/**
 * VariantsWorkspace — Phase 6 creator-first Variants panel.
 *
 * Shows the immutable Original canonical Character Sheet plus up to 12
 * variants. Each variant is a wardrobe/look change that preserves the locked
 * identity (face/hair/eyes/body/silhouette) because variant generation is
 * reference-locked to the Original canonical sheet.
 *
 * Creator-first: large buttons, generous whitespace, plain language, (?) tips.
 * Reuses shared `characterCore.css` classes for a matching look.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api, type CharacterVariant } from "../../api";
import "./characterCore.css";

type Props = {
  projectId: string;
  characterId: string;
  /** When false, the panel disables everything (character not saved yet). */
  enabled: boolean;
};

type VariantList = {
  characterId: string;
  identityId: string;
  versionId: string;
  original: {
    id: string | null;
    name: string;
    description: string;
    characterSheetAssetId: string | null;
    isOriginal: true;
    immutable: true;
  };
  variants: CharacterVariant[];
  maxVariants: number;
  canGenerate: boolean;
};

const POLL_INTERVAL_MS = 2500;
const POLL_MAX_ATTEMPTS = 120;

export function VariantsWorkspace({ projectId, characterId, enabled }: Props) {
  const [list, setList] = useState<VariantList | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  // New-variant form state.
  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [creating, setCreating] = useState(false);

  // Per-variant action state.
  const [busy, setBusy] = useState<Record<string, boolean>>({});
  const pollingRef = useRef(false);

  const refresh = useCallback(async () => {
    if (!projectId || !characterId) return;
    setLoading(true);
    setError("");
    try {
      const data = (await api.listCharacterVariants(projectId, characterId)) as VariantList;
      setList(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load variants.");
    } finally {
      setLoading(false);
    }
  }, [projectId, characterId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const hasCanonical = !!list?.canGenerate && !!list?.original.characterSheetAssetId;
  const panelEnabled = enabled && hasCanonical;
  const variantCount = list?.variants.length ?? 0;
  const maxVariants = list?.maxVariants ?? 12;
  const atLimit = variantCount >= maxVariants;

  const setVariantBusy = useCallback((id: string, v: boolean) => {
    setBusy((prev) => ({ ...prev, [id]: v }));
  }, []);

  const pollVariant = useCallback(
    async (variantId: string, attemptsLeft: number) => {
      if (attemptsLeft <= 0 || !pollingRef.current) return;
      try {
        const adv = await api.advanceCharacterVariant(projectId, characterId, variantId);
        const gen = (adv.generation || {}) as { status?: string; sheetAssetId?: string | null };
        if (gen.status === "done" || gen.sheetAssetId) {
          pollingRef.current = false;
          await refresh();
          setNotice("Variant look ready.");
          return;
        }
        if (gen.status === "failed") {
          pollingRef.current = false;
          await refresh();
          setNotice(gen.status ? "Variant generation failed." : "Variant generation failed.");
          return;
        }
      } catch {
        // transient; keep polling
      }
      setTimeout(() => void pollVariant(variantId, attemptsLeft - 1), POLL_INTERVAL_MS);
    },
    [projectId, characterId, refresh],
  );

  const handleCreate = useCallback(async () => {
    const name = newName.trim();
    if (!name || !panelEnabled || atLimit) return;
    setCreating(true);
    setError("");
    setNotice("");
    try {
      await api.createCharacterVariant(projectId, characterId, {
        name,
        description: newDescription.trim(),
      });
      setNewName("");
      setNewDescription("");
      await refresh();
      setNotice(`Variant "${name}" added. Generate it when ready.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not add variant.");
    } finally {
      setCreating(false);
    }
  }, [newName, newDescription, panelEnabled, atLimit, projectId, characterId, refresh]);

  const handleGenerate = useCallback(
    async (variantId: string) => {
      if (!panelEnabled) return;
      setVariantBusy(variantId, true);
      setError("");
      setNotice("Generating variant look…");
      try {
        await api.generateCharacterVariant(projectId, characterId, variantId);
        await refresh();
        pollingRef.current = true;
        void pollVariant(variantId, POLL_MAX_ATTEMPTS);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not start variant generation.");
        setVariantBusy(variantId, false);
      }
    },
    [panelEnabled, projectId, characterId, refresh, pollVariant, setVariantBusy],
  );

  const handleAdvance = useCallback(
    async (variantId: string) => {
      setVariantBusy(variantId, true);
      try {
        await api.advanceCharacterVariant(projectId, characterId, variantId);
        await refresh();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not refresh variant.");
      } finally {
        setVariantBusy(variantId, false);
      }
    },
    [projectId, characterId, refresh, setVariantBusy],
  );

  const handleDelete = useCallback(
    async (variantId: string, name: string) => {
      const confirmed = window.confirm(
        `Delete variant "${name}"? The Original look is never affected.`,
      );
      if (!confirmed) return;
      setVariantBusy(variantId, true);
      try {
        await api.deleteCharacterVariant(projectId, characterId, variantId);
        await refresh();
        setNotice(`Variant "${name}" deleted. Original is untouched.`);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not delete variant.");
      } finally {
        setVariantBusy(variantId, false);
      }
    },
    [projectId, characterId, refresh, setVariantBusy],
  );

  return (
    <div className="character-core" data-testid="variants-workspace">
      <div className="character-core__section">
        <h3 className="character-core__section-title">
          Variants{" "}
          <span className="character-core__tip" title="Alternate looks for this character that keep the same face, hair, eyes, and body. The Original is locked and never changes.">
            (?)
          </span>
        </h3>
        <p className="character-core__hint">
          The Original is your character&apos;s locked look. Add up to {maxVariants} variants to try
          different outfits and styling — identity stays the same.
        </p>

        {!enabled ? (
          <p className="character-core__hint" data-testid="variants-disabled-unsaved">
            Save your character first to start creating variants.
          </p>
        ) : !hasCanonical ? (
          <p className="character-core__hint" data-testid="variants-disabled-no-sheet">
            Generate and approve the Original character sheet first — variants are locked to that look.
          </p>
        ) : null}

        {loading ? <p className="character-core__hint">Loading variants…</p> : null}
        {error ? (
          <p className="character-core__hint" style={{ color: "#f08787" }} data-testid="variants-error">
            {error}
          </p>
        ) : null}
        {notice ? (
          <p className="character-core__hint" data-testid="variants-notice">
            {notice}
          </p>
        ) : null}

        {/* Original (immutable) */}
        {list ? (
          <div className="character-core__candidates" data-testid="variants-original-grid">
            <VariantCard
              label={list.original.name}
              description={list.original.description}
              assetId={list.original.characterSheetAssetId}
              isOriginal
              immutable
            />
            {list.variants.map((v) => (
              <VariantCard
                key={v.id}
                label={v.name}
                description={v.description}
                assetId={v.characterSheetAssetId}
                generating={v.generationStatus === "generating"}
                failed={v.generationStatus === "failed"}
                error={v.generationError}
                disabled={!panelEnabled}
                busy={!!busy[v.id]}
                onGenerate={() => void handleGenerate(v.id)}
                onRefresh={() => void handleAdvance(v.id)}
                onDelete={() => void handleDelete(v.id, v.name)}
              />
            ))}
          </div>
        ) : null}

        {/* Add variant form */}
        <div className="character-core__generate" style={{ marginTop: 16 }}>
          <div className="character-core__field">
            <label className="character-core__label">
              Variant name <em>*</em>
            </label>
            <input
              type="text"
              value={newName}
              disabled={!panelEnabled || atLimit || creating}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="e.g. Winter Coat, Battle Armor, Formal Gown"
              data-testid="variants-new-name"
            />
          </div>
          <div className="character-core__field">
            <label className="character-core__label">
              Describe this look <span className="character-core__optional">(optional)</span>
            </label>
            <textarea
              value={newDescription}
              disabled={!panelEnabled || atLimit || creating}
              onChange={(e) => setNewDescription(e.target.value)}
              placeholder="Describe the wardrobe/styling change. Identity stays locked."
              data-testid="variants-new-description"
            />
          </div>
          <button
            type="button"
            className="character-core__button primary"
            disabled={!panelEnabled || atLimit || creating || !newName.trim()}
            onClick={() => void handleCreate()}
            data-testid="variants-create"
          >
            {creating ? "Adding…" : atLimit ? "Variant limit reached" : "Add Variant"}
          </button>
          <p className="character-core__hint">
            {variantCount} of {maxVariants} variants used (plus the Original).
          </p>
        </div>
      </div>
    </div>
  );
}

type CardProps = {
  label: string;
  description: string;
  assetId?: string | null;
  isOriginal?: boolean;
  immutable?: boolean;
  generating?: boolean;
  failed?: boolean;
  error?: string | null;
  disabled?: boolean;
  busy?: boolean;
  onGenerate?: () => void;
  onRefresh?: () => void;
  onDelete?: () => void;
};

function VariantCard(props: CardProps) {
  const {
    label,
    description,
    assetId,
    isOriginal,
    immutable,
    generating,
    failed,
    error,
    disabled,
    busy,
    onGenerate,
    onRefresh,
    onDelete,
  } = props;
  const src = assetId ? api.assetUrl(assetId) : "";
  return (
    <div
      className={`character-core__candidate${isOriginal ? " is-selected" : ""}`}
      data-testid={isOriginal ? "variants-original-card" : "variants-variant-card"}
    >
      <div className="character-core__candidate-media">
        {src ? (
          <img src={src} alt={label} loading="lazy" />
        ) : (
          <div className="character-core__candidate-placeholder">
            {generating ? "Generating…" : failed ? "Failed" : isOriginal ? "No Original sheet" : "Not generated yet"}
          </div>
        )}
      </div>
      <div className="character-core__candidate-meta">
        <span className="character-core__candidate-prov">
          {isOriginal ? "ORIGINAL · LOCKED" : label}
        </span>
        {description ? (
          <p className="character-core__hint" style={{ margin: 0 }}>
            {description}
          </p>
        ) : null}
        {failed && error ? (
          <p className="character-core__hint" style={{ color: "#f08787", margin: 0 }}>
            {error}
          </p>
        ) : null}
        {!isOriginal ? (
          <div className="character-core__reference-actions" style={{ marginTop: 6 }}>
            {!assetId && !generating ? (
              <button
                type="button"
                className="character-core__button primary"
                disabled={disabled || busy}
                onClick={onGenerate}
                data-testid="variant-generate"
              >
                {busy ? "Starting…" : "Generate Variant"}
              </button>
            ) : null}
            {generating ? (
              <button
                type="button"
                className="character-core__button"
                disabled={busy}
                onClick={onRefresh}
                data-testid="variant-refresh"
              >
                Refresh
              </button>
            ) : null}
            {!immutable ? (
              <button
                type="button"
                className="character-core__button danger"
                disabled={busy}
                onClick={onDelete}
                data-testid="variant-delete"
              >
                Delete
              </button>
            ) : null}
          </div>
        ) : (
          <p className="character-core__hint" style={{ margin: 0 }}>
            This look is locked. It never changes.
          </p>
        )}
      </div>
    </div>
  );
}
