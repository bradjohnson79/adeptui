/**
 * CharacterCore — the single shared Character Profile workflow composed from the
 * shared building blocks. Used by BOTH the Co-Director Express surface and the
 * standalone Character Creator so they share schema, hydration, and behavior.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../api";
import { CharacterActions } from "./CharacterActions";
import { CharacterCandidateGrid } from "./CharacterCandidateGrid";
import { CharacterGeneratorPanel } from "./CharacterGeneratorPanel";
import { CharacterProfileForm } from "./CharacterProfileForm";
import { CharacterReferenceControl } from "./CharacterReferenceControl";
import { CharacterSheetGenerator } from "./CharacterSheetGenerator";
import {
  DEFAULT_CHARACTER_GENERATOR_PLAN,
  buildGeneratorSourcesPayload,
  hydratePlanFromPreferences,
  type CharacterGeneratorPlan,
} from "./characterGeneratorPlan";
import type { CharacterCandidate, GeneratorOption } from "./types";
import { getHeroIdentity, getReferenceImage, useCharacterProfile } from "./useCharacterProfile";
import "./characterCore.css";

type Props = {
  projectId: string;
  characterId: string;
  /** Optional advanced-workspace buttons rendered when the character is saved. */
  renderAdvanced?: (ctx: { characterId: string; saved: boolean }) => React.ReactNode;
  onDeleted?: () => void;
  /** When true, auto-focus the name field (new character). */
  autoFocusName?: boolean;
};

export function CharacterCore({ projectId, characterId, renderAdvanced, onDeleted, autoFocusName }: Props) {
  const { t } = useTranslation("characterCreator");
  const cp = useCharacterProfile(projectId, characterId);
  const { profile, references } = cp;

  const [plan, setPlan] = useState<CharacterGeneratorPlan>(DEFAULT_CHARACTER_GENERATOR_PLAN);
  const [localOptions, setLocalOptions] = useState<GeneratorOption[]>([]);
  const [apiOptions, setApiOptions] = useState<GeneratorOption[]>([]);
  const [candidates, setCandidates] = useState<CharacterCandidate[]>([]);
  const [notice, setNotice] = useState("");
  // CDX-006: explicit "Promote to Production" affordance after a look approval.
  const [promoting, setPromoting] = useState(false);
  const [promoted, setPromoted] = useState(false);
  const prevHeroAssetRef = useRef<string | null>(null);
  const retryHandlerRef = useRef<((candidate: CharacterCandidate) => void) | null>(null);
  const prefsHydratedRef = useRef(false);
  const prefsTimerRef = useRef<number | null>(null);
  const rawPrefsRef = useRef<unknown>(null);
  const packLoadedRef = useRef(false);
  const inventoryRef = useRef<{ localOptions: GeneratorOption[]; apiOptions: GeneratorOption[] } | null>(null);

  const hero = useMemo(() => getHeroIdentity(references), [references]);
  const referenceImage = useMemo(() => getReferenceImage(references), [references]);
  const hasReference = !!referenceImage?.asset_id;
  const selectedAssetId = hero?.asset_id ?? null;

  const saved = !!profile?.id;
  const canSave = !!profile?.name?.trim();

  const applyHydration = useCallback(
    (
      prefs: unknown,
      inv: { localOptions: GeneratorOption[]; apiOptions: GeneratorOption[] },
    ) => {
      const apiModels = inv.apiOptions.map((opt) => ({
        providerId: opt.providerId || "",
        modelId: opt.modelId || "",
        model: opt.id.includes(":") ? opt.id.split(":").slice(1).join(":") : opt.id,
        displayName: opt.label,
        capabilities: opt.capabilities || [],
        supportsReferences: !!opt.supportsReferences,
        availability: opt.availability || "Connected",
        executable: opt.executable,
        credits: opt.credits,
      }));
      setPlan(hydratePlanFromPreferences(prefs, inv.localOptions, apiModels));
    },
    [],
  );

  const handleInventory = useCallback(
    (inv: { localOptions: GeneratorOption[]; apiOptions: GeneratorOption[] }) => {
      inventoryRef.current = inv;
      setLocalOptions(inv.localOptions);
      setApiOptions(inv.apiOptions);
      if (packLoadedRef.current && rawPrefsRef.current) applyHydration(rawPrefsRef.current, inv);
      if (packLoadedRef.current) prefsHydratedRef.current = true;
    },
    [applyHydration],
  );

  useEffect(() => {
    prefsHydratedRef.current = false;
    packLoadedRef.current = false;
    rawPrefsRef.current = null;
    let cancelled = false;
    void (async () => {
      try {
        const res = await api.getCharacterVisualSheet(projectId, characterId);
        const pack = (res as { pack?: Record<string, unknown> }).pack || (res as Record<string, unknown>);
        const prefs = pack?.generatorPreferences || pack?.generatorSources;
        if (cancelled) return;
        rawPrefsRef.current = prefs || null;
        packLoadedRef.current = true;
        if (prefs && inventoryRef.current) applyHydration(prefs, inventoryRef.current);
        else setPlan(DEFAULT_CHARACTER_GENERATOR_PLAN);
        prefsHydratedRef.current = true;
      } catch {
        if (!cancelled) {
          packLoadedRef.current = true;
          prefsHydratedRef.current = true;
          setPlan(DEFAULT_CHARACTER_GENERATOR_PLAN);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId, characterId, applyHydration]);

  useEffect(() => {
    if (!prefsHydratedRef.current) return;
    if (prefsTimerRef.current) window.clearTimeout(prefsTimerRef.current);
    prefsTimerRef.current = window.setTimeout(() => {
      const payload = buildGeneratorSourcesPayload(plan);
      void api.saveCharacterVisualSheetPreferences(projectId, characterId, { generatorSources: payload }).catch(() => {
        /* prefs save is best-effort; generation still uses live UI state */
      });
    }, 400);
    return () => {
      if (prefsTimerRef.current) window.clearTimeout(prefsTimerRef.current);
    };
  }, [plan, projectId, characterId]);

  const handleApprove = useCallback(
    async (candidate: CharacterCandidate) => {
      const assetId = candidate.sheetAssetId || candidate.assetId;
      if (!assetId) {
        setNotice("That look is still generating. Wait for it to finish.");
        return;
      }
      if (hero?.asset_id) {
        const confirmed = window.confirm(
          `Replace ${profile?.name || "this character"}'s look with this one?`,
        );
        if (!confirmed) return;
      }
      setNotice("");
      try {
        await api.approveCharacterCandidate(projectId, characterId, {
          assetId,
          referenceRole: "hero_identity",
          sourceType: candidate.generator || candidate.provider ? "generation" : "generation",
          notes: `Approved character sheet ${candidate.label || ""}`.trim(),
        });
        try {
          await api.ownerApproveCharacterVisualSheet(projectId, characterId);
        } catch {
          // gate approval optional in embedded flow
        }
        await cp.refresh();
        setNotice("Character look saved.");
      } catch (e) {
        setNotice(e instanceof Error ? e.message : "Approve failed");
      }
    },
    [projectId, characterId, hero, profile, cp],
  );

  const handleUseAsIdentity = useCallback(
    async (assetId: string, sourceType: "upload" | "library") => {
      setNotice("");
      try {
        await api.approveCharacterCandidate(projectId, characterId, {
          assetId,
          referenceRole: "hero_identity",
          sourceType,
          notes: "Used reference image as character identity (no AI generation).",
        });
        await cp.refresh();
        setNotice("Reference set as this character's look.");
      } catch (e) {
        setNotice(e instanceof Error ? e.message : "Could not use as identity.");
      }
    },
    [projectId, characterId, cp],
  );

  useEffect(() => {
    const id = hero?.asset_id ?? null;
    if (prevHeroAssetRef.current && prevHeroAssetRef.current !== id) setPromoted(false);
    prevHeroAssetRef.current = id;
  }, [hero?.asset_id]);

  const handlePromote = useCallback(async () => {
    setPromoting(true);
    setNotice("");
    try {
      await api.promoteCharacterIdentity(projectId, characterId);
      setPromoted(true);
      setNotice("Character promoted to Production — continuity, VisualIdentity, and the Production Bible updated.");
    } catch (e) {
      setNotice(e instanceof Error ? e.message : "Promote failed");
    } finally {
      setPromoting(false);
    }
  }, [projectId, characterId]);

  const handleSave = useCallback(async () => {
    const ok = await cp.save({
      name: profile?.name,
      gender_presentation: profile?.gender_presentation,
      visual_style: profile?.visual_style,
      description: profile?.description,
    });
    if (ok) setNotice("Character profile saved");
  }, [cp, profile]);

  const handleDelete = useCallback(async () => {
    const confirmed = window.confirm(
      `Delete ${profile?.name || "this character"}? This cannot be undone.`,
    );
    if (!confirmed) return;
    const ok = await cp.remove();
    if (ok) onDeleted?.();
  }, [cp, profile, onDeleted]);

  if (cp.loading && !profile) {
    return <p className="character-core__hint">Loading character…</p>;
  }

  return (
    <div className="character-core" data-testid="character-core">
      <div className="character-core__section">
        <h3 className="character-core__section-title">Character Profile</h3>
        <CharacterProfileForm
          profile={profile}
          autoFocusName={autoFocusName}
          onChange={(fields) => cp.patchDebounced(fields)}
        />
      </div>

      <div className="character-core__section">
        <h3 className="character-core__section-title">Character Reference</h3>
        <CharacterReferenceControl
          projectId={projectId}
          characterId={characterId}
          references={references}
          onChanged={cp.refresh}
          onUseAsIdentity={handleUseAsIdentity}
        />
      </div>

      <div className="character-core__section">
        <h3 className="character-core__section-title">{t("sheet")}</h3>
        <CharacterGeneratorPanel
          projectId={projectId}
          visualStyle={profile?.visual_style}
          hasReference={hasReference}
          value={plan}
          onChange={setPlan}
          onInventory={handleInventory}
        />
        <CharacterSheetGenerator
          projectId={projectId}
          characterId={characterId}
          profile={profile}
          plan={plan}
          localOptions={localOptions}
          apiOptions={apiOptions}
          hasReference={hasReference}
          onCandidates={setCandidates}
          retryHandlerRef={retryHandlerRef}
        />
        <CharacterCandidateGrid
          candidates={candidates}
          selectedAssetId={selectedAssetId}
          onApprove={(c) => void handleApprove(c)}
          onRetry={(c) => retryHandlerRef.current?.(c)}
        />
      </div>

      {notice ? (
        <p className="character-core__hint" data-testid="character-core-notice">
          {notice}
        </p>
      ) : null}
      {cp.error ? (
        <p className="character-core__hint" style={{ color: "#f08787" }} data-testid="character-core-error">
          {cp.error}
        </p>
      ) : null}

      {hero && !promoted ? (
        <div className="character-core__promote" data-testid="character-core-promote">
          <span>
            Look approved{profile?.name ? ` for ${profile.name}` : ""}. Promote to Production to sync continuity, VisualIdentity, and the Production Bible.
          </span>
          <button
            type="button"
            className="character-core__button"
            onClick={() => void handlePromote()}
            disabled={promoting}
            data-testid="character-core-promote-button"
          >
            {promoting ? "Promoting…" : "Promote to Production"}
          </button>
        </div>
      ) : null}

      <CharacterActions
        isSaved={saved}
        canSave={canSave}
        saving={cp.saving}
        onSave={() => void handleSave()}
        onReset={() => cp.reset()}
        onDelete={() => void handleDelete()}
      />

      {renderAdvanced ? (
        <div className="character-core__advanced-toggle">
          <h3 className="character-core__section-title">Advanced</h3>
          <div className="character-core__advanced-grid">{renderAdvanced({ characterId, saved })}</div>
        </div>
      ) : null}
    </div>
  );
}
