/**
 * Shared Environment Creator surface (Express + Standard).
 * Creator-facing planning: optional reference, description, chars/props,
 * inherited Story theme, aspect, generator, compact plan summary, Generate.
 * Reuses useErsGeneration + ERSGenerationMonitor after Generate.
 * Scene Creator Standard is NOT production imagery — Image Generator is.
 * Env Creator = ERS / environment planning. Spatial Map stays shelved.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, api } from "../../../api";
import {
  ENVIRONMENT_NAME_ALREADY_EXISTS_MESSAGE,
  PROFILE_NAME_ALREADY_EXISTS,
  findVisibleNameCollision,
  normalizeProfileName,
} from "../../../creatorScope";
import { promptCanonicalEnvironmentTag } from "../../../creatorScope/identityTags";
import type { WorkSurfaceState } from "../AgentWorkSurface/types";
import { persistThenOpenSceneCreator } from "../SceneCreator/persistThenOpenSceneCreator";
import { GlobalScopeField } from "../../creator/GlobalScopeField";
import { EntityPicker } from "../SpatialMap/EntityPicker";
import { ERSGenerationMonitor } from "../SpatialMap/ERSGenerationMonitor";
import { useErsGeneration } from "../SpatialMap/useErsGeneration";
import "../SpatialMap/spatialMap.css";
import "../SceneCreator/sceneCreator.css";
import "../../character/characterCore.css";
import type { EnvironmentReferenceSheetSummary } from "../../../contracts/environmentReferenceSheet";
import {
  ERS_NOT_CREATED_MESSAGE,
  environmentDraftStatusLabel,
  environmentReferenceStatusLabel,
  isErsSnapshotSheet,
  resolveErsEditMasterId,
  ersListDisplayLabel,
  isOwnedEnvironmentDraft,
  isProjectEnvironmentReferenceSheet,
} from "./environmentReferenceState";
import { ErsEditModal } from "./ErsEditModal";
import {
  ErsSheetImagePreviewModal,
  type ErsSheetImagePreview,
} from "./ErsSheetImagePreviewModal";
import { ersEditPendingStatusLabel } from "./ersSubmitGate";
import {
  ENV_PROVIDER_UNAVAILABLE_MESSAGE,
  environmentApiProviderSlots,
  environmentApiProvidersFromDiscovered,
  resolveEnvironmentApiSelection,
  type EnvCreatorApiProvider,
} from "./environmentCreatorProviders";
import "./environmentCreator.css";
import { CreatorProfileDeleteModal } from "../../creators/CreatorProfileDeleteModal";
import type { CreatorDeletePreview } from "../../creators/creatorProfileDelete";
import {
  ENV_CREATOR_ASPECTS,
  ENV_CREATOR_GENERATORS,
  ENV_CREATOR_MAX_CHARACTERS,
  ENV_CREATOR_MAX_PROPS,
  buildEnvironmentCreatorSaveBody,
  buildEnvironmentPlanSummary,
  canAddCharacter,
  canAddProp,
  emptyEnvironmentCreatorPlanning,
  environmentCreatorGenerateBlockReason,
  environmentCreatorPersistSnapshot,
  extractApprovedProp,
  extractCharacterThumbAndCrs,
  formatPropAssignmentLabel,
  loadEnvironmentCreatorDraft,
  planningFromSavedSheet,
  publishEnvironmentCreatorPlanning,
  resolveStoryThemeLabel,
  saveEnvironmentCreatorDraft,
  serializeEnvironmentCreatorPlan,
  validateEnvironmentCreatorSave,
  type EnvCreatorAspect,
  type EnvCreatorCharacterPlan,
  type EnvCreatorPropPlan,
  type EnvironmentCreatorPlanningState,
} from "./environmentCreatorPlanning";

export type EnvironmentCreatorSurfaceProps = {
  projectId: string;
  variant?: "express" | "standard";
  onGoTab?: (tab: string, extra?: Record<string, string>) => void;
};

type CatalogCharacter = EnvCreatorCharacterPlan;
type CatalogProp = {
  propId: string;
  name: string;
  prsAssetId: string | null;
  thumbAssetId: string | null;
};

function mergeDraft(
  base: EnvironmentCreatorPlanningState,
  draft: Partial<EnvironmentCreatorPlanningState> | null,
): EnvironmentCreatorPlanningState {
  if (!draft) return base;
  return {
    ...base,
    referenceImageAssetId:
      draft.referenceImageAssetId !== undefined ? draft.referenceImageAssetId : base.referenceImageAssetId,
    name: typeof draft.name === "string" ? draft.name : base.name,
    isGlobal: typeof draft.isGlobal === "boolean" ? draft.isGlobal : base.isGlobal,
    environmentPrompt:
      typeof draft.environmentPrompt === "string" ? draft.environmentPrompt : base.environmentPrompt,
    characters: Array.isArray(draft.characters) ? draft.characters.slice(0, ENV_CREATOR_MAX_CHARACTERS) : base.characters,
    props: Array.isArray(draft.props) ? draft.props.slice(0, ENV_CREATOR_MAX_PROPS) : base.props,
    storyTheme: draft.storyTheme
      ? {
          label: String(draft.storyTheme.label || ""),
          source: draft.storyTheme.source === "story" || draft.storyTheme.source === "override" ? draft.storyTheme.source : "none",
          override: String(draft.storyTheme.override || ""),
        }
      : base.storyTheme,
    aspectRatio: ENV_CREATOR_ASPECTS.includes(draft.aspectRatio as EnvCreatorAspect)
      ? (draft.aspectRatio as EnvCreatorAspect)
      : base.aspectRatio,
    generator: "gpt-image-2",
    apiProvider: typeof draft.apiProvider === "string" ? draft.apiProvider : base.apiProvider,
    apiModelId: typeof draft.apiModelId === "string" ? draft.apiModelId : base.apiModelId,
    apiOfficialModelId: typeof draft.apiOfficialModelId === "string" ? draft.apiOfficialModelId : base.apiOfficialModelId,
    apiModelLabel: typeof draft.apiModelLabel === "string" ? draft.apiModelLabel : base.apiModelLabel,
  };
}

type SaveFeedback = "idle" | "saving" | "saved" | "error";

function EnvironmentDeleteButton({
  placement,
  disabled,
  onDelete,
  label = "Delete Environment",
}: {
  placement: "top" | "bottom" | "row";
  disabled: boolean;
  onDelete: () => void;
  label?: string;
}) {
  return (
    <button
      type="button"
      className="danger"
      data-testid={
        placement === "top"
          ? "environment-creator-delete-top"
          : placement === "bottom"
            ? "environment-creator-delete-bottom"
            : "environment-creator-delete"
      }
      data-delete-command={label === "Delete Snapshot" ? "deleteSnapshot" : "deleteEnvironment"}
      disabled={disabled}
      onClick={onDelete}
    >
      {label}
    </button>
  );
}

function EnvironmentSaveButton({
  placement,
  busy,
  dirty,
  feedback,
  onSave,
}: {
  placement: "top" | "bottom";
  busy: boolean;
  dirty: boolean;
  feedback: SaveFeedback;
  onSave: () => void;
}) {
  const label = busy ? "Saving…" : feedback === "saved" && !dirty ? "Saved ✓" : "Save Environment";
  return (
    <div className="environment-creator-surface__save-wrap">
      <button
        type="button"
        className="primary environment-creator-surface__save"
        data-testid={`environment-creator-save-${placement}`}
        data-save-command="saveEnvironment"
        data-dirty={dirty ? "true" : "false"}
        aria-busy={busy}
        disabled={busy}
        onClick={onSave}
      >
        {label}
      </button>
      <span className="muted" data-testid={`environment-creator-save-state-${placement}`}>
        {busy ? "Saving…" : dirty ? "Unsaved" : "Saved"}
      </span>
    </div>
  );
}

export function EnvironmentCreatorSurface({
  projectId,
  variant = "express",
  onGoTab,
}: EnvironmentCreatorSurfaceProps) {
  const [activeExecution, setActiveExecution] = useState<WorkSurfaceState | null>(null);
  const [planning, setPlanning] = useState<EnvironmentCreatorPlanningState>(() => {
    const empty = emptyEnvironmentCreatorPlanning();
    return mergeDraft(empty, loadEnvironmentCreatorDraft(projectId));
  });
  const [pickerOpen, setPickerOpen] = useState(false);
  const [charMenuOpen, setCharMenuOpen] = useState(false);
  const [propMenuOpen, setPropMenuOpen] = useState(false);
  const [charCatalog, setCharCatalog] = useState<CatalogCharacter[]>([]);
  const [propCatalog, setPropCatalog] = useState<CatalogProp[]>([]);
  const [uploadBusy, setUploadBusy] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const [projectSheets, setProjectSheets] = useState<EnvironmentReferenceSheetSummary[]>([]);
  const [sheetsLoading, setSheetsLoading] = useState(false);
  const [sheetsError, setSheetsError] = useState<string | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [editCandidate, setEditCandidate] = useState<{
    sheetId: string;
    sourceAssetId: string;
    sheetName?: string;
  } | null>(null);
  const [lastDerivativeId, setLastDerivativeId] = useState<string | null>(null);
  const [pendingErsEdit, setPendingErsEdit] = useState<{
    kind: "annotation_only" | "image_edit";
    jobId: string | null;
    status: string;
    message: string;
    sheetId: string;
    sourceAssetId: string;
    derivativeAssetId?: string | null;
  } | null>(null);
  const [ersSubmitFlash, setErsSubmitFlash] = useState<string | null>(null);
  const initialDraft = loadEnvironmentCreatorDraft(projectId);
  const [boundSheetId, setBoundSheetId] = useState<string | null>(() => initialDraft?.boundSheetId || null);
  const [lastSavedSnapshot, setLastSavedSnapshot] = useState<string | null>(() => initialDraft?.savedSnapshot ?? null);
  const [saveBusy, setSaveBusy] = useState(false);
  const [saveFeedback, setSaveFeedback] = useState<SaveFeedback>("idle");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [deletePreview, setDeletePreview] = useState<CreatorDeletePreview | null>(null);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteNotice, setDeleteNotice] = useState<string | null>(null);
  const [sheetImagePreview, setSheetImagePreview] = useState<ErsSheetImagePreview | null>(null);
  const [approveBusy, setApproveBusy] = useState(false);
  const [draftNew, setDraftNew] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const nameInputRef = useRef<HTMLInputElement>(null);
  const saveLockRef = useRef(false);
  const hydratedProjectRef = useRef<string | null>(null);
  const [apiProviders, setApiProviders] = useState<EnvCreatorApiProvider[]>(environmentApiProviderSlots);
  const [providerCatalogLoaded, setProviderCatalogLoaded] = useState(false);
  const [providerNotice, setProviderNotice] = useState<string | null>(null);

  const ers = useErsGeneration({
    projectId,
    spatialMapId: null,
    sourceAssetId: planning.referenceImageAssetId,
    planning: serializeEnvironmentCreatorPlan(planning),
    document: undefined,
    activeExecution,
    setActiveExecution,
    hydrateExistingSheets: true,
  });

  const generatorMeta = ENV_CREATOR_GENERATORS.find((g) => g.id === planning.generator) || ENV_CREATOR_GENERATORS[0];
  const providerReady = planning.generator === "gpt-image-2" ? ers.gptReady : false;
  const providerI2IReady = planning.generator === "gpt-image-2" ? ers.gptI2IReady : false;

  const generateBlocked = environmentCreatorGenerateBlockReason({
    planning,
    providerReady,
    providerI2IReady,
    generatorCatalogAvailable: generatorMeta.catalogAvailable,
    generatorUnavailableReason: generatorMeta.unavailableReason,
    selectedProviderAvailable: providerCatalogLoaded ? apiProviders.some((provider) => provider.available) : undefined,
  });

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const discovered = await api.hostedProvidersDiscoveredModels("image");
        const payload = discovered as { items?: Array<Record<string, unknown>>; models?: Array<Record<string, unknown>> } | null;
        const items = payload?.items || payload?.models || [];
        if (!cancelled) setApiProviders(environmentApiProvidersFromDiscovered(items));
      } catch {
        if (!cancelled) setApiProviders(environmentApiProviderSlots());
      } finally {
        if (!cancelled) setProviderCatalogLoaded(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  useEffect(() => {
    if (!apiProviders.some((provider) => provider.available)) return;
    const next = resolveEnvironmentApiSelection(apiProviders, planning.apiProvider, planning.apiModelId);
    if (next.unavailable) setProviderNotice(ENV_PROVIDER_UNAVAILABLE_MESSAGE);
    if (
      next.providerId === planning.apiProvider &&
      next.modelId === planning.apiModelId &&
      next.officialModelId === planning.apiOfficialModelId &&
      next.modelLabel === planning.apiModelLabel
    ) {
      return;
    }
    setPlanning((prev) => ({
      ...prev,
      apiProvider: next.providerId,
      apiModelId: next.modelId,
      apiOfficialModelId: next.officialModelId,
      apiModelLabel: next.modelLabel,
    }));
  }, [apiProviders, planning.apiModelId, planning.apiModelLabel, planning.apiOfficialModelId, planning.apiProvider]);

  const sessionActive = ers.busy || ers.phase !== "idle" || Boolean(ers.compositeAssetId || ers.progress.finalAssetId);
  const imageId = ers.compositeAssetId || ers.progress.finalAssetId;
  const planSummary = useMemo(() => buildEnvironmentPlanSummary(planning), [planning]);
  const referenceSheets = useMemo(
    () => projectSheets.filter((sheet) => isProjectEnvironmentReferenceSheet(sheet)),
    [projectSheets],
  );
  const draftSheets = useMemo(
    () => projectSheets.filter((sheet) => isOwnedEnvironmentDraft(sheet, projectId)),
    [projectId, projectSheets],
  );

  const persistSnap = useMemo(() => environmentCreatorPersistSnapshot(planning), [planning]);
  const dirty = (lastSavedSnapshot ?? environmentCreatorPersistSnapshot(emptyEnvironmentCreatorPlanning())) !== persistSnap;

  // Re-hydrate draft when project changes.
  useEffect(() => {
    if (hydratedProjectRef.current === projectId) return;
    hydratedProjectRef.current = projectId;
    const draft = loadEnvironmentCreatorDraft(projectId);
    setPlanning(mergeDraft(emptyEnvironmentCreatorPlanning(), draft));
    setBoundSheetId(draft?.boundSheetId || null);
    setLastSavedSnapshot(draft?.savedSnapshot ?? null);
    setSaveFeedback("idle");
    setSaveError(null);
  }, [projectId]);



  // Keep Edit entry aligned with hook-hydrated sheet/composite.
  useEffect(() => {
    if (draftNew) return;
    if (!ers.sheetId || !(ers.compositeAssetId || ers.progress.finalAssetId)) return;
    if (boundSheetId && boundSheetId !== ers.sheetId) return;
    const sheetId = ers.sheetId;
    setEditCandidate((prev) => {
      if (prev && (prev.sheetId === sheetId || (boundSheetId && prev.sheetId === boundSheetId))) return prev;
      const sourceAssetId = String(ers.compositeAssetId || ers.progress.finalAssetId || "");
      const sheetName = projectSheets.find((s) => s.sheetId === sheetId)?.name;
      return {
        sheetId,
        sourceAssetId,
        sheetName: sheetName || "Environment Reference Sheet",
      };
    });
  }, [boundSheetId, draftNew, ers.compositeAssetId, ers.progress.finalAssetId, ers.sheetId, projectSheets]);

  // Hydrate existing project ERS sheets into Creator (kill Library-only dead-end).
  useEffect(() => {
    let cancelled = false;
    setSheetsLoading(true);
    setSheetsError(null);
    void (async () => {
      try {
        const listed = await api.environmentReferenceSheet.listSheets(projectId);
        const sheets = [...(listed.sheets || [])].sort((a, b) =>
          String(b.updatedAt || "").localeCompare(String(a.updatedAt || "")),
        );
        if (!cancelled) setProjectSheets(sheets);
      } catch (err) {
        if (!cancelled) {
          setProjectSheets([]);
          setSheetsError(err instanceof Error ? err.message : "Failed to load ERS sheets.");
        }
      } finally {
        if (!cancelled) setSheetsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId, ers.compositeAssetId, ers.sheetId]);

  useEffect(() => {
    if (draftNew) return;
    const current = projectSheets.find((s) => s.sheetId === ers.sheetId);
    if (!current) return;
    setPlanning((prev) => {
      const typed = normalizeProfileName(prev.name);
      const sheetName = normalizeProfileName(current.name);
      if (typed && typed !== sheetName) return prev;
      return {
        ...prev,
        name: prev.name.trim() ? prev.name : String(current.name || ""),
        isGlobal: Boolean(current.isGlobal || current.is_global || prev.isGlobal),
      };
    });
  }, [draftNew, ers.sheetId, projectSheets]);

  // Persist draft + publish for Co-Director awareness (module store + uiContext).
  useEffect(() => {
    saveEnvironmentCreatorDraft(projectId, planning, { boundSheetId, savedSnapshot: lastSavedSnapshot });
    publishEnvironmentCreatorPlanning(projectId, planning);
  }, [boundSheetId, lastSavedSnapshot, planning, projectId]);

  useEffect(() => {
    return () => {
      publishEnvironmentCreatorPlanning(projectId, null);
    };
  }, [projectId]);

  // Inherit canonical Story theme (same authority as Scene Creator Standard: api.getBible themes).
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const bible = await api.getBible(projectId);
        const themes =
          (bible as { compiledStorySummary?: { themes?: string[] } } | undefined)?.compiledStorySummary
            ?.themes || [];
        const theme = themes.length ? themes.join(", ") : "";
        if (cancelled) return;
        setPlanning((prev) => {
          if (prev.storyTheme.override.trim()) {
            return {
              ...prev,
              storyTheme: {
                ...prev.storyTheme,
                label: theme ? String(theme) : prev.storyTheme.label,
                source: theme ? "story" : prev.storyTheme.source,
              },
            };
          }
          if (theme) {
            return {
              ...prev,
              storyTheme: { label: String(theme), source: "story", override: prev.storyTheme.override },
            };
          }
          return {
            ...prev,
            storyTheme: { label: "", source: "none", override: prev.storyTheme.override },
          };
        });
      } catch {
        if (!cancelled) {
          setPlanning((prev) =>
            prev.storyTheme.override.trim()
              ? prev
              : { ...prev, storyTheme: { label: "", source: "none", override: "" } },
          );
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  // Load saved project characters + approved props catalogs.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const chars = await api.listCharacterProfiles(projectId);
        const rows = (Array.isArray(chars) ? chars : (chars as { items?: unknown[] })?.items || []) as Record<
          string,
          unknown
        >[];
        const items = rows
          .map((row) => extractCharacterThumbAndCrs(row))
          .filter((row) => row.characterId)
          .map(
            (row): CatalogCharacter => ({
              characterId: row.characterId,
              name: row.name,
              thumbAssetId: row.thumbAssetId,
              crsAssetId: row.crsAssetId,
              crsApproved: row.crsApproved,
            }),
          );
        if (!cancelled) setCharCatalog(items);
      } catch {
        if (!cancelled) setCharCatalog([]);
      }
      try {
        const propsRes = await api.propCreator.list(projectId, true);
        const rows = (
          Array.isArray(propsRes)
            ? propsRes
            : (propsRes as { props?: unknown[] })?.props || (propsRes as { items?: unknown[] })?.items || []
        ) as Record<string, unknown>[];
        const items = rows
          .map((row) => extractApprovedProp(row))
          .filter((row): row is CatalogProp => Boolean(row?.propId));
        if (!cancelled) setPropCatalog(items);
      } catch {
        if (!cancelled) setPropCatalog([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const handleUploadSource = useCallback(
    async (file: File) => {
      setUploadError(null);
      setUploadBusy(true);
      try {
        const asset = await api.uploadAsset(projectId, file, "environment_reference", "image");
        const id = String((asset as { id?: string })?.id || "").trim();
        if (!id) throw new Error("Upload did not return an asset id.");
        setPlanning((prev) => ({ ...prev, referenceImageAssetId: id }));
      } catch (err) {
        setUploadError(err instanceof Error ? err.message : "Upload failed.");
      } finally {
        setUploadBusy(false);
      }
    },
    [projectId],
  );

  const handleUseInSceneCreator = useCallback(async () => {
    await persistThenOpenSceneCreator({
      projectId,
      sheetId: ers.sheetId || undefined,
      onGoTab,
    });
  }, [ers.sheetId, onGoTab, projectId]);

  const handleOpenFullSize = useCallback(
    (url: string) => {
      const id = imageId;
      const href = id ? api.assetUrl(id) : url;
      window.open(href, "_blank", "noopener,noreferrer");
    },
    [imageId],
  );

  const handleGenerate = useCallback(async () => {
    setStartError(null);
    const typed = normalizeProfileName(planning.name);
    const selectedId = String(boundSheetId || editCandidate?.sheetId || ers.sheetId || "").trim();
    const selected =
      projectSheets.find((sheet) => sheet.sheetId === selectedId) || null;
    const selectedName = normalizeProfileName(selected?.name || editCandidate?.sheetName || "");
    const sameSheet = Boolean(!draftNew && selectedId && typed && typed === selectedName);
    if (!sameSheet) {
      setDraftNew(true);
      setBoundSheetId(null);
      setEditCandidate(null);
    }
    try {
      await ers.start({
        ...serializeEnvironmentCreatorPlan(planning),
        ...(sameSheet ? { sheetId: selectedId } : {}),
      });
    } catch (err) {
      setStartError(err instanceof Error ? err.message : String(err));
    }
  }, [boundSheetId, draftNew, editCandidate, ers, planning, projectSheets]);

  const resolveTargetSheetId = useCallback((): string | null => {
    // Owner/mutation rule: a visible Global sheet owned by another project is
    // never a save/approve target — editing here means a NEW environment in
    // THIS project (the backend rejects foreign mutation with 403).
    const ownedOrNull = (sid: string | null | undefined): string | null => {
      const id = String(sid || "").trim();
      if (!id) return null;
      const listed = projectSheets.find((s) => s.sheetId === id);
      if (!listed) return id; // freshly bound and not yet listed — keep
      const owner = String(listed.projectId || "").trim();
      return !owner || owner === projectId ? id : null;
    };
    const bound = ownedOrNull(boundSheetId);
    if (bound) return bound;
    const candidate = ownedOrNull(editCandidate?.sheetId);
    if (candidate) return candidate;
    const needle = planning.name.trim().toLowerCase();
    if (needle) {
      const byName = projectSheets.find((s) => String(s.name || "").trim().toLowerCase() === needle);
      const owned = ownedOrNull(byName?.sheetId);
      if (owned) return owned;
    }
    if (ers.sheetId) {
      const current = projectSheets.find((s) => s.sheetId === ers.sheetId);
      if (current && needle && String(current.name || "").trim().toLowerCase() === needle) {
        return ownedOrNull(ers.sheetId);
      }
    }
    return null;
  }, [boundSheetId, editCandidate?.sheetId, ers.sheetId, planning.name, projectId, projectSheets]);

  const saveEnvironment = useCallback(async () => {
    if (saveLockRef.current || saveBusy) return;
    const valid = validateEnvironmentCreatorSave(planning);
    if (!valid.ok) {
      setSaveFeedback("error");
      setSaveError(valid.error);
      if (valid.field === "name") nameInputRef.current?.focus();
      return;
    }
    const sheetId = resolveTargetSheetId();
    const localHit = findVisibleNameCollision(projectSheets, planning.name, sheetId || boundSheetId || "");
    if (localHit && !sheetId) {
      setSaveFeedback("error");
      setSaveError(ENVIRONMENT_NAME_ALREADY_EXISTS_MESSAGE);
      return;
    }
    saveLockRef.current = true;
    setSaveBusy(true);
    setSaveFeedback("saving");
    setSaveError(null);
    try {
      const res = await api.environmentReferenceSheet.upsert(
        projectId,
        buildEnvironmentCreatorSaveBody(planning, sheetId),
      );
      const nextId = String(res.sheet?.sheetId || "").trim();
      if (!nextId) throw new Error("Save did not return an environment id.");
      const nextSnapshot = environmentCreatorPersistSnapshot(planning);
      setBoundSheetId(nextId);
      setDraftNew(false);
      setLastSavedSnapshot(nextSnapshot);
      setSaveFeedback("saved");
      const composite = String(
        res.sheet?.ers_composite_asset_id || res.summary?.ers_composite_asset_id || editCandidate?.sourceAssetId || "",
      ).trim();
      setEditCandidate({
        sheetId: nextId,
        sourceAssetId: composite || editCandidate?.sourceAssetId || "",
        sheetName: res.sheet?.name || planning.name,
      });
      try {
        const listed = await api.environmentReferenceSheet.listSheets(projectId);
        const sheets = [...(listed.sheets || [])].sort((a, b) =>
          String(b.updatedAt || "").localeCompare(String(a.updatedAt || "")),
        );
        setProjectSheets(sheets);
      } catch {
        // list refresh is best-effort; the save itself already succeeded
      }
    } catch (err) {
      setSaveFeedback("error");
      const message =
        err instanceof ApiError && err.code === PROFILE_NAME_ALREADY_EXISTS
          ? err.message
          : err instanceof Error
            ? err.message
            : String(err);
      setSaveError(message);
    } finally {
      saveLockRef.current = false;
      setSaveBusy(false);
    }
  }, [boundSheetId, editCandidate?.sourceAssetId, planning, projectId, projectSheets, resolveTargetSheetId, saveBusy]);

  const selectHydratedSheet = useCallback(
    async (sheetId: string) => {
      try {
        const res = await api.environmentReferenceSheet.getSheet(projectId, sheetId);
        const composite =
          String(res.summary?.ers_composite_asset_id || res.sheet?.ers_composite_asset_id || "").trim() || null;
        const nextPlanning = planningFromSavedSheet(res.sheet, planning);
        setPlanning(nextPlanning);
        setBoundSheetId(sheetId);
        setDraftNew(false);
        setLastSavedSnapshot(environmentCreatorPersistSnapshot(nextPlanning));
        setSaveFeedback("idle");
        setSaveError(null);
        setEditCandidate({
          sheetId,
          sourceAssetId: composite || "",
          sheetName: res.summary?.name || res.sheet?.name || "Environment Reference Sheet",
        });
        setLastDerivativeId(null);
      } catch (err) {
        setStartError(err instanceof Error ? err.message : "Failed to load sheet.");
      }
    },
    [planning, projectId],
  );

  const openEditInpaint = useCallback(() => {
    const sheetId = editCandidate?.sheetId || ers.sheetId;
    const sourceAssetId = editCandidate?.sourceAssetId || ers.compositeAssetId || ers.progress.finalAssetId;
    if (!sheetId || !sourceAssetId) {
      setStartError("Select an ERS sheet with a composite before Edit / Inpaint.");
      return;
    }
    const name =
      editCandidate?.sheetName ||
      projectSheets.find((s) => s.sheetId === sheetId)?.name ||
      "Environment Reference Sheet";
    setEditCandidate({ sheetId, sourceAssetId, sheetName: name });
    setEditOpen(true);
  }, [editCandidate, ers.compositeAssetId, ers.progress.finalAssetId, ers.sheetId, projectSheets]);

  // After image-edit Submit acceptance, track pending/running on EC while Edit/Inpaint is closed.
  useEffect(() => {
    if (!pendingErsEdit || pendingErsEdit.kind !== "image_edit" || !pendingErsEdit.jobId) return;
    const terminal = ["completed", "failed", "error", "cancelled"];
    if (terminal.includes(pendingErsEdit.status)) return;

    let cancelled = false;
    const jobId = pendingErsEdit.jobId;
    const sheetId = pendingErsEdit.sheetId;

    const tick = async () => {
      try {
        let status = "";
        let derivative: string | null = null;
        try {
          const result = await api.environmentReferenceSheet.getEditJob(projectId, sheetId, jobId);
          status = String(result?.status || "").toLowerCase();
          derivative =
            String(result?.derivativeAssetId || result?.resultAssetId || "").trim() || null;
        } catch {
          const job = await api.getJob(jobId);
          const meta =
            (job as { metadata?: Record<string, unknown>; result?: Record<string, unknown> }).metadata ||
            {};
          const jobResult = (job as { result?: Record<string, unknown> }).result || {};
          status = String((job as { status?: string }).status || "").toLowerCase();
          derivative =
            String(
              meta.derivativeAssetId ||
                meta.resultAssetId ||
                jobResult.derivativeAssetId ||
                jobResult.resultAssetId ||
                (job as { asset_id?: string }).asset_id ||
                "",
            ).trim() || null;
        }
        if (cancelled) return;
        const label = ersEditPendingStatusLabel(status || "running");
        if (derivative) {
          setLastDerivativeId(derivative);
          setPendingErsEdit((prev) =>
            prev
              ? {
                  ...prev,
                  status: "completed",
                  derivativeAssetId: derivative,
                  message: "Edit ready — open Edit / Inpaint to review the draft.",
                }
              : null,
          );
          return;
        }
        if (["failed", "error", "cancelled"].includes(label)) {
          setPendingErsEdit((prev) =>
            prev
              ? {
                  ...prev,
                  status: label,
                  message: "The edit failed. Open Edit / Inpaint to retry.",
                }
              : null,
          );
          return;
        }
        setPendingErsEdit((prev) => (prev ? { ...prev, status: label } : null));
      } catch {
        /* keep last known pending/running status */
      }
    };

    void tick();
    const id = window.setInterval(() => void tick(), 3000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [pendingErsEdit, projectId]);


  const selectedSheetId = draftNew
    ? boundSheetId
    : boundSheetId || editCandidate?.sheetId || null;

  const selectedSheetOwned = useMemo(() => {
    if (!selectedSheetId) return false;
    const sheet = projectSheets.find((s) => s.sheetId === selectedSheetId);
    if (!sheet) return selectedSheetId === boundSheetId;
    const owner = String(sheet.projectId || "").trim();
    return !owner || owner === projectId;
  }, [boundSheetId, projectId, projectSheets, selectedSheetId]);

  // Direct-approval state (Path A): the attached reference image is the
  // approved environment visual when the selected sheet's official composite
  // points at it and the sheet is approved.
  const selectedSheet = useMemo(() => {
    if (!selectedSheetId) return null;
    return projectSheets.find((s) => s.sheetId === selectedSheetId) || null;
  }, [projectSheets, selectedSheetId]);

  const approvedVisualAssetId = useMemo(() => {
    const raw = String(selectedSheet?.ers_composite_asset_id || "").trim();
    return raw || null;
  }, [selectedSheet]);

  const referenceIsApproved = Boolean(
    planning.referenceImageAssetId &&
      approvedVisualAssetId &&
      String(planning.referenceImageAssetId).trim() === approvedVisualAssetId &&
      selectedSheet?.status === "approved",
  );

  const refreshProjectSheets = useCallback(async () => {
    try {
      const listed = await api.environmentReferenceSheet.listSheets(projectId);
      const sheets = [...(listed.sheets || [])].sort((a, b) =>
        String(b.updatedAt || "").localeCompare(String(a.updatedAt || "")),
      );
      setProjectSheets(sheets);
    } catch {
      // list refresh is best-effort; the approving save already succeeded
    }
  }, [projectId]);

  // Path A — approve the attached reference image as the official environment
  // visual for the current environment identity. Commits the form first when
  // the identity has unsaved changes, so approval never needs a separate save.
  const handleApproveAsEnvironment = useCallback(async () => {
    const assetId = String(planning.referenceImageAssetId || "").trim();
    if (!assetId || approveBusy || saveBusy || ers.busy || deleting) return;
    setApproveBusy(true);
    setSaveError(null);
    try {
      let sheetId = resolveTargetSheetId();
      if (!sheetId || dirty) {
        const valid = validateEnvironmentCreatorSave(planning);
        if (!valid.ok) {
          setSaveFeedback("error");
          setSaveError(valid.error);
          if (valid.field === "name") nameInputRef.current?.focus();
          return;
        }
        const localHit = findVisibleNameCollision(projectSheets, planning.name, sheetId || boundSheetId || "");
        if (localHit && !sheetId) {
          setSaveFeedback("error");
          setSaveError(ENVIRONMENT_NAME_ALREADY_EXISTS_MESSAGE);
          return;
        }
        const saved = await api.environmentReferenceSheet.upsert(
          projectId,
          buildEnvironmentCreatorSaveBody(planning, sheetId),
        );
        sheetId = String(saved.sheet?.sheetId || "").trim();
        if (!sheetId) throw new Error("Save did not return an environment id.");
        setBoundSheetId(sheetId);
        setDraftNew(false);
      }
      const res = await api.environmentReferenceSheet.approveReference(projectId, sheetId, assetId);
      setLastSavedSnapshot(environmentCreatorPersistSnapshot(planning));
      setSaveFeedback("saved");
      setEditCandidate({
        sheetId,
        sourceAssetId: assetId,
        sheetName: res.sheet?.name || planning.name,
      });
      await refreshProjectSheets();
    } catch (err) {
      setSaveFeedback("error");
      setSaveError(err instanceof Error ? err.message : String(err));
    } finally {
      setApproveBusy(false);
    }
  }, [approveBusy, boundSheetId, deleting, dirty, ers.busy, planning, projectId, projectSheets, refreshProjectSheets, resolveTargetSheetId, saveBusy]);

  // Remove must not leave a dangling approval: when the attached image IS the
  // approved environment visual, confirm and clear approval with the detach.
  const handleRemoveReference = useCallback(() => {
    const assetId = String(planning.referenceImageAssetId || "").trim();
    if (!assetId) return;
    if (referenceIsApproved && selectedSheetId) {
      const ok = window.confirm(
        "This image is the approved Environment Reference. Remove approval as well?",
      );
      if (!ok) return;
      const sheetId = selectedSheetId;
      void (async () => {
        try {
          await api.environmentReferenceSheet.clearApproval(projectId, sheetId);
        } catch (err) {
          // Clearing failed — keep the local image attached so approval never dangles.
          setSaveError(err instanceof Error ? err.message : "Could not remove the approval. Try again.");
          return;
        }
        setPlanning((prev) => ({ ...prev, referenceImageAssetId: null }));
        await refreshProjectSheets();
      })();
      return;
    }
    setPlanning((prev) => ({ ...prev, referenceImageAssetId: null }));
  }, [planning.referenceImageAssetId, projectId, referenceIsApproved, refreshProjectSheets, selectedSheetId]);

  const handleCreateNew = useCallback(() => {
    if (saveBusy || ers.busy || deleting) return;
    setDraftNew(true);
    setBoundSheetId(null);
    setEditCandidate(null);
    setLastDerivativeId(null);
    setDeleteNotice(null);
    setSaveError(null);
    setStartError(null);
    const empty = emptyEnvironmentCreatorPlanning();
    setPlanning(empty);
    setLastSavedSnapshot(environmentCreatorPersistSnapshot(empty));
    setSaveFeedback("idle");
    nameInputRef.current?.focus();
  }, [deleting, ers.busy, saveBusy]);

  const handleDeleteClick = useCallback(async (sheetId?: string) => {
    const target = sheetId || selectedSheetId;
    if (!target || saveBusy || ers.busy || deleting) return;
    const row = projectSheets.find((s) => s.sheetId === target);
    const owner = String(row?.projectId || "").trim();
    if (owner && owner !== projectId) {
      setDeleteNotice("Global environments can only be deleted from the project that created them.");
      return;
    }
    setDeleteNotice(null);
    try {
      const preview = await api.environmentReferenceSheet.getDeletePreview(projectId, target);
      setDeletePreview(preview);
      setDeleteModalOpen(true);
    } catch (e) {
      setDeleteNotice(e instanceof Error ? e.message : "Failed to load delete preview.");
    }
  }, [deleting, ers.busy, projectId, projectSheets, saveBusy, selectedSheetId]);

  const handleConfirmDelete = useCallback(async () => {
    const target = deletePreview?.entityId || selectedSheetId;
    if (!target || !deletePreview) return;
    setDeleting(true);
    setDeleteNotice(null);
    try {
      const result = await api.environmentReferenceSheet.deleteSheet(
        projectId,
        target,
        deletePreview.isGlobal && deletePreview.usageCount > 0,
      );
      if (result.deleted) {
        setDeleteModalOpen(false);
        setDeletePreview(null);
        setDeleteNotice("Environment deleted");
        setEditCandidate(null);
        setBoundSheetId(null);
        setDraftNew(true);
        const empty = emptyEnvironmentCreatorPlanning();
        setPlanning(empty);
        setLastSavedSnapshot(environmentCreatorPersistSnapshot(empty));
        setSaveFeedback("idle");
        try {
          const listed = await api.environmentReferenceSheet.listSheets(projectId);
          const sheets = [...(listed.sheets || [])].sort((a, b) =>
            String(b.updatedAt || "").localeCompare(String(a.updatedAt || "")),
          );
          setProjectSheets(sheets);
        } catch {
          setProjectSheets([]);
        }
      } else {
        setDeleteNotice("Could not delete environment.");
      }
    } catch (e) {
      setDeleteNotice(e instanceof Error ? e.message : "Failed to delete environment.");
    } finally {
      setDeleting(false);
    }
  }, [deletePreview, projectId, selectedSheetId]);

  const addCharacter = useCallback((row: CatalogCharacter) => {
    setPlanning((prev) => {
      if (!canAddCharacter(prev.characters.length)) return prev;
      if (prev.characters.some((c) => c.characterId === row.characterId)) return prev;
      return { ...prev, characters: [...prev.characters, row] };
    });
    setCharMenuOpen(false);
  }, []);

  const removeCharacter = useCallback((characterId: string) => {
    setPlanning((prev) => ({
      ...prev,
      characters: prev.characters.filter((c) => c.characterId !== characterId),
      // Drop used_by assignments that pointed at removed characters — no silent reassign.
      props: prev.props.map((p) =>
        p.assignment.kind === "used_by" && p.assignment.characterId === characterId
          ? { ...p, assignment: { kind: "environment_object" as const } }
          : p,
      ),
    }));
  }, []);

  const addProp = useCallback((row: CatalogProp) => {
    setPlanning((prev) => {
      if (!canAddProp(prev.props.length)) return prev;
      if (prev.props.some((p) => p.propId === row.propId)) return prev;
      const next: EnvCreatorPropPlan = {
        propId: row.propId,
        name: row.name,
        prsAssetId: row.prsAssetId,
        thumbAssetId: row.thumbAssetId,
        assignment: { kind: "environment_object" },
      };
      return { ...prev, props: [...prev.props, next] };
    });
    setPropMenuOpen(false);
  }, []);

  const removeProp = useCallback((propId: string) => {
    setPlanning((prev) => ({ ...prev, props: prev.props.filter((p) => p.propId !== propId) }));
  }, []);

  const setPropAssignment = useCallback((propId: string, value: string) => {
    setPlanning((prev) => ({
      ...prev,
      props: prev.props.map((p) => {
        if (p.propId !== propId) return p;
        if (value === "environment_object") return { ...p, assignment: { kind: "environment_object" } };
        if (prev.characters.some((c) => c.characterId === value)) {
          return { ...p, assignment: { kind: "used_by", characterId: value } };
        }
        return p;
      }),
    }));
  }, []);

  const availableChars = charCatalog.filter((c) => !planning.characters.some((s) => s.characterId === c.characterId));
  const availableProps = propCatalog.filter((p) => !planning.props.some((s) => s.propId === p.propId));

  return (
    <section
      className="scene-creator-launcher environment-creator-surface"
      data-testid="environment-creator-surface"
      data-creator="environment"
      data-variant={variant}
      data-clean-start="true"
      aria-labelledby="environment-creator-title"
    >
      <header className="environment-creator-surface__header">
        <p className="eyebrow">Environment Creator</p>
        <div className="environment-creator-surface__title-row">
          <h2 id="environment-creator-title" className="scene-creator-launcher__title">
            Environment Creator
          </h2>
          <div className="environment-creator-surface__profile-actions">
            <button
              type="button"
              className="ghost"
              data-testid="environment-creator-new"
              disabled={saveBusy || ers.busy || deleting}
              onClick={handleCreateNew}
            >
              Create New
            </button>
            <EnvironmentSaveButton
              placement="top"
              busy={saveBusy}
              dirty={dirty}
              feedback={saveFeedback}
              onSave={() => void saveEnvironment()}
            />
            <EnvironmentDeleteButton
              placement="top"
              disabled={!selectedSheetId || !selectedSheetOwned || saveBusy || ers.busy || deleting}
              onDelete={() => void handleDeleteClick()}
            />
          </div>
        </div>
        <p className="scene-creator-launcher__lead">
          Plan and create the Environment Reference Sheet (ERS) for a location or set —
          environment identity for production, like a CRS for characters or a PRS for props.
        </p>
        {saveError ? (
          <p className="muted" data-testid="environment-creator-save-error" role="alert">
            {saveError}
          </p>
        ) : null}
        {deleteNotice ? (
          <p className="muted" data-testid="environment-creator-delete-notice" role="status">
            {deleteNotice}
          </p>
        ) : null}
      </header>

      {/* 1) Reference Image — OPTIONAL */}
      <div className="environment-creator-surface__source" data-testid="environment-creator-source-field">
        <h3 className="environment-creator-plan__section-title">Reference Image (optional)</h3>
        <p className="muted" style={{ margin: "0.35rem 0 0.4rem" }}>
          Optional. Library or upload. Leave blank to generate from description alone.
        </p>
        {planning.referenceImageAssetId ? (
          <div
            data-testid="environment-creator-source"
            style={{ display: "flex", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}
          >
            <img
              src={api.assetUrl(planning.referenceImageAssetId)}
              alt="Reference environment"
              style={{ maxWidth: "10rem", maxHeight: "7rem", objectFit: "cover", borderRadius: "0.4rem", width: "auto" }}
            />
            <button
              type="button"
              className="ghost"
              data-testid="environment-creator-change-source"
              onClick={() => setPickerOpen(true)}
            >
              Change from Library
            </button>
            <button
              type="button"
              className="ghost"
              data-testid="environment-creator-upload-source"
              disabled={uploadBusy}
              onClick={() => fileInputRef.current?.click()}
            >
              {uploadBusy ? "Uploading..." : "Upload image"}
            </button>
            <button
              type="button"
              className="ghost"
              data-testid="environment-creator-clear-source"
              onClick={handleRemoveReference}
            >
              Remove
            </button>
            <button
              type="button"
              className={referenceIsApproved ? "ghost" : "secondary"}
              data-testid="environment-creator-approve-source"
              data-approved={referenceIsApproved ? "true" : "false"}
              disabled={approveBusy || saveBusy || ers.busy || deleting || referenceIsApproved}
              title="Make this image the official environment visual — no generation needed."
              onClick={() => void handleApproveAsEnvironment()}
            >
              {approveBusy
                ? "Approving…"
                : referenceIsApproved
                  ? "Approved Environment ✓"
                  : "Approve as Environment"}
            </button>
          </div>
        ) : (
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center" }}>
            <button
              type="button"
              className="secondary"
              data-testid="environment-creator-choose-source"
              onClick={() => setPickerOpen(true)}
            >
              Choose from Library
            </button>
            <button
              type="button"
              className="ghost"
              data-testid="environment-creator-upload-source"
              disabled={uploadBusy}
              onClick={() => fileInputRef.current?.click()}
            >
              {uploadBusy ? "Uploading..." : "Upload image"}
            </button>
            <button
              type="button"
              className="secondary"
              data-testid="environment-creator-approve-source"
              data-approved="false"
              disabled
              title="Attach a reference image first, then approve it as the official environment visual."
              onClick={() => undefined}
            >
              Approve as Environment
            </button>
          </div>
        )}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          hidden
          data-testid="environment-creator-upload-input"
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            if (file) void handleUploadSource(file);
          }}
        />
        {uploadError ? (
          <p className="muted" data-testid="environment-creator-upload-error" role="status">
            {uploadError}
          </p>
        ) : null}
      </div>

      {pickerOpen ? (
        <EntityPicker
          kind="environment"
          projectId={projectId}
          title="Choose reference environment image"
          onClose={() => setPickerOpen(false)}
          onConfirm={(assetId) => {
            setPlanning((prev) => ({ ...prev, referenceImageAssetId: assetId }));
            setPickerOpen(false);
          }}
        />
      ) : null}

      <div className="environment-creator-plan__section" data-testid="environment-creator-identity">
        <h3 className="environment-creator-plan__section-title">Name</h3>
        <input
          ref={nameInputRef}
          type="text"
          data-testid="environment-creator-name"
          value={planning.name}
          onChange={(e) => {
            setSaveFeedback((prev) => (prev === "saved" ? "idle" : prev));
            setPlanning((prev) => ({ ...prev, name: e.target.value }));
          }}
          placeholder="e.g. Venture Corridor"
          aria-label="Environment name"
          style={{ width: "100%", boxSizing: "border-box", marginBottom: "0.6rem" }}
        />
        <GlobalScopeField
          testId="environment-creator-global"
          checked={planning.isGlobal}
          onChange={(isGlobal) => {
            setPlanning((prev) => ({ ...prev, isGlobal }));
            const selected = projectSheets.find((sheet) => sheet.sheetId === ers.sheetId);
            const sameSheet =
              !draftNew &&
              Boolean(ers.sheetId) &&
              Boolean(selected) &&
              normalizeProfileName(planning.name) === normalizeProfileName(selected?.name);
            if (sameSheet && ers.sheetId) {
              void api.environmentReferenceSheet
                .patchIdentity(projectId, ers.sheetId, { isGlobal, name: planning.name || undefined })
                .catch(() => undefined);
            }
          }}
        />
      </div>

      {/* 2) Environment Description */}
      <div className="environment-creator-plan__section" data-testid="environment-creator-prompt-field">
        <h3 className="environment-creator-plan__section-title">
          Environment Description
          {planning.referenceImageAssetId ? (
            <span className="muted"> (optional with reference image)</span>
          ) : (
            <span className="muted"> (required without reference image)</span>
          )}
        </h3>
        <textarea
          className="environment-creator-plan__prompt"
          data-testid="environment-creator-prompt"
          rows={4}
          value={planning.environmentPrompt}
          onChange={(e) => setPlanning((prev) => ({ ...prev, environmentPrompt: e.target.value }))}
          placeholder="Describe the location or set for the Environment Reference Sheet — place, architecture, lighting, atmosphere, era…"
          style={{ width: "100%", boxSizing: "border-box" }}
        />
      </div>

      {/* 3) Characters 0–4 */}
      <div className="environment-creator-plan__section" data-testid="environment-creator-characters">
        <h3 className="environment-creator-plan__section-title">
          Characters ({planning.characters.length}/{ENV_CREATOR_MAX_CHARACTERS})
        </h3>
        <p className="muted" style={{ margin: "0 0 0.4rem" }}>
          From saved project characters only. Optional.
        </p>
        <ul className="environment-creator-plan__chips" style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {planning.characters.map((c) => (
            <li
              key={c.characterId}
              data-testid="environment-creator-character-chip"
              style={{ display: "flex", gap: "0.5rem", alignItems: "center", marginBottom: "0.35rem" }}
            >
              {c.thumbAssetId ? (
                <img
                  src={api.assetUrl(c.thumbAssetId)}
                  alt=""
                  style={{ width: "2.25rem", height: "2.25rem", objectFit: "cover", borderRadius: "0.35rem" }}
                />
              ) : (
                <span
                  aria-hidden
                  style={{
                    width: "2.25rem",
                    height: "2.25rem",
                    borderRadius: "0.35rem",
                    background: "var(--border, #2c3346)",
                    display: "inline-block",
                  }}
                />
              )}
              <span>{c.name}</span>
              {c.crsApproved ? (
                <span data-testid="environment-creator-crs-approved" title="CRS approved">
                  CRS ✓
                </span>
              ) : (
                <span className="muted">No CRS</span>
              )}
              <button
                type="button"
                className="ghost"
                data-testid="environment-creator-remove-character"
                onClick={() => removeCharacter(c.characterId)}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
        {canAddCharacter(planning.characters.length) ? (
          <div>
            <button
              type="button"
              className="secondary"
              data-testid="environment-creator-add-character"
              onClick={() => setCharMenuOpen((v) => !v)}
            >
              Add Character
            </button>
            {charMenuOpen ? (
              <div className="scene-creator-add-menu" data-testid="environment-creator-character-menu">
                {!availableChars.length ? (
                  <p className="muted">No more saved characters available.</p>
                ) : (
                  availableChars.map((c) => (
                    <button
                      key={c.characterId}
                      type="button"
                      className="ghost"
                      data-testid="environment-creator-character-option"
                      onClick={() => addCharacter(c)}
                    >
                      {c.name}
                      {c.crsApproved ? " · CRS ✓" : ""}
                    </button>
                  ))
                )}
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      {/* 4) Props 0–4 */}
      <div className="environment-creator-plan__section" data-testid="environment-creator-props">
        <h3 className="environment-creator-plan__section-title">
          Props ({planning.props.length}/{ENV_CREATOR_MAX_PROPS})
        </h3>
        <p className="muted" style={{ margin: "0 0 0.4rem" }}>
          From approved PRS only. Assignment is explicit — never overridden from the prompt.
        </p>
        <ul className="environment-creator-plan__chips" style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {planning.props.map((p) => (
            <li
              key={p.propId}
              data-testid="environment-creator-prop-chip"
              style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap", marginBottom: "0.35rem" }}
            >
              {p.thumbAssetId ? (
                <img
                  src={api.assetUrl(p.thumbAssetId)}
                  alt=""
                  style={{ width: "2.25rem", height: "2.25rem", objectFit: "cover", borderRadius: "0.35rem" }}
                />
              ) : null}
              <span>{p.name}</span>
              <label className="muted">
                Assignment{" "}
                <select
                  data-testid="environment-creator-prop-assignment"
                  value={
                    p.assignment.kind === "used_by" ? p.assignment.characterId : "environment_object"
                  }
                  onChange={(e) => setPropAssignment(p.propId, e.target.value)}
                >
                  <option value="environment_object">Environment Object</option>
                  {planning.characters.map((c) => (
                    <option key={c.characterId} value={c.characterId}>
                      Used by {c.name}
                    </option>
                  ))}
                </select>
              </label>
              <span className="muted">{formatPropAssignmentLabel(p.assignment, planning.characters)}</span>
              <button
                type="button"
                className="ghost"
                data-testid="environment-creator-remove-prop"
                onClick={() => removeProp(p.propId)}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
        {canAddProp(planning.props.length) ? (
          <div>
            <button
              type="button"
              className="secondary"
              data-testid="environment-creator-add-prop"
              onClick={() => setPropMenuOpen((v) => !v)}
            >
              Add Prop
            </button>
            {propMenuOpen ? (
              <div className="scene-creator-add-menu" data-testid="environment-creator-prop-menu">
                {!availableProps.length ? (
                  <p className="muted">No approved props available.</p>
                ) : (
                  availableProps.map((p) => (
                    <button
                      key={p.propId}
                      type="button"
                      className="ghost"
                      data-testid="environment-creator-prop-option"
                      onClick={() => addProp(p)}
                    >
                      {p.name}
                    </button>
                  ))
                )}
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      {/* 5) Story Theme — inherited */}
      <div className="environment-creator-plan__section" data-testid="environment-creator-story-theme">
        <h3 className="environment-creator-plan__section-title">Story Theme</h3>
        <p className="muted" data-testid="environment-creator-story-theme-inherited">
          {planning.storyTheme.source === "story" && planning.storyTheme.label
            ? `Inherited from Story: ${planning.storyTheme.label}`
            : "No Story theme set"}
        </p>
        <label className="muted" style={{ display: "block", marginTop: "0.35rem" }}>
          Optional theme override
          <input
            type="text"
            data-testid="environment-creator-story-theme-override"
            value={planning.storyTheme.override}
            onChange={(e) =>
              setPlanning((prev) => ({
                ...prev,
                storyTheme: {
                  ...prev.storyTheme,
                  override: e.target.value,
                  source: e.target.value.trim() ? "override" : prev.storyTheme.label ? "story" : "none",
                },
              }))
            }
            placeholder="Override story theme for this ERS"
            style={{ width: "100%", boxSizing: "border-box", marginTop: "0.25rem" }}
          />
        </label>
        <p className="muted" style={{ marginTop: "0.25rem" }}>
          Effective: {resolveStoryThemeLabel(planning.storyTheme) || "—"}
        </p>
      </div>

      {/* 6) Image Aspect */}
      <div className="environment-creator-plan__section" data-testid="environment-creator-aspect">
        <h3 className="environment-creator-plan__section-title">Image Aspect</h3>
        <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
          {ENV_CREATOR_ASPECTS.map((aspect) => (
            <button
              key={aspect}
              type="button"
              className={planning.aspectRatio === aspect ? "primary" : "ghost"}
              data-testid="environment-creator-aspect-option"
              data-aspect={aspect}
              aria-pressed={planning.aspectRatio === aspect}
              onClick={() => setPlanning((prev) => ({ ...prev, aspectRatio: aspect }))}
            >
              {aspect}
            </button>
          ))}
        </div>
      </div>

      {/* 7) API provider + generator from Setup Wizard catalog */}
      <div className="environment-creator-plan__section" data-testid="environment-creator-generator">
        <h3 className="environment-creator-plan__section-title">API Provider</h3>
        {providerNotice ? (
          <p data-testid="environment-creator-provider-unavailable">{providerNotice}</p>
        ) : null}
        {!providerCatalogLoaded ? (
          <p className="muted">Checking configured providers…</p>
        ) : null}
        {providerCatalogLoaded && !apiProviders.some((provider) => provider.available) ? (
          <p className="muted" data-testid="environment-creator-provider-empty">
            No API provider is configured. Add one in Setup.
          </p>
        ) : null}
        <select
          className="environment-creator-provider-select"
          data-testid="environment-creator-provider"
          aria-label="API Provider"
          value={planning.apiProvider}
          onChange={(event) => {
            const chosen = apiProviders.find((provider) => provider.id === event.target.value);
            if (!chosen?.available) return;
            const next = resolveEnvironmentApiSelection(apiProviders, event.target.value, "");
            setProviderNotice(null);
            setPlanning((prev) => ({
              ...prev,
              apiProvider: next.providerId,
              apiModelId: next.modelId,
              apiOfficialModelId: next.officialModelId,
              apiModelLabel: next.modelLabel,
            }));
          }}
        >
          {apiProviders.map((provider) => (
            <option
              key={provider.id}
              value={provider.id}
              disabled={!provider.available}
              data-testid={`environment-creator-provider-${provider.id}`}
            >
              {provider.label}
            </option>
          ))}
        </select>
        <h3 className="environment-creator-plan__section-title" style={{ marginTop: "0.75rem" }}>
          Generator
        </h3>
        <select
          data-testid="environment-creator-model"
          aria-label="Generator"
          value={planning.apiModelId}
          disabled={!apiProviders.some((provider) => provider.available)}
          onChange={(event) => {
            const provider = apiProviders.find((item) => item.id === planning.apiProvider && item.available);
            const model = provider?.models.find((item) => item.id === event.target.value) || provider?.models[0];
            if (!provider || !model) return;
            setPlanning((prev) => ({
              ...prev,
              apiProvider: provider.id,
              apiModelId: model.id,
              apiOfficialModelId: model.officialModelId,
              apiModelLabel: model.label,
            }));
          }}
        >
          {(apiProviders.find((item) => item.id === planning.apiProvider && item.available)?.models || []).map(
            (model) => (
              <option key={model.id} value={model.id}>
                {model.label}
              </option>
            ),
          )}
        </select>
      </div>

      {/* 9) Compact ENVIRONMENT PLAN summary */}
      <div
        className="environment-creator-plan__summary"
        data-testid="environment-creator-plan-summary"
        style={{
          margin: "0.75rem 0",
          padding: "0.75rem 1rem",
          border: "1px solid var(--border, #2c3346)",
          borderRadius: "0.5rem",
        }}
      >
        <h3 className="environment-creator-plan__section-title" style={{ marginTop: 0 }}>
          ENVIRONMENT PLAN
        </h3>
        <ul style={{ margin: 0, paddingLeft: "1.1rem" }}>
          {planSummary.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </div>

      <div
        className="environment-creator-surface__actions"
        style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", margin: "0.75rem 0", alignItems: "center" }}
      >
        <button
          type="button"
          className="primary"
          data-testid="environment-creator-generate"
          onClick={() => void handleGenerate()}
          disabled={ers.busy || uploadBusy || Boolean(generateBlocked)}
          aria-label="Generate Environment Reference Sheet"
          title={generateBlocked || undefined}
        >
          {ers.busy ? "Generating..." : "Generate Environment Reference Sheet"}
        </button>
        {generateBlocked ? (
          <p className="muted" data-testid="environment-creator-generate-blocked" role="status">
            {generateBlocked}
          </p>
        ) : null}
        {startError || ers.error ? (
          <div data-testid="environment-creator-generate-error" role="alert">
            <p className="muted">{ERS_NOT_CREATED_MESSAGE}</p>
            <details>
              <summary>Technical details</summary>
              <p className="muted">{ers.errorDetail || startError || ers.error}</p>
            </details>
          </div>
        ) : null}
      </div>


      {/* Hydrated project ERS sheets */}
      <div
        className="environment-creator-surface__sheets"
        data-testid="environment-creator-sheets"
        style={{
          margin: "1rem 0 0.5rem",
          padding: "0.75rem 1rem",
          border: "1px solid var(--border, #2c3346)",
          borderRadius: "0.5rem",
        }}
      >
        <h3 className="environment-creator-plan__section-title" style={{ marginTop: 0 }}>
          Project Environment Reference Sheets
        </h3>
        {sheetsLoading ? (
          <p className="muted" data-testid="environment-creator-sheets-loading">
            Loading sheets…
          </p>
        ) : null}
        {sheetsError ? (
          <p className="muted" role="alert" data-testid="environment-creator-sheets-error">
            {sheetsError}
          </p>
        ) : null}
        {!sheetsLoading && !referenceSheets.length ? (
          <p className="muted" data-testid="environment-creator-sheets-empty">
            No environment reference sheets in this project yet.
          </p>
        ) : null}
        {referenceSheets.length ? (
          <ul
            data-testid="environment-creator-sheet-list"
            style={{ listStyle: "none", padding: 0, margin: "0.35rem 0 0", display: "grid", gap: "0.5rem" }}
          >
            {referenceSheets.map((sheet) => {
              const selected = (editCandidate?.sheetId || boundSheetId || ers.sheetId) === sheet.sheetId;
              const composite = sheet.ers_composite_asset_id;
              return (
                <li
                  key={sheet.sheetId}
                  data-testid="environment-creator-sheet-item"
                  data-sheet-id={sheet.sheetId}
                  data-selected={selected ? "true" : "false"}
                  style={{
                    display: "flex",
                    gap: "0.75rem",
                    alignItems: "center",
                    flexWrap: "wrap",
                    padding: "0.45rem 0.5rem",
                    borderRadius: "0.4rem",
                    border: selected ? "1px solid var(--accent, #6ea8fe)" : "1px solid transparent",
                    background: selected ? "rgba(110,168,254,0.08)" : "transparent",
                  }}
                >
                  {composite ? (
                    <button
                      type="button"
                      data-testid="environment-creator-sheet-thumb-button"
                      aria-label={`Open full-size preview of ${ersListDisplayLabel(sheet)}`}
                      onClick={() => {
                        setSheetImagePreview({
                          assetId: composite,
                          title: ersListDisplayLabel(sheet),
                          src: api.assetUrl(composite),
                          kind: isErsSnapshotSheet(sheet) ? "snapshot" : "original",
                        });
                      }}
                      style={{
                        padding: 0,
                        border: "1px solid transparent",
                        background: "transparent",
                        borderRadius: "0.3rem",
                        cursor: "zoom-in",
                        lineHeight: 0,
                      }}
                    >
                      <img
                        src={api.assetUrl(composite)}
                        alt=""
                        data-testid="environment-creator-sheet-thumb"
                        style={{ width: "4.5rem", height: "3rem", objectFit: "cover", borderRadius: "0.3rem", display: "block" }}
                      />
                    </button>
                  ) : (
                    <span
                      aria-hidden
                      style={{
                        width: "4.5rem",
                        height: "3rem",
                        borderRadius: "0.3rem",
                        background: "var(--border, #2c3346)",
                        display: "inline-block",
                      }}
                    />
                  )}
                  <div style={{ flex: "1 1 12rem" }}>
                    <div style={{ fontWeight: 600, display: "flex", gap: "0.4rem", alignItems: "center", flexWrap: "wrap" }}>
                      <span data-testid="environment-creator-sheet-display-name">
                        {ersListDisplayLabel(sheet)}
                      </span>
                      <span
                        className="muted"
                        data-testid={isErsSnapshotSheet(sheet) ? "environment-creator-sheet-snapshot-badge" : "environment-creator-sheet-original-badge"}
                        style={{ fontSize: "0.75em", fontWeight: 500, opacity: 0.85 }}
                      >
                        {isErsSnapshotSheet(sheet) ? "Snapshot" : "Original"}
                      </span>
                    </div>
                    <div className="muted" style={{ fontSize: "0.85em" }}>
                      {environmentReferenceStatusLabel(sheet)}
                      {sheet.updatedAt ? ` · ${sheet.updatedAt}` : ""}
                    </div>
                  </div>
                  <button
                    type="button"
                    className={selected ? "primary" : "secondary"}
                    data-testid="environment-creator-select-sheet"
                    onClick={() => {
                      setEditCandidate({
                        sheetId: sheet.sheetId,
                        sourceAssetId: composite || "",
                        sheetName: sheet.name,
                      });
                      void selectHydratedSheet(sheet.sheetId);
                    }}
                  >
                    {selected ? "Selected" : "Select"}
                  </button>
                  {(() => {
                    const hashTag = promptCanonicalEnvironmentTag(
                      sheet.name,
                      sheet.canonicalTag || sheet.canonical_tag,
                    );
                    return composite && hashTag ? (
                      <span
                        className="environment-creator-surface__tag-row"
                        data-testid="environment-creator-tag-row"
                        style={{ display: "inline-flex", gap: "0.4rem", alignItems: "center", flexWrap: "wrap" }}
                      >
                        <code data-testid="environment-creator-tag">{hashTag}</code>
                        <button
                          type="button"
                          className="character-core__button"
                          data-testid="environment-creator-copy-tag"
                          onClick={() => {
                            void navigator.clipboard.writeText(hashTag);
                          }}
                        >
                          Copy #tag
                        </button>
                      </span>
                    ) : null;
                  })()}
                  {!isErsSnapshotSheet(sheet) ? (
                    <button
                      type="button"
                      className="secondary"
                      data-testid="environment-creator-edit-inpaint"
                      disabled={!composite}
                      onClick={() => {
                        if (!composite) return;
                        setEditCandidate({
                          sheetId: sheet.sheetId,
                          sourceAssetId: composite,
                          sheetName: sheet.name,
                        });
                        setEditOpen(true);
                      }}
                    >
                      Edit / Inpaint
                    </button>
                  ) : null}
                  <EnvironmentDeleteButton
                    placement="row"
                    label={isErsSnapshotSheet(sheet) ? "Delete Snapshot" : "Delete Environment"}
                    disabled={ers.busy || saveBusy || deleting || (Boolean(sheet.projectId) && sheet.projectId !== projectId)}
                    onDelete={() => {
                      if (isErsSnapshotSheet(sheet)) {
                        const masterId = resolveErsEditMasterId(sheet, sheet.sheetId);
                        void (async () => {
                          try {
                            await api.environmentReferenceSheet.deleteSnapshot(
                              projectId,
                              masterId,
                              sheet.sheetId,
                            );
                            await refreshProjectSheets();
                            setErsSubmitFlash(`Removed snapshot ${sheet.name || ""}`.trim());
                            window.setTimeout(() => setErsSubmitFlash(null), 3000);
                          } catch (err) {
                            setSheetsError(
                              err instanceof Error ? err.message : "Could not remove snapshot.",
                            );
                          }
                        })();
                        return;
                      }
                      if (!selected) {
                        setEditCandidate({
                          sheetId: sheet.sheetId,
                          sourceAssetId: composite || "",
                          sheetName: sheet.name,
                        });
                        void selectHydratedSheet(sheet.sheetId);
                      }
                      void handleDeleteClick(sheet.sheetId);
                    }}
                  />
                </li>
              );
            })}
          </ul>
        ) : null}
        {draftSheets.length ? (
          <div data-testid="environment-creator-drafts" style={{ marginTop: "0.85rem" }}>
            <h3 className="environment-creator-plan__section-title">Environment drafts</h3>
            <ul
              data-testid="environment-creator-draft-list"
              style={{ listStyle: "none", padding: 0, margin: "0.35rem 0 0", display: "grid", gap: "0.5rem" }}
            >
              {draftSheets.map((sheet) => {
                const selected = (editCandidate?.sheetId || boundSheetId) === sheet.sheetId;
                const current =
                  selected ||
                  (normalizeProfileName(sheet.name) === normalizeProfileName(planning.name) &&
                    (ers.busy || ers.phase === "failed"));
                return (
                  <li
                    key={sheet.sheetId}
                    data-testid="environment-creator-draft-item"
                    data-sheet-id={sheet.sheetId}
                    style={{ display: "flex", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}
                  >
                    <div style={{ flex: "1 1 12rem" }}>
                      <div style={{ fontWeight: 600 }}>{sheet.name || "Untitled environment"}</div>
                      <div className="muted" style={{ fontSize: "0.85em" }}>
                        {environmentDraftStatusLabel({
                          generating: Boolean(current && ers.busy),
                          failed: Boolean(current && !ers.busy && ers.phase === "failed"),
                        })}
                      </div>
                    </div>
                    <button
                      type="button"
                      className={selected ? "primary" : "secondary"}
                      data-testid="environment-creator-select-draft"
                      onClick={() => {
                        setEditCandidate({
                          sheetId: sheet.sheetId,
                          sourceAssetId: "",
                          sheetName: sheet.name,
                        });
                        void selectHydratedSheet(sheet.sheetId);
                      }}
                    >
                      {selected ? "Selected" : "Continue"}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        ) : null}
        {(editCandidate?.sourceAssetId || ers.compositeAssetId || ers.progress.finalAssetId) && !sessionActive ? (
          <div data-testid="environment-creator-hydrated-preview" style={{ marginTop: "0.75rem" }}>
            {(() => {
              const sel =
                projectSheets.find((s) => s.sheetId === (editCandidate?.sheetId || boundSheetId || ers.sheetId)) ||
                null;
              const hashTag = promptCanonicalEnvironmentTag(
                sel?.name || editCandidate?.sheetName || planning.name,
                sel?.canonicalTag || sel?.canonical_tag,
              );
              return hashTag ? (
                <div
                  className="environment-creator-surface__tag-row"
                  data-testid="environment-creator-preview-tag-row"
                  style={{ display: "flex", gap: "0.5rem", alignItems: "center", marginBottom: "0.5rem", flexWrap: "wrap" }}
                >
                  <code data-testid="environment-creator-preview-tag">{hashTag}</code>
                  <button
                    type="button"
                    className="character-core__button"
                    data-testid="environment-creator-preview-copy-tag"
                    onClick={() => {
                      void navigator.clipboard.writeText(hashTag);
                    }}
                  >
                    Copy #tag
                  </button>
                </div>
              ) : null;
            })()}
            <img
              src={api.assetUrl(editCandidate?.sourceAssetId || ers.compositeAssetId || ers.progress.finalAssetId || "")}
              alt="Selected ERS composite"
              style={{ maxWidth: "100%", maxHeight: "220px", objectFit: "contain", borderRadius: "0.4rem" }}
            />
          </div>
        ) : null}
      </div>

      {!sessionActive ? (
        <div
          className="environment-creator-surface__empty"
          data-testid="environment-creator-empty"
          role="status"
          style={{
            marginTop: "1rem",
            padding: "1.25rem 1rem",
            border: "1px dashed var(--border, #2c3346)",
            borderRadius: "0.6rem",
            textAlign: "center",
          }}
        >
          <p style={{ margin: "0 0 0.35rem", fontWeight: 600 }}>No Environment Reference Sheet selected</p>
          <p className="muted" style={{ margin: 0 }}>
            Generate a new ERS, or select a project sheet above to preview and Edit / Inpaint.
          </p>
        </div>
      ) : (
        <ERSGenerationMonitor
          state={ers}
          onRetry={() => void ers.retry()}
          onOpenInLibrary={() => onGoTab?.("library")}
          onUseInSceneCreator={() => void handleUseInSceneCreator()}
          onOpenFullSize={handleOpenFullSize}
          onUseAnyway={() => void ers.useAnyway()}
          onEditInpaint={openEditInpaint}
        />
      )}

      {editOpen && editCandidate ? (
        <ErsEditModal
          projectId={projectId}
          sheetId={editCandidate.sheetId}
          sourceAssetId={editCandidate.sourceAssetId}
          sheetName={editCandidate.sheetName}
          apiProvider={planning.apiProvider}
          apiModelId={planning.apiModelId}
          apiOfficialModelId={planning.apiOfficialModelId}
          apiModelLabel={planning.apiModelLabel}
          onClose={() => setEditOpen(false)}
          onDerivativeReady={(info) => {
            setLastDerivativeId(info.derivativeAssetId);
          }}
          onViewportRefresh={(info) => {
            setEditCandidate((prev) => ({
              sheetId: info.sheetId || prev?.sheetId || "",
              sourceAssetId: info.sourceAssetId,
              sheetName: info.sheetName || prev?.sheetName,
            }));
            setLastDerivativeId(info.sourceAssetId);
          }}
          onSubmitAccepted={(info) => {
            if (info.kind === "snapshot_capture" || info.kind === "annotation_only") {
              setPendingErsEdit(null);
              setErsSubmitFlash(
                info.kind === "snapshot_capture"
                  ? info.snapshotName
                    ? `Snapshot captured: ${info.snapshotName}`
                    : info.message
                  : info.message,
              );
              window.setTimeout(() => setErsSubmitFlash(null), 4000);
              void refreshProjectSheets();
              return;
            }
            // Legacy image-edit path retained for older sessions; Submit no longer enqueues.
            setErsSubmitFlash(null);
            setPendingErsEdit({
              kind: "image_edit",
              jobId: info.jobId || null,
              status: ersEditPendingStatusLabel(info.status || "pending"),
              message: info.message,
              sheetId: info.sheetId,
              sourceAssetId: info.sourceAssetId,
              derivativeAssetId: info.derivativeAssetId || null,
            });
            if (info.derivativeAssetId) {
              setLastDerivativeId(info.derivativeAssetId);
            }
          }}
        />
      ) : null}

      {ersSubmitFlash ? (
        <p className="muted" role="status" data-testid="environment-creator-ers-submit-flash" style={{ marginTop: "0.75rem" }}>
          {ersSubmitFlash}
        </p>
      ) : null}

      {pendingErsEdit && pendingErsEdit.kind === "image_edit" ? (
        <p
          className="muted"
          role="status"
          data-testid="environment-creator-ers-edit-pending"
          data-status={pendingErsEdit.status}
          data-job-id={pendingErsEdit.jobId || ""}
          style={{ marginTop: "0.75rem" }}
        >
          {pendingErsEdit.status === "completed"
            ? pendingErsEdit.message
            : pendingErsEdit.status === "failed" ||
                pendingErsEdit.status === "error" ||
                pendingErsEdit.status === "cancelled"
              ? pendingErsEdit.message
              : `ERS edit ${pendingErsEdit.status}${
                  pendingErsEdit.jobId ? ` (job ${pendingErsEdit.jobId.slice(0, 8)}…)` : ""
                }.`}
        </p>
      ) : null}

      {lastDerivativeId ? (
        <p className="muted" data-testid="environment-creator-last-derivative" style={{ marginTop: "0.75rem" }}>
          Last edit derivative: {lastDerivativeId} (Version Approve required to promote — not auto-approved)
        </p>
      ) : null}

      <ErsSheetImagePreviewModal
        preview={sheetImagePreview}
        onClose={() => setSheetImagePreview(null)}
      />
      <CreatorProfileDeleteModal
        open={deleteModalOpen}
        entityType="environment"
        preview={deletePreview}
        deleting={deleting}
        onClose={() => {
          if (!deleting) {
            setDeleteModalOpen(false);
            setDeletePreview(null);
          }
        }}
        onConfirm={() => void handleConfirmDelete()}
      />

      <div className="environment-creator-surface__save-row" data-testid="environment-creator-save-bottom-row">
        <EnvironmentSaveButton
          placement="bottom"
          busy={saveBusy}
          dirty={dirty}
          feedback={saveFeedback}
          onSave={() => void saveEnvironment()}
        />
        <EnvironmentDeleteButton
          placement="bottom"
          disabled={!selectedSheetId || !selectedSheetOwned || saveBusy || ers.busy || deleting}
          onDelete={() => void handleDeleteClick()}
        />
        {saveError ? (
          <p className="muted" data-testid="environment-creator-save-error-bottom" role="alert">
            {saveError}
          </p>
        ) : null}
      </div>
    </section>
  );
}
