/**
 * CharacterCore — the single shared Character Profile workflow composed from the
 * shared building blocks. Used by BOTH the Co-Director Express surface and the
 * standalone Character Creator so they share schema, hydration, and behavior.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../api";
import { useOpenCoDirector } from "../CoDirector";
import { LibraryQuickPreviewModal, type LibraryQuickPreviewAsset } from "../library/LibraryQuickPreviewModal";
import { CharacterActions } from "./CharacterActions";
import { CharacterActiveCrsCard } from "./CharacterActiveCrsCard";
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

function candidateAssetId(c: CharacterCandidate | null | undefined): string {
  return String(c?.sheetAssetId || c?.assetId || "").trim();
}

export function CharacterCore({ projectId, characterId, renderAdvanced, onDeleted, autoFocusName }: Props) {
  const { t } = useTranslation("characterCreator");
  const openCoDirector = useOpenCoDirector();
  const cp = useCharacterProfile(projectId, characterId);
  const { profile, references } = cp;

  const [plan, setPlan] = useState<CharacterGeneratorPlan>(DEFAULT_CHARACTER_GENERATOR_PLAN);
  const [localOptions, setLocalOptions] = useState<GeneratorOption[]>([]);
  const [apiOptions, setApiOptions] = useState<GeneratorOption[]>([]);
  const [candidates, setCandidates] = useState<CharacterCandidate[]>([]);
  const [history, setHistory] = useState<CharacterCandidate[]>([]);
  const [profileDirty, setProfileDirty] = useState(false);
  const [notice, setNotice] = useState("");
  const [crsRevision, setCrsRevision] = useState<number | null>(null);
  const [previewAsset, setPreviewAsset] = useState<LibraryQuickPreviewAsset | null>(null);
  const retryHandlerRef = useRef<((candidate: CharacterCandidate) => void) | null>(null);
  const generateHandlerRef = useRef<(() => void) | null>(null);
  const prefsHydratedRef = useRef(false);
  const prefsTimerRef = useRef<number | null>(null);
  const rawPrefsRef = useRef<unknown>(null);
  const packLoadedRef = useRef(false);
  const inventoryRef = useRef<{ localOptions: GeneratorOption[]; apiOptions: GeneratorOption[] } | null>(null);

  const hero = useMemo(() => getHeroIdentity(references), [references]);
  const referenceImage = useMemo(() => getReferenceImage(references), [references]);
  const hasReference = !!referenceImage?.asset_id;
  const productionReady = (profile?.approval_status || "").toLowerCase() === "approved";

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
      if (packLoadedRef.current) applyHydration(rawPrefsRef.current, inv);
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
        if (inventoryRef.current) applyHydration(prefs || null, inventoryRef.current);
        else if (!prefs) setPlan(DEFAULT_CHARACTER_GENERATOR_PLAN);
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
    let cancelled = false;
    void api
      .getCharacterCrs(projectId, characterId)
      .then((res) => {
        if (cancelled) return;
        const rev = (res as { crs_revision?: number; crsRevision?: number })?.crs_revision
          ?? (res as { crsRevision?: number })?.crsRevision;
        if (typeof rev === "number" && rev > 0) setCrsRevision(rev);
      })
      .catch(() => {
        /* CRS endpoint may be empty before first Approve */
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, characterId, profile?.approval_status, hero?.asset_id]);

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
      if (hero?.asset_id && hero.asset_id !== assetId) {
        const confirmed = window.confirm(
          `Replace ${profile?.name || "this character"}'s approved Character Reference Sheet with this one?`,
        );
        if (!confirmed) return;
      }
      setNotice("");
      try {
        const result = await api.approveCharacterCandidate(projectId, characterId, {
          assetId,
          referenceRole: "hero_identity",
          sourceType: candidate.generator || candidate.provider ? "generation" : "generation",
          notes: `Approved character sheet ${candidate.label || ""}`.trim(),
        });
        const rev =
          (result as { crsRevision?: number; crs_revision?: number })?.crsRevision
          ?? (result as { crs_revision?: number })?.crs_revision;
        if (typeof rev === "number") setCrsRevision(rev);
        try {
          await api.ownerApproveCharacterVisualSheet(projectId, characterId);
        } catch {
          // gate approval optional in embedded flow
        }
        await cp.refresh();
        try {
          await api.promoteCharacterIdentity(projectId, characterId);
        } catch {
          // Bible sync is best-effort; Approve already registered the look.
        }
        const at = profile?.name?.trim() ? `@${profile.name.trim()}` : "@Character";
        setNotice(`${profile?.name || "Character"} is ready. ${at}`);
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

  const handleSave = useCallback(async () => {
    const ok = await cp.save({
      name: profile?.name,
      gender_presentation: profile?.gender_presentation,
      visual_style: profile?.visual_style,
      description: profile?.description,
    });
    if (ok) {
      setProfileDirty(false);
      setNotice("Character profile saved");
    }
  }, [cp, profile]);

  const handleReset = useCallback(() => {
    if (!profileDirty) return;
    cp.reset();
    setProfileDirty(false);
    setNotice("Character profile restored");
  }, [cp, profileDirty]);

  const handleDelete = useCallback(async () => {
    const confirmed = window.confirm(
      `Delete ${profile?.name || "this character"}? This cannot be undone.`,
    );
    if (!confirmed) return;
    const ok = await cp.remove();
    if (ok) onDeleted?.();
  }, [cp, profile, onDeleted]);

  const approvedSheet = useMemo((): CharacterCandidate | null => {
    if (!hero?.asset_id) return null;
    const match = candidates.find((c) => candidateAssetId(c) === hero.asset_id)
      || history.find((c) => candidateAssetId(c) === hero.asset_id);
    if (match) return { ...match, assetId: hero.asset_id, sheetAssetId: match.sheetAssetId || hero.asset_id };
    return {
      assetId: hero.asset_id,
      sheetAssetId: hero.asset_id,
      label: profile?.name || "Character Reference Sheet",
      status: "done",
      qualityTier: "2K",
    };
  }, [hero, candidates, history, profile?.name]);

  const draftSheet = useMemo((): CharacterCandidate | null => {
    const current = candidates[0];
    if (!current) return null;
    const id = candidateAssetId(current);
    if (hero?.asset_id && id === hero.asset_id) return null;
    return current;
  }, [candidates, hero]);

  const activeSheet = draftSheet || approvedSheet;
  const displayRevision = (activeSheet?.revision as number | undefined) ?? crsRevision;
  const activeStatus = draftSheet ? "draft" : approvedSheet ? "approved" : "none";
  const generatorLabel =
    activeSheet?.provenance ||
    activeSheet?.generator ||
    (activeSheet?.model ? String(activeSheet.model) : null);
  const conditioningLabel =
    activeSheet?.conditioningMode === "REFERENCE_CONDITIONED"
      ? "Uses your photo"
      : activeSheet?.conditioningMode === "PROFILE_GUIDED"
        ? "From the profile"
        : null;

  const openPreview = useCallback(
    (assetId: string) => {
      if (!assetId) return;
      const match = candidates.find((c) => candidateAssetId(c) === assetId);
      const bits = [
        profile?.name || "Character Reference Sheet",
        match?.provenance || match?.generator || "",
        match?.width && match?.height ? `${match.width}×${match.height}` : "",
        crsRevision != null ? `Revision ${crsRevision}` : "",
        productionReady && !draftSheet ? "Approved" : "Draft",
      ].filter(Boolean);
      setPreviewAsset({
        id: assetId,
        kind: "image",
        name: bits.join(" — "),
        filename: match?.label || undefined,
      });
    },
    [candidates, profile?.name, crsRevision, productionReady],
  );

  if (cp.loading && !profile) {
    return <p className="character-core__hint">Loading character…</p>;
  }

  const atName = profile?.name?.trim() ? `@${profile.name.trim()}` : null;

  return (
    <div className="character-core" data-testid="character-core">
      <div className="character-core__section">
        <h3 className="character-core__section-title">Character Profile</h3>
        <CharacterProfileForm
          profile={profile}
          autoFocusName={autoFocusName}
          onChange={(fields) => {
            setProfileDirty(true);
            cp.setLocal(fields);
          }}
        />
      </div>

      <div className="character-core__section">
        <h3 className="character-core__section-title">Character Reference</h3>
        <CharacterReferenceControl
          projectId={projectId}
          characterId={characterId}
          characterName={profile?.name}
          references={references}
          onChanged={cp.refresh}
          onUseAsIdentity={handleUseAsIdentity}
          onAskCoDirector={(prompt, opts) => openCoDirector(prompt, { autoSend: opts?.autoSend ?? false })}
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
          onHistory={setHistory}
          retryHandlerRef={retryHandlerRef}
          generateHandlerRef={generateHandlerRef}
        />
        <CharacterActiveCrsCard
          hero={activeSheet}
          characterName={profile?.name || ""}
          status={activeStatus}
          revision={typeof displayRevision === "number" ? displayRevision : crsRevision}
          generatorLabel={generatorLabel}
          conditioningLabel={conditioningLabel}
          onPreview={openPreview}
          onRegenerate={() => generateHandlerRef.current?.()}
          onApprove={(c) => void handleApprove(c)}
        />
        {productionReady && atName ? (
          <p className="character-core__hint" data-testid="character-approved-banner">
            {profile?.name || "Character"} is ready. {atName}
          </p>
        ) : null}
        {history.length ? (
          <details className="character-core__history" data-testid="character-crs-history">
            <summary>Advanced — Previous versions</summary>
            <ul className="character-core__history-list">
              {history.slice(0, 8).map((item, i) => {
                const id = candidateAssetId(item);
                return (
                  <li key={id || `hist-${i}`}>
                    <button
                      type="button"
                      className="character-core__button"
                      disabled={!id}
                      onClick={() => id && openPreview(id)}
                    >
                      Revision {item.revision ?? i + 1}
                      {item.provenance || item.generator ? ` — ${item.provenance || item.generator}` : ""}
                    </button>
                  </li>
                );
              })}
            </ul>
          </details>
        ) : null}
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

      <CharacterActions
        isSaved={saved}
        canSave={canSave}
        saving={cp.saving}
        dirty={profileDirty}
        onSave={() => void handleSave()}
        onReset={handleReset}
        onDelete={() => void handleDelete()}
      />

      {renderAdvanced ? (
        <div className="character-core__advanced-toggle">
          <h3 className="character-core__section-title">Advanced</h3>
          <div className="character-core__advanced-grid">{renderAdvanced({ characterId, saved })}</div>
        </div>
      ) : null}

      <LibraryQuickPreviewModal asset={previewAsset} onClose={() => setPreviewAsset(null)} />
    </div>
  );
}