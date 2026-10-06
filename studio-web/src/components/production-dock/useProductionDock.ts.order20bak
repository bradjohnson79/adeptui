import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../../api";
import type {
  ApiModelsSectionMeta,
  Modality,
  ModalityModelSections,
  ModelDescriptor,
  ProductionControlStatus,
  ProductionDockMenu,
  ProductionQueueSnapshot,
  ProviderSwitchPreview,
  ResolvedSelection,
  UserGlobalPreferences,
} from "../../modelRegistry/contracts";
import { applyTheme, watchSystemTheme } from "../../theme/applyTheme";

type DockState = {
  status: ProductionControlStatus | null;
  preferences: UserGlobalPreferences | null;
  models: Partial<Record<Modality, ModelDescriptor[]>>;
  sections: Partial<Record<Modality, ModalityModelSections>>;
  apiMeta: Partial<Record<Modality, ApiModelsSectionMeta>>;
  resolved: Partial<Record<Modality, ResolvedSelection>>;
  queue: ProductionQueueSnapshot | null;
  loading: boolean;
  error: string | null;
  collapsed: boolean;
  openMenu: ProductionDockMenu;
  providerModalOpen: boolean;
  providerSwitch: ProviderSwitchPreview | null;
  providerSwitchToken: string | null;
};

const DEFAULT_PREFS: UserGlobalPreferences = {
  theme: "aurora-night",
  dockCollapsed: true,
  dockAutoCollapse: true,
  runtimeSource: "hybrid",
  runtimeLocalEnabled: true,
  runtimeApiEnabled: true,
  defaultHostedProviderId: "automatic",
  cpuFallbackPolicy: "disabled",
};

function routingKey(modality: Modality): keyof UserGlobalPreferences {
  if (modality === "llm") return "llmRouting";
  if (modality === "video") return "videoRouting";
  if (modality === "image") return "imageRouting";
  return "audioRouting";
}

export function useProductionDock() {
  const params = useParams();
  const projectId = params.id ?? null;
  const [state, setState] = useState<DockState>({
    status: null,
    preferences: null,
    models: {},
    sections: {},
    apiMeta: {},
    resolved: {},
    queue: null,
    loading: true,
    error: null,
    collapsed: true,
    openMenu: null,
    providerModalOpen: false,
    providerSwitch: null,
    providerSwitchToken: null,
  });
  const autoCollapseTimer = useRef<number | null>(null);
  const refreshInFlight = useRef(false);
  const refreshAbort = useRef<AbortController | null>(null);

  const discoveryAttempted = useRef(false);

  const refresh = useCallback(async () => {
    // Phase CK — suspend when central health monitor reports API offline
    const { shouldSuspendDependentPolling } = await import("../../runtime/studioApiConnection");
    if (shouldSuspendDependentPolling()) { return; }

    // Phase CK — single in-flight guard: prevent overlapping refreshes
    if (refreshInFlight.current) return;
    refreshInFlight.current = true;

    // Cancel any pending stale refresh
    if (refreshAbort.current) refreshAbort.current.abort();
    refreshAbort.current = new AbortController();

    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const [status, prefs, gate] = await Promise.all([
        api.productionControlStatus(projectId ?? undefined),
        api.productionControlGetPreferences(),
        api.productionControlGate().catch(() => null),
      ]);
      // If a primary provider is connected but the normalized catalog is empty, run discovery once.
      if (!discoveryAttempted.current) {
        try {
          const discovery = await api.hostedProvidersDiscoveryStatus();
          if ((discovery?.modelCount ?? 0) === 0 && discovery?.activeProviderId == null) {
            discoveryAttempted.current = true;
            await api.hostedProvidersDiscover().catch(() => null);
          } else {
            discoveryAttempted.current = true;
          }
        } catch {
          discoveryAttempted.current = true;
        }
      }
      const preferences = { ...DEFAULT_PREFS, ...prefs };
      const modalities: Modality[] = ["llm", "video", "image", "audio"];
      const [modelsEntries, resolvedResult] = await Promise.all([
        Promise.all(
          modalities.map(async (modality) => {
            try {
              const list = await api.productionControlModels(modality);
              const local = list.sections?.local ?? (list.models ?? []).filter((m) => m.locality === "local");
              const apiModels = list.sections?.api ?? [];
              const apiMeta: ApiModelsSectionMeta = {
                activeProviderId: list.api?.activeProviderId,
                emptyReason: list.api?.emptyReason,
                emptyMessage: list.api?.emptyMessage,
                summary: list.api?.summary,
                updatedAt: list.api?.updatedAt,
              };
              const sections: ModalityModelSections = {
                local,
                api: apiModels,
                apiMeta,
              };
              return [modality, list.models ?? list, sections, apiMeta] as const;
            } catch {
              return [
                modality,
                [] as ModelDescriptor[],
                { local: [], api: [] } as ModalityModelSections,
                {} as ApiModelsSectionMeta,
              ] as const;
            }
          }),
        ),
        // Phase CK — single batch resolved call (replaces 4 parallel /resolve requests)
        api.productionControlResolved(projectId ?? undefined).catch(() => null),
      ]);
      let queue: ProductionQueueSnapshot | null = null;
      try {
        queue = await api.productionControlQueue(projectId ?? undefined);
      } catch {
        queue = status.queueSummary
          ? {
              jobs: [],
              gpuQueued: status.queueSummary.gpuQueued ?? 0,
              hostedQueued: status.queueSummary.hostedQueued ?? 0,
              active: status.queueSummary.active ?? 0,
            }
          : null;
      }
      const models = Object.fromEntries(modelsEntries.map(([m, list]) => [m, list])) as Partial<
        Record<Modality, ModelDescriptor[]>
      >;
      const sections = Object.fromEntries(modelsEntries.map(([m, , sec]) => [m, sec])) as Partial<
        Record<Modality, ModalityModelSections>
      >;
      const apiMeta = Object.fromEntries(modelsEntries.map(([m, , , meta]) => [m, meta])) as Partial<
        Record<Modality, ApiModelsSectionMeta>
      >;
      const resolved: Partial<Record<Modality, ResolvedSelection>> = {};
      // Phase CK — batch resolved: unwrap {resolved:{llm:{ok,selection},...}} or fall back to per-modality status
      if (resolvedResult?.resolved) {
        for (const mod of modalities) {
          const entry = resolvedResult.resolved[mod];
          if (entry?.selection) {
            resolved[mod] = entry.selection as ResolvedSelection;
          }
        }
      } else {
        // Fallback: use status modalities
        for (const mod of modalities) {
          const m = status.modalities?.[mod];
          if (m) resolved[mod] = m as unknown as ResolvedSelection;
        }
      }
      applyTheme(preferences.theme);
      setState((s) => ({
        ...s,
        status: { ...status, ok: gate?.productionDockGo ?? status.ok ?? true },
        preferences,
        models,
        sections,
        apiMeta,
        resolved,
        queue,
        collapsed: preferences.dockCollapsed,
        loading: false,
        error: null,
      }));
    } catch (err) {
      setState((s) => ({
        ...s,
        loading: false,
        error: err instanceof Error ? err.message : String(err),
      }));
    } finally {
      refreshInFlight.current = false;
    }
  }, [projectId]);

  useEffect(() => {
    void refresh();
    const interval = window.setInterval(() => {
      if (document.visibilityState === "visible") void refresh();
    }, 20_000);
    const onVisible = () => {
      if (document.visibilityState === "visible") void refresh();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisible);
      if (refreshAbort.current) refreshAbort.current.abort();
    };
  }, [refresh]);

  useEffect(() => {
    const pref = state.preferences?.theme ?? "aurora-night";
    if (pref !== "system") return watchSystemTheme(() => undefined);
    return watchSystemTheme(() => applyTheme("system"));
  }, [state.preferences?.theme]);

  const patchPreferences = useCallback(async (patch: Partial<UserGlobalPreferences>) => {
    const next = await api.productionControlPutPreferences(patch);
    const merged = { ...DEFAULT_PREFS, ...next, ...patch };
    if (patch.theme) applyTheme(merged.theme);
    setState((s) => ({
      ...s,
      preferences: merged,
      collapsed: patch.dockCollapsed ?? s.collapsed,
    }));
    return merged;
  }, []);

  const setCollapsed = useCallback(
    async (collapsed: boolean) => {
      setState((s) => ({ ...s, collapsed }));
      try {
        await patchPreferences({ dockCollapsed: collapsed });
      } catch {
        /* local UI still toggles */
      }
    },
    [patchPreferences],
  );

  const setOpenMenu = useCallback((openMenu: ProductionDockMenu) => {
    setState((s) => ({ ...s, openMenu }));
    if (autoCollapseTimer.current) window.clearTimeout(autoCollapseTimer.current);
  }, []);

  const scheduleAutoCollapse = useCallback(() => {
    if (!state.preferences?.dockAutoCollapse) return;
    if (autoCollapseTimer.current) window.clearTimeout(autoCollapseTimer.current);
    autoCollapseTimer.current = window.setTimeout(() => {
      void setCollapsed(true);
      setOpenMenu(null);
    }, 8000);
  }, [setCollapsed, setOpenMenu, state.preferences?.dockAutoCollapse]);

  const selectModel = useCallback(
    async (modality: Modality, modelId: string) => {
      const key = routingKey(modality);
      const current =
        key === "llmRouting"
          ? state.preferences?.llmRouting
          : key === "videoRouting"
            ? state.preferences?.videoRouting
            : key === "imageRouting"
              ? state.preferences?.imageRouting
              : state.preferences?.audioRouting;
      const patch: Partial<UserGlobalPreferences> = {
        [key]: {
          modality,
          preference: current?.preference ?? "manual_only",
          availableModelIds: current?.availableModelIds ?? [modelId],
          activeModelId: modelId,
          fallbackModelId: current?.fallbackModelId ?? null,
          allowFallback: current?.allowFallback ?? false,
        },
      };
      await patchPreferences(patch);
      if (projectId) {
        const projectPatch: Record<string, string> = {};
        if (modality === "llm") projectPatch.activeLlmModelId = modelId;
        if (modality === "video") projectPatch.activeVideoModelId = modelId;
        if (modality === "image") projectPatch.activeImageModelId = modelId;
        if (modality === "audio") projectPatch.activeAudioModelId = modelId;
        if (Object.keys(projectPatch).length) {
          await api.productionControlPutProjectPreferences(projectId, projectPatch);
        }
      }
      const resolved = await api.productionControlResolve({ modality, projectId: projectId ?? undefined });
      setState((s) => ({
        ...s,
        resolved: { ...s.resolved, [modality]: resolved },
      }));
      scheduleAutoCollapse();
    },
    [patchPreferences, projectId, scheduleAutoCollapse, state.preferences],
  );

  const setRuntimeFlags = useCallback(
    async (localEnabled: boolean, apiEnabled: boolean) => {
      const runtimeSource: UserGlobalPreferences["runtimeSource"] =
        localEnabled && apiEnabled ? "hybrid" : localEnabled ? "local" : apiEnabled ? "api" : "local";
      await patchPreferences({
        runtimeLocalEnabled: localEnabled,
        runtimeApiEnabled: apiEnabled,
        runtimeSource,
      });
      await refresh();
    },
    [patchPreferences, refresh],
  );

  const previewProviderSwitch = useCallback(async (toProviderId: string) => {
    const preview = await api.productionControlProviderSwitch({ toProviderId });
    setState((s) => ({
      ...s,
      providerSwitch: preview,
      providerSwitchToken: preview.token ?? null,
      providerModalOpen: false,
    }));
    return preview;
  }, []);

  const confirmProviderSwitch = useCallback(
    async (confirmed: boolean) => {
      if (!state.providerSwitchToken) return;
      await api.productionControlProviderSwitchConfirm({
        token: state.providerSwitchToken,
        confirmed,
      });
      setState((s) => ({ ...s, providerSwitch: null, providerSwitchToken: null }));
      try {
        await api.hostedProvidersDiscover();
      } catch {
        /* discovery best-effort after switch */
      }
      await refresh();
    },
    [refresh, state.providerSwitchToken],
  );

  const retryDiscovery = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      await api.hostedProvidersDiscover();
      await refresh();
    } catch (err) {
      setState((s) => ({
        ...s,
        loading: false,
        error: err instanceof Error ? err.message : String(err),
      }));
    }
  }, [refresh]);

  const activeLabels = useMemo(() => {
    const pick = (modality: Modality) =>
      state.resolved[modality]?.activeLabel ||
      state.status?.modalities?.[modality]?.activeLabel ||
      modality.toUpperCase();
    return {
      llm: pick("llm"),
      video: pick("video"),
      image: pick("image"),
      audio: pick("audio"),
    };
  }, [state.resolved, state.status?.modalities]);

  return {
    projectId,
    ...state,
    activeLabels,
    refresh,
    patchPreferences,
    setCollapsed,
    setOpenMenu,
    selectModel,
    setRuntimeFlags,
    previewProviderSwitch,
    confirmProviderSwitch,
    retryDiscovery,
    setProviderModalOpen: (providerModalOpen: boolean) => setState((s) => ({ ...s, providerModalOpen })),
  };
}

export type ProductionDockApi = ReturnType<typeof useProductionDock>;
