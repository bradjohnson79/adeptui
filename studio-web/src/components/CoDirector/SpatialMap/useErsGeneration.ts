/**
 * Shared ERS generation hook for Spatial Map Express + Standard.
 * One path: Spatial Map -> ers.generate -> Image Core -> persist composite.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../../api";
import { isTerminal, type WorkSurfaceState } from "../AgentWorkSurface/types";
import { normalizeErsError } from "./ersErrorMessage";
import {
  ERS_GENERATOR_DEFAULT,
  buildErsStartContext,
  formatErsProvenance,
  generatorBlockReason,
  isGptImage2Ready,
  isQwenReady,
  provenanceModelFromSelection,
  resolveErsGeneratorFromModel,
  type ErsGeneratorId,
} from "./ersGenerator";
import { normalizeJobProgress, type NormalizedJobProgress } from "./normalizeJobProgress";
import type { SpatialMapDocument } from "./types";

export type ErsPhase = "idle" | "queued" | "generating" | "complete" | "failed";

export type ErsModelLine = {
  model: string;
  sourceKind: "Local" | "API" | null;
};

export type ErsContextCounts = {
  environment: number;
  characters: number;
  props: number;
  cameras: number;
};

/** Advisory VLM verdict stamped on sheet provenance by the worker. */
export type ErsSemanticGate = {
  verdict: "PASS" | "ERS_LAYOUT_NONCOMPLIANT" | "ERS_CONTEXT_NONCOMPLIANT" | "NOT_VERIFIED";
  summary?: string;
  model?: string;
  checkedAt?: string;
};

export type ErsGenerationState = {
  phase: ErsPhase;
  busy: boolean;
  executionId: string | null;
  jobId: string | null;
  progress: NormalizedJobProgress;
  model: ErsModelLine;
  provenance: string;
  counts: ErsContextCounts;
  elapsedSec: number;
  error: string | null;
  errorDetail: string | null;
  compositeAssetId: string | null;
  zombie: boolean;
  selectedGenerator: ErsGeneratorId;
  qwenReady: boolean | null;
  gptReady: boolean | null;
  generatorBlockReason: string | null;
  sheetId: string | null;
  semanticGate: ErsSemanticGate | null;
  gateOverride: boolean;
  /** Lineage changed since the persisted sheet was generated. */
  stale: boolean;
};

const POLL_MS = 2500;
const ZOMBIE_STATUSES = new Set(["failed", "error", "cancelled", "canceled", "interrupted", "dead", "missing"]);

/** Last choice survives Express/Standard remounts without a second store. */
let lastErsGeneratorId: ErsGeneratorId = ERS_GENERATOR_DEFAULT;

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

function parseJson(raw: unknown): Record<string, unknown> {
  if (!raw) return {};
  if (typeof raw === "object") return asRecord(raw);
  if (typeof raw !== "string") return {};
  try {
    return asRecord(JSON.parse(raw));
  } catch {
    return {};
  }
}

export function normalizeExecution(res: any, fallbackCapability = "ers.generate"): WorkSurfaceState {
  return {
    mode: "agent_work",
    execution_id: String(res?.execution_id || res?.executionId || res?.id || ""),
    capability: String(res?.capability || fallbackCapability),
    surface_type: (res?.surface_type || res?.surfaceType || "ers_generation") as WorkSurfaceState["surface_type"],
    status: String(res?.status || "running"),
    progress: Number(res?.progress || 0),
    focused_artifact_ids: Array.isArray(res?.focused_artifact_ids) ? res.focused_artifact_ids : [],
    child_jobs: Array.isArray(res?.child_jobs) ? res.child_jobs : [],
    result_asset_ids: Array.isArray(res?.result_asset_ids) ? res.result_asset_ids : [],
    collection_id: res?.collection_id ?? null,
    error: res?.error ?? null,
    project_id: res?.project_id || res?.projectId || "",
  };
}

export function formatResolvedModel(source: {
  provider?: string | null;
  model?: string | null;
  metadata?: Record<string, unknown>;
  params?: Record<string, unknown>;
}): ErsModelLine {
  const meta = source.metadata || {};
  const params = source.params || {};
  const provider = String(
    source.provider || meta.resolvedProvider || params.providerKind || params.provider_kind || params.provider || "",
  ).toLowerCase();
  const model = String(
    source.model ||
      meta.resolvedOfficialModelId ||
      meta.resolvedWorkflowKey ||
      meta.resolvedModel ||
      params.hostedModelId ||
      params.model ||
      params.kieImageModelId ||
      params.falImageModelId ||
      "",
  ).trim();
  const sourceKind: ErsModelLine["sourceKind"] = !provider
    ? null
    : provider === "local" || provider === "comfy"
      ? "Local"
      : "API";
  return { model, sourceKind };
}

function countsFromDocument(document: SpatialMapDocument | null | undefined): ErsContextCounts {
  return {
    environment: document?.backgroundAssetId ? 1 : 0,
    characters: document?.characters?.length || 0,
    props: document?.props?.length || 0,
    cameras: document?.cameras?.length || 0,
  };
}

function executionSpatialMapId(res: any): string {
  const plan = asRecord(res);
  const planData = asRecord(plan.plan_data);
  if (typeof planData.spatial_map_id === "string") return planData.spatial_map_id;
  const kids = Array.isArray(plan.child_jobs) ? plan.child_jobs : [];
  for (const child of kids) {
    const meta = asRecord(asRecord(child).metadata);
    if (typeof meta.spatial_map_id === "string") return meta.spatial_map_id;
  }
  return "";
}

function childJobId(exec: WorkSurfaceState | null): string | null {
  const id = exec?.child_jobs?.[0]?.job_id;
  return id ? String(id) : null;
}

type Args = {
  projectId: string;
  spatialMapId: string | null;
  document?: SpatialMapDocument | null;
  activeExecution: WorkSurfaceState | null | undefined;
  setActiveExecution: (next: WorkSurfaceState | null) => void;
  attachOnly?: boolean;
};

const IDLE_PROGRESS: NormalizedJobProgress = {
  status: "idle",
  progressPercent: null,
  stage: "",
  message: "",
  indeterminate: false,
  previewUrl: null,
  finalAssetId: null,
  genuineSampler: false,
};

export function useErsGeneration({
  projectId,
  spatialMapId,
  document,
  activeExecution,
  setActiveExecution,
  attachOnly = false,
}: Args) {
  const inFlightRef = useRef(false);
  const startedAtRef = useRef<number | null>(null);
  const [phase, setPhase] = useState<ErsPhase>("idle");
  const [busy, setBusy] = useState(false);
  const [executionId, setExecutionId] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [progress, setProgress] = useState<NormalizedJobProgress>(IDLE_PROGRESS);
  const [model, setModel] = useState<ErsModelLine>({ model: "", sourceKind: null });
  const [elapsedSec, setElapsedSec] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [errorDetail, setErrorDetail] = useState<string | null>(null);
  const [compositeAssetId, setCompositeAssetId] = useState<string | null>(null);
  const [zombie, setZombie] = useState(false);
  const [selectedGenerator, setSelectedGeneratorState] = useState<ErsGeneratorId>(lastErsGeneratorId);
  const [qwenReady, setQwenReady] = useState<boolean | null>(null);
  const [gptReady, setGptReady] = useState<boolean | null>(null);
  const [sheetId, setSheetId] = useState<string | null>(null);
  const [semanticGate, setSemanticGate] = useState<ErsSemanticGate | null>(null);
  const [gateOverride, setGateOverride] = useState(false);
  const [sheetFingerprint, setSheetFingerprint] = useState<string | null>(null);

  const counts = useMemo(() => countsFromDocument(document), [document]);
  const blockReason = useMemo(
    () => generatorBlockReason(selectedGenerator, qwenReady, gptReady),
    [gptReady, qwenReady, selectedGenerator],
  );
  const provenance = useMemo(() => formatErsProvenance(model), [model]);

  // Staleness (W5): the persisted sheet's grounding fingerprint vs the live
  // document lineage. A legacy sheet (no fingerprint) counts as stale once the
  // document carries a Scene Intent — it was generated without grounding.
  const docFingerprint = document?.groundingFingerprint || null;
  const stale = useMemo(() => {
    if (!compositeAssetId) return false;
    if (docFingerprint && sheetFingerprint) return docFingerprint !== sheetFingerprint;
    if (!sheetFingerprint && document?.sceneIntent) return true;
    return false;
  }, [compositeAssetId, docFingerprint, sheetFingerprint, document?.sceneIntent]);

  const applySheetProvenance = useCallback((sheet: Record<string, unknown> | null | undefined) => {
    if (!sheet) return;
    const details = asRecord(asRecord(sheet.provenance).details);
    const gate = asRecord(details.semanticGate);
    if (typeof gate.verdict === "string" && gate.verdict) {
      setSemanticGate({
        verdict: gate.verdict as ErsSemanticGate["verdict"],
        summary: typeof gate.summary === "string" ? gate.summary : "",
        model: typeof gate.model === "string" ? gate.model : "",
        checkedAt: typeof gate.checkedAt === "string" ? gate.checkedAt : "",
      });
    }
    if (asRecord(details.semanticGateOverride).decision === "use_anyway") {
      setGateOverride(true);
    }
    const fp = typeof details.groundingFingerprint === "string" ? details.groundingFingerprint : "";
    if (fp) setSheetFingerprint(fp);
  }, []);

  const refreshSheetState = useCallback(async (): Promise<void> => {
    if (!projectId || !spatialMapId) return;
    try {
      const listed = await api.environmentReferenceSheet.listSheets(projectId);
      const sheets = (listed.sheets || []) as Array<{
        sheetId?: string;
        updatedAt?: string;
        ers_composite_asset_id?: string | null;
      }>;
      const withAsset = [...sheets]
        .filter((s) => s.ers_composite_asset_id)
        .sort((a, b) => String(b.updatedAt || "").localeCompare(String(a.updatedAt || "")));
      for (const summary of withAsset.slice(0, 6)) {
        if (!summary.sheetId || !summary.ers_composite_asset_id) continue;
        let full: Record<string, unknown> | null = null;
        try {
          full = asRecord(await api.environmentReferenceSheet.getSheet(projectId, summary.sheetId));
          const mapId = asRecord(asRecord(full.sheet).spatialMap).mapId;
          if (mapId && String(mapId) !== spatialMapId) continue;
        } catch {
          // summary asset is still usable
        }
        setSheetId(summary.sheetId);
        setCompositeAssetId(summary.ers_composite_asset_id);
        if (full) applySheetProvenance(asRecord(full.sheet));
        return;
      }
    } catch {
      // sheet state is best-effort
    }
  }, [applySheetProvenance, projectId, spatialMapId]);

  const useAnyway = useCallback(async () => {
    if (!projectId || !sheetId) return;
    try {
      await api.environmentReferenceSheet.useAnyway(projectId, sheetId);
      setGateOverride(true);
    } catch {
      // surfaced on next refresh; the banner remains visible
    }
  }, [projectId, sheetId]);

  const setSelectedGenerator = useCallback((id: ErsGeneratorId) => {
    lastErsGeneratorId = id;
    setSelectedGeneratorState(id);
  }, []);

  const applyProgress = useCallback((jobLike: unknown, exec?: WorkSurfaceState | null) => {
    const normalized = normalizeJobProgress(jobLike);
    setProgress(normalized);
    const child = exec?.child_jobs?.[0];
    const params = parseJson((jobLike as { params_json?: string })?.params_json);
    const nextModel = formatResolvedModel({
      provider: (exec as { provider?: string } | null)?.provider,
      model: (exec as { model?: string } | null)?.model,
      metadata: asRecord(child?.metadata),
      params,
    });
    setModel(nextModel);
    const reconnect = resolveErsGeneratorFromModel(nextModel);
    if (reconnect) {
      lastErsGeneratorId = reconnect;
      setSelectedGeneratorState(reconnect);
    }
    if (normalized.finalAssetId) setCompositeAssetId(normalized.finalAssetId);
    return normalized;
  }, []);

  const markLive = useCallback((nextPhase: ErsPhase) => {
    setPhase(nextPhase);
    setBusy(nextPhase === "queued" || nextPhase === "generating");
    if (nextPhase === "queued" || nextPhase === "generating") {
      if (!startedAtRef.current) startedAtRef.current = Date.now();
    }
  }, []);

  const attachExecution = useCallback(
    (exec: WorkSurfaceState, jobLike?: unknown) => {
      if (!exec.execution_id) return;
      inFlightRef.current = !isTerminal(exec);
      setExecutionId(exec.execution_id);
      setJobId(childJobId(exec));
      setActiveExecution(exec);
      const resultId = exec.result_asset_ids?.[exec.result_asset_ids.length - 1] || null;
      if (resultId) setCompositeAssetId(resultId);
      const jobProgress = applyProgress(
        jobLike || {
          status: exec.status,
          progress: exec.progress,
          stage: exec.child_jobs?.[0]?.stage || exec.status,
          message: (exec.child_jobs?.[0] as { message?: string } | undefined)?.message || exec.error || "",
          asset_id: resultId,
        },
        exec,
      );
      if (isTerminal(exec) && exec.status === "completed") {
        inFlightRef.current = false;
        setZombie(false);
        markLive("complete");
        setBusy(false);
        return;
      }
      if (isTerminal(exec) && (exec.status === "failed" || exec.status === "cancelled")) {
        inFlightRef.current = false;
        setZombie(false);
        setError(normalizeErsError(exec.error || jobProgress.message));
        setErrorDetail(exec.error || jobProgress.message || null);
        markLive("failed");
        setBusy(false);
        return;
      }
      setZombie(false);
      markLive(exec.status === "queued" || exec.status === "preparing" ? "queued" : "generating");
    },
    [applyProgress, markLive, setActiveExecution],
  );

  const pollOnce = useCallback(async () => {
    if (!projectId || !executionId) return;
    let exec: WorkSurfaceState | null = null;
    try {
      const res = await api.advanceExecution(projectId, executionId);
      exec = normalizeExecution(res, "ers.generate");
      setActiveExecution(exec);
    } catch {
      exec = activeExecution && activeExecution.execution_id === executionId ? activeExecution : null;
    }
    const jid = childJobId(exec) || jobId;
    if (jid) setJobId(jid);
    let jobRow: Record<string, unknown> | null = null;
    if (jid) {
      try {
        jobRow = asRecord(await api.getJob(jid));
      } catch (err) {
        const missing = err instanceof Error && /not found|404/i.test(err.message);
        if (missing || !jobRow) {
          setZombie(true);
          inFlightRef.current = false;
          setError(normalizeErsError("ERS job is missing or interrupted"));
          setErrorDetail(err instanceof Error ? err.message : String(err));
          markLive("failed");
          setBusy(false);
          return;
        }
      }
    }
    if (jobRow) {
      const rawStatus = String(jobRow.status || "").toLowerCase();
      if (ZOMBIE_STATUSES.has(rawStatus) && (phase === "queued" || exec?.status === "queued")) {
        setZombie(true);
        inFlightRef.current = false;
        setError(normalizeErsError(String(jobRow.message || "ERS job failed before it started")));
        setErrorDetail(String(jobRow.message || jobRow.status || ""));
        applyProgress(jobRow, exec);
        markLive("failed");
        setBusy(false);
        return;
      }
      const normalized = applyProgress(jobRow, exec);
      if (normalized.status === "completed") {
        const asset =
          normalized.finalAssetId ||
          exec?.result_asset_ids?.[exec.result_asset_ids.length - 1] ||
          null;
        if (asset) setCompositeAssetId(asset);
        inFlightRef.current = false;
        setZombie(false);
        markLive("complete");
        setBusy(false);
        // Pick up the semantic gate verdict + lineage fingerprint stamped by
        // the worker after persist. One delayed refresh covers the async gate.
        void refreshSheetState();
        window.setTimeout(() => void refreshSheetState(), 15000);
        return;
      }
      if (normalized.status === "failed" || normalized.status === "cancelled") {
        inFlightRef.current = false;
        setError(normalizeErsError(normalized.message || exec?.error));
        setErrorDetail(normalized.message || exec?.error || null);
        markLive("failed");
        setBusy(false);
        return;
      }
      markLive(normalized.status === "queued" ? "queued" : "generating");
      return;
    }
    if (exec) attachExecution(exec);
  }, [activeExecution, applyProgress, attachExecution, executionId, jobId, markLive, phase, projectId, setActiveExecution]);

  const start = useCallback(async () => {
    if (attachOnly) return;
    if (!projectId || !spatialMapId) return;
    if (inFlightRef.current || busy) return;
    const blocked = generatorBlockReason(selectedGenerator, qwenReady, gptReady);
    if (blocked) {
      setError(blocked);
      setErrorDetail(null);
      return;
    }
    inFlightRef.current = true;
    setError(null);
    setErrorDetail(null);
    setZombie(false);
    startedAtRef.current = Date.now();
    setElapsedSec(0);
    setPhase("queued");
    setBusy(true);
    setModel(provenanceModelFromSelection(selectedGenerator));
    setProgress({
      status: "queued",
      progressPercent: null,
      stage: "Queued",
      message: "Preparing ERS generation…",
      indeterminate: true,
      previewUrl: null,
      finalAssetId: null,
      genuineSampler: false,
    });
    try {
      const res = await api.startExecution(projectId, {
        capability: "ers.generate",
        context: {
          spatial_map_id: spatialMapId,
          ...buildErsStartContext(selectedGenerator),
        },
      });
      const exec = normalizeExecution(res, "ers.generate");
      attachExecution(exec);
    } catch (err) {
      inFlightRef.current = false;
      const raw = err instanceof Error ? err.message : String(err);
      setError(normalizeErsError(raw));
      setErrorDetail(raw);
      markLive("failed");
      setBusy(false);
    }
  }, [attachOnly, attachExecution, busy, gptReady, markLive, projectId, qwenReady, selectedGenerator, spatialMapId]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const listed = await api.imageStudio.listProviders(true);
        const providers = Array.isArray(listed?.providers) ? listed.providers : [];
        if (!cancelled) {
          setQwenReady(isQwenReady(providers));
          setGptReady(isGptImage2Ready(providers));
        }
      } catch {
        if (!cancelled) {
          setQwenReady(false);
          setGptReady(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!projectId || !spatialMapId) return;
    let cancelled = false;
    void (async () => {
      try {
        const listed = await api.listExecutions(projectId, true);
        const rows = Array.isArray(listed?.executions) ? listed.executions : Array.isArray(listed) ? listed : [];
        const match = rows.find((row: any) => {
          const cap = String(row?.capability || "");
          if (cap !== "ers.generate") return false;
          if (isTerminal(normalizeExecution(row, "ers.generate"))) return false;
          const mapId = executionSpatialMapId(row);
          return !mapId || mapId === spatialMapId;
        });
        if (!cancelled && match && !inFlightRef.current) {
          attachExecution(normalizeExecution(match, "ers.generate"));
        }
      } catch {
        // reconnect is best-effort
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [attachExecution, projectId, spatialMapId]);

  useEffect(() => {
    if (!projectId || !spatialMapId || compositeAssetId) return;
    let cancelled = false;
    void (async () => {
      const before = compositeAssetId;
      await refreshSheetState();
      if (!cancelled && !before) {
        setCompositeAssetId((current) => {
          if (current && phase === "idle") {
            setPhase("complete");
            setProgress({
              status: "completed",
              progressPercent: 100,
              stage: "Complete",
              message: "Environment Reference Sheet generated.",
              indeterminate: false,
              previewUrl: null,
              finalAssetId: current,
              genuineSampler: false,
            });
          }
          return current;
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [compositeAssetId, phase, projectId, refreshSheetState, spatialMapId]);

  useEffect(() => {
    if (!executionId || !busy) return;
    const timer = window.setTimeout(() => {
      void pollOnce();
    }, POLL_MS);
    return () => window.clearTimeout(timer);
  }, [busy, executionId, pollOnce, progress.status, progress.stage]);

  useEffect(() => {
    if (!busy || !startedAtRef.current) return;
    const timer = window.setInterval(() => {
      if (!startedAtRef.current) return;
      setElapsedSec(Math.max(0, Math.round((Date.now() - startedAtRef.current) / 1000)));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [busy]);

  useEffect(() => {
    if (!activeExecution?.execution_id) return;
    if (activeExecution.capability && activeExecution.capability !== "ers.generate") return;
    if (activeExecution.surface_type && activeExecution.surface_type !== "ers_generation") return;
    if (executionId && executionId !== activeExecution.execution_id && inFlightRef.current) return;
    if (!executionId || executionId === activeExecution.execution_id) {
      if (isTerminal(activeExecution) && phase !== "idle") {
        attachExecution(activeExecution);
      }
    }
  }, [activeExecution, attachExecution, executionId, phase]);

  const state: ErsGenerationState = {
    phase,
    busy,
    executionId,
    jobId,
    progress,
    model,
    provenance,
    counts,
    elapsedSec,
    error,
    errorDetail,
    compositeAssetId,
    zombie,
    selectedGenerator,
    qwenReady,
    gptReady,
    generatorBlockReason: blockReason,
    sheetId,
    semanticGate,
    gateOverride,
    stale,
  };

  return {
    ...state,
    start,
    retry: start,
    setSelectedGenerator,
    useAnyway,
    refreshSheetState,
  };
}
