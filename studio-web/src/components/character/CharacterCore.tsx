/**
 * CharacterCore — the single shared Character Profile workflow composed from the
 * shared building blocks. Used by BOTH the Co-Director Express surface and the
 * standalone Character Creator so they share schema, hydration, and behavior.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../api";
import { useOpenCoDirector } from "../CoDirector";
import { Dialog } from "../ui/Dialog";
import { LibraryQuickPreviewModal, type LibraryQuickPreviewAsset } from "../library/LibraryQuickPreviewModal";
import { CharacterActions } from "./CharacterActions";
import { CharacterActiveCrsCard } from "./CharacterActiveCrsCard";
import { CharacterProfileForm } from "./CharacterProfileForm";
import { CharacterReferenceControl } from "./CharacterReferenceControl";
import { CharacterV2Studio } from "./CharacterV2Studio";
import {
  DEFAULT_CHARACTER_GENERATOR_PLAN,
  buildGeneratorSourcesPayload,
  hydratePlanFromPreferences,
  type CharacterGeneratorPlan,
} from "./characterGeneratorPlan";
import { candidateAssetId, resolveActiveCrsCard } from "./activeCrsCard";
import { approvedHistoricalRevisions, type CharacterCandidate, type GeneratorOption } from "./types";
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
  /** Express (Co-Director) hides Close-up and generator internals. */
  mode?: "express" | "standard";
};

export function CharacterCore({ projectId, characterId, renderAdvanced, onDeleted, autoFocusName, mode = "standard" }: Props) {
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
  const [crsApprovedAssetId, setCrsApprovedAssetId] = useState<string>("");
  const [previewAsset, setPreviewAsset] = useState<LibraryQuickPreviewAsset | null>(null);
  const [approveTarget, setApproveTarget] = useState<CharacterCandidate | null>(null);
  const [rejectTarget, setRejectTarget] = useState<CharacterCandidate | null>(null);
  const [crsActionBusy, setCrsActionBusy] = useState(false);
  const retryHandlerRef = useRef<((candidate: CharacterCandidate) => void) | null>(null);
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
    setCrsApprovedAssetId("");
    void api
      .getCharacterCrs(projectId, characterId)
      .then((res) => {
        if (cancelled) return;
        const rev = (res as { crs_revision?: number; crsRevision?: number })?.crs_revision
          ?? (res as { crsRevision?: number })?.crsRevision;
        if (typeof rev === "number" && rev > 0) setCrsRevision(rev);
        const approvedId = String(
          (res as { approved_reference_asset_id?: string; approvedReferenceAssetId?: string })
            .approved_reference_asset_id
            || (res as { approvedReferenceAssetId?: string }).approvedReferenceAssetId
            || "",
        ).trim();
        if (approvedId) setCrsApprovedAssetId(approvedId);
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
        setNotice("That look is still generating. Wait for it to finish, then approve it.");
        setApproveTarget(null);
        return;
      }
      setNotice("");
      setCrsActionBusy(true);
      try {
        const result = await api.approveCharacterCandidate(projectId, characterId, {
          assetId,
          referenceRole: "hero_identity",
          sourceType: candidate.generator || candidate.provider ? "generation" : "generation",
          notes: `Approved character sheet ${candidate.label || ""}`.trim(),
          ownerConfirmed: true,
        });
        const rev =
          (result as { crsRevision?: number; crs_revision?: number })?.crsRevision
          ?? (result as { crs_revision?: number })?.crs_revision;
        if (typeof rev === "number") setCrsRevision(rev);
        const approvedId = String(
          (result as { approvedSheetAssetId?: string; assetId?: string }).approvedSheetAssetId
          || (result as { assetId?: string }).assetId
          || assetId,
        ).trim();
        if (approvedId) setCrsApprovedAssetId(approvedId);
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
      } finally {
        setCrsActionBusy(false);
        setApproveTarget(null);
      }
    },
    [projectId, characterId, profile, cp],
  );

  const requestApprove = useCallback((candidate: CharacterCandidate) => {
    const assetId = candidate.sheetAssetId || candidate.assetId;
    if (!assetId) {
      setNotice("That look is still generating. Wait for it to finish.");
      return;
    }
    setApproveTarget(candidate);
  }, []);

  const requestReject = useCallback((candidate: CharacterCandidate) => {
    setRejectTarget(candidate);
  }, []);

  const handleReject = useCallback(
    async (candidate: CharacterCandidate) => {
      const assetId = candidate.sheetAssetId || candidate.assetId || "";
      // Reject-during-gen: a generating draft has no asset yet, but it has a
      // jobId. The backend reject path matches by candidateId (jobId), cancels
      // the in-flight Comfy job (POST /interrupt), and removes the placeholder
      // from the pack — so the creator can cancel a stuck generation.
      const candidateKey =
        (candidate as { id?: string; jobId?: string }).id
        || (candidate as { jobId?: string }).jobId
        || "";
      if (!assetId && !candidateKey) {
        setNotice("This draft has no asset or job to reject yet.");
        setRejectTarget(null);
        return;
      }
      setNotice("");
      setCrsActionBusy(true);
      try {
        await api.rejectCharacterCandidate(projectId, characterId, {
          assetId,
          candidateId: candidateKey,
        });
        // Remove the rejected candidate by assetId OR candidateKey (jobId) so a
        // generating draft with no asset is still cleared from the grid.
        const matchId = assetId || candidateKey;
        const isMatch = (c: CharacterCandidate) => {
          const a = candidateAssetId(c);
          if (a && a === matchId) return true;
          const cId = (c as { id?: string; jobId?: string }).id || (c as { jobId?: string }).jobId || "";
          return Boolean(cId) && cId === matchId;
        };
        setCandidates((prev) => prev.filter((c) => !isMatch(c)));
        setHistory((prev) => prev.filter((c) => !isMatch(c)));
        await cp.refresh();
        setNotice("Draft Character Reference Sheet rejected.");
      } catch (e) {
        setNotice(e instanceof Error ? e.message : "Reject failed");
      } finally {
        setCrsActionBusy(false);
        setRejectTarget(null);
      }
    },
    [projectId, characterId, cp],
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
          ownerConfirmed: true,
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

  const approvedAssetId = crsApprovedAssetId || hero?.asset_id || "";
  const approvedHistory = useMemo(
    () => approvedHistoricalRevisions(history, approvedAssetId),
    [history, approvedAssetId],
  );
  const approvedMatch = useMemo(() => {
    if (!approvedAssetId) return null;
    return (
      candidates.find((c) => candidateAssetId(c) === approvedAssetId)
      || history.find((c) => candidateAssetId(c) === approvedAssetId)
      || null
    );
  }, [approvedAssetId, candidates, history]);
  const draftSheet = candidates[0] || null;
  const resolvedCrs = useMemo(
    () =>
      resolveActiveCrsCard({
        approvedAssetId,
        crsRevision,
        draft: draftSheet,
        approvedMatch,
        characterName: profile?.name,
      }),
    [approvedAssetId, approvedMatch, crsRevision, draftSheet, profile?.name],
  );
  const activeSheet = resolvedCrs.hero;
  const displayRevision = resolvedCrs.revision;
  const activeStatus = resolvedCrs.status;
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
        activeStatus === "approved" ? "Approved" : "Draft",
      ].filter(Boolean);
      setPreviewAsset({
        id: assetId,
        kind: "image",
        name: bits.join(" — "),
        filename: match?.label || undefined,
      });
    },
    [activeStatus, candidates, profile?.name, crsRevision],
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
        <h3 className="character-core__section-title">{mode === "express" ? "Character views" : t("sheet")}</h3>
        <CharacterV2Studio
          projectId={projectId}
          characterId={characterId}
          mode={mode}
          saved={saved}
        />
        {resolvedCrs.showBoth && resolvedCrs.canon ? (
          <CharacterActiveCrsCard
            hero={resolvedCrs.canon}
            characterName={profile?.name || ""}
            status="approved"
            revision={typeof crsRevision === "number" ? crsRevision : displayRevision}
            generatorLabel={
              resolvedCrs.canon.provenance
              || resolvedCrs.canon.generator
              || (resolvedCrs.canon.model ? String(resolvedCrs.canon.model) : null)
            }
            conditioningLabel={
              resolvedCrs.canon.conditioningMode === "REFERENCE_CONDITIONED"
                ? "Uses your photo"
                : resolvedCrs.canon.conditioningMode === "PROFILE_GUIDED"
                  ? "From the profile"
                  : null
            }
            testId="character-active-crs-canon"
            title="Approved Character Reference Sheet"
            onPreview={openPreview}
            disabled={crsActionBusy}
            onApprove={requestApprove}
          />
        ) : null}
        <CharacterActiveCrsCard
          hero={resolvedCrs.showBoth ? resolvedCrs.draft : activeSheet}
          characterName={profile?.name || ""}
          status={resolvedCrs.showBoth ? "draft" : activeStatus}
          revision={typeof displayRevision === "number" ? displayRevision : crsRevision}
          generatorLabel={generatorLabel}
          conditioningLabel={conditioningLabel}
          testId={resolvedCrs.showBoth ? "character-active-crs-draft" : "character-active-crs"}
          title={
            resolvedCrs.showBoth
              ? "Draft Character Reference Sheet"
              : activeStatus === "approved"
                ? "Approved Character Reference Sheet"
                : undefined
          }
          onPreview={openPreview}
          disabled={crsActionBusy}
          onApprove={requestApprove}
          onReject={requestReject}
        />
        {productionReady && atName ? (
          <p className="character-core__hint" data-testid="character-approved-banner">
            {profile?.name || "Character"} is ready. {atName}
          </p>
        ) : null}
        {approvedHistory.length ? (
          <details className="character-core__history" data-testid="character-crs-history">
            <summary>Advanced — Previous versions</summary>
            <ul className="character-core__history-list">
              {approvedHistory.slice(0, 8).map((item, i) => {
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
      <Dialog
        open={!!approveTarget}
        title={`Approve ${profile?.name || "this character"}'s Character Reference Sheet?`}
        primaryLabel="Approve"
        secondaryLabel="Cancel"
        closeOnPrimary={false}
        primaryDisabled={crsActionBusy}
        primaryLoading={crsActionBusy}
        testId="character-approve-crs-dialog"
        onClose={() => {
          if (!crsActionBusy) setApproveTarget(null);
        }}
        onPrimary={() => {
          if (approveTarget) void handleApprove(approveTarget);
        }}
      >
        This becomes the look for {profile?.name || "this character"}. Cancel or dismiss keeps the draft unchanged.
      </Dialog>
      <Dialog
        open={!!rejectTarget}
        title={`Reject ${profile?.name || "this character"}'s draft Character Reference Sheet?`}
        primaryLabel="Reject"
        secondaryLabel="Cancel"
        danger
        closeOnPrimary={false}
        primaryDisabled={crsActionBusy}
        primaryLoading={crsActionBusy}
        testId="character-reject-crs-dialog"
        onClose={() => {
          if (!crsActionBusy) setRejectTarget(null);
        }}
        onPrimary={() => {
          if (rejectTarget) void handleReject(rejectTarget);
        }}
      >
        This deletes only that draft candidate. The approved Character Reference Sheet is not touched. Cancel or dismiss keeps the draft.
      </Dialog>
    </div>
  );
}