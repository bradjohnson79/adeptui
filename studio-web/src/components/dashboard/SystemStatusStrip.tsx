import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api";
import { CapabilityStatusBadge, capabilityById, useCapabilities } from "../CapabilityPanel";
import { StatusBadge } from "../ui";
import {
  apiHealthLabel,
  gpuHealthLabel,
  mapApiOk,
  mapComfyHealth,
  mapGpuOk,
  mapProviderStatus,
  providerStatusLabel,
} from "../../status";
import { useStudioHealth } from "../../hooks/useStudioHealth";
import { BetaRuntimeStatus } from "../BetaRuntimeStatus";
import { buildAiGuidedSetupPath } from "../../setup/navigation";
import { shouldSuspendDependentPolling } from "../../runtime/studioApiConnection";

type GpuSummary = {
  ok: boolean;
  title: string;
};

export function SystemStatusStrip({
  compact = false,
  queuedJobs,
  projectId,
  stacked = false,
  onOpenCoDirector,
  onReloadHealth,
}: {
  compact?: boolean;
  queuedJobs?: number | null;
  projectId?: string;
  stacked?: boolean;
  onOpenCoDirector?: () => void;
  onReloadHealth?: () => void;
}) {
  const navigate = useNavigate();
  const [gpu, setGpu] = useState<GpuSummary | null>(null);
  const [queued, setQueued] = useState<number | null>(queuedJobs ?? null);
  const { health, error: healthError, reload } = useStudioHealth();
  const { snapshot } = useCapabilities({ projectId, pollMs: 30000 });

  useEffect(() => {
    if (queuedJobs != null) setQueued(queuedJobs);
  }, [queuedJobs]);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      if (!alive) return;
      if (shouldSuspendDependentPolling()) return;
      try {
        const g = await api.gpuStats();
        if (!alive) return;
        const first = g.gpus?.[0];
        const ok = Boolean(g.ok && g.gpus?.length);
        const title = first
          ? `${first.name || "GPU"}${
              first.memory_total_mib != null
                ? ` · ${first.memory_used_mib ?? "?"}/${first.memory_total_mib} MiB`
                : ""
            }`
          : ok
            ? "GPU detected"
            : "No GPU reported by nvidia-smi";
        setGpu({ ok, title });
      } catch {
        if (alive) setGpu(null);
      }
      if (projectId && queuedJobs == null) {
        try {
          const jobs = await api.listJobs(projectId);
          if (alive) {
            setQueued(jobs.filter((j) => ["queued", "running", "pending"].includes(j.status)).length);
          }
        } catch {
          /* leave queued as-is */
        }
      }
    };
    void tick();
    const id = setInterval(() => void tick(), 15000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [projectId, queuedJobs]);

  const comfyModels = health?.comfy?.models;
  // REQUIRED-missing count drives runtime health (a missing optional/generator-specific
  // component must NOT flip a reachable runtime to degraded). Optional-missing is surfaced
  // separately as a "Models" badge so runtime health and model readiness are visibly distinct.
  const missingRequiredFromComfy = Array.isArray(comfyModels)
    ? comfyModels.filter((m) => m.required && !m.present)
    : [];
  const missingOptionalFromComfy = Array.isArray(comfyModels)
    ? comfyModels.filter((m) => !m.required && !m.present)
    : [];
  const missingRequiredCount = missingRequiredFromComfy.length
    || health?.comfy?.missingRequiredModelComponentIds?.length
    || 0;
  const missingOptionalCount = missingOptionalFromComfy.length
    || Math.max(
      0,
      (health?.comfy?.missingModelComponentIds?.length ?? health?.missing_model_component_ids?.length ?? health?.missing_models?.length ?? 0) - missingRequiredCount,
    );
  const comfyProbed = health?.comfy_probed !== false && Boolean(health);
  const comfyReachable = Boolean(health?.comfy_reachable);
  const comfyNodeCatalogOk = Boolean(health?.node_catalog_available);
  const op = health?.operator;
  const provider = op?.provider;
  const providerCap = capabilityById(snapshot, "codirector.provider");
  const providerReady = providerCap
    ? providerCap.status === "locally_verified" || providerCap.status === "production_ready"
    : null;

  const goSetupOrSourceManager = () => {
    navigate(
      buildAiGuidedSetupPath({
        projectId,
        source: "status_center",
      }),
    );
  };

  const goProvider = () => {
    if (onOpenCoDirector) onOpenCoDirector();
    else navigate("/co-director");
  };

  const goJobs = () => {
    if (projectId) navigate(`/project/${projectId}?workspace=home`);
    else navigate("/");
  };

  const refreshApi = () => {
    if (onReloadHealth) onReloadHealth();
    else void reload();
  };

  const apiOk = Boolean(health) && !healthError;
  const apiDegraded = Boolean(health) && (op?.api === "degraded" || (Array.isArray(op?.partialErrors) && op.partialErrors.length > 0));

  return (
    <div
      className={[
        "system-status-strip",
        compact ? "compact" : "",
        stacked ? "system-status-strip--stacked" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      role="status"
      aria-live="polite"
      data-testid="system-status-strip"
    >
      <StatusBadge
        kind={!health && !healthError ? "Checking" : apiOk ? (apiDegraded ? "NeedsAttention" : mapApiOk(true)) : mapApiOk(false)}
        label={
          !health && !healthError
            ? "Studio API Checking…"
            : apiHealthLabel(apiOk, apiDegraded)
        }
        data-testid="status-api"
        title={
          healthError instanceof Error
            ? healthError.message
            : Array.isArray(op?.partialErrors) && op.partialErrors.length
              ? `Partial probe issues: ${op.partialErrors.join(", ")}`
              : "Studio API health endpoint"
        }
        onClick={refreshApi}
      />
      <StatusBadge
        kind={
          !health || !comfyProbed
            ? "Checking"
            : !comfyReachable
              ? "Offline"
              : healthError
                ? "NeedsAttention"
                : mapComfyHealth(comfyReachable, Boolean(missingRequiredCount))
        }
        label={
          !health || !comfyProbed
            ? "ComfyUI Checking…"
            : !comfyReachable
              ? "ComfyUI Offline"
              : healthError
                ? "ComfyUI Error"
                : !comfyNodeCatalogOk
                  ? "ComfyUI Ready · Loading Nodes"
                  : missingRequiredCount
                    ? `ComfyUI · ${missingRequiredCount} required missing`
                    : "ComfyUI Ready"
        }
        data-testid="status-comfy"
        title={
          !health || !comfyProbed
            ? "ComfyUI health probe in progress"
            : !comfyReachable
              ? health?.message || "ComfyUI is unreachable. Start ComfyUI, then refresh."
              : healthError
                ? String(healthError)
                : !comfyNodeCatalogOk
                  ? "Runtime is up. Node list is still loading."
                  : missingRequiredCount
                    ? `${missingRequiredCount} required model component(s) missing. Runtime cannot generate until installed.`
                    : health?.comfy_version
                      ? `ComfyUI ${health.comfy_version} · node catalogue OK`
                      : "ComfyUI reachable, node catalogue OK"
        }
        onClick={goSetupOrSourceManager}
      />
      <StatusBadge
        kind={
          !health
            ? "Checking"
            : !comfyReachable
              ? "Checking"
              : missingRequiredCount > 0
                ? "NeedsAttention"
                : "Ready"
        }
        label={
          !health
            ? "Models…"
            : missingRequiredCount > 0
              ? `Models · ${missingRequiredCount} required missing`
              : "Models Ready"
        }
        data-testid="status-models"
        title={
          !health
            ? "Model readiness probe in progress"
            : missingRequiredCount > 0
              ? `${missingRequiredCount} required model component(s) missing.`
              : missingOptionalCount > 0
                ? `Required models present. ${missingOptionalCount} optional component(s) not installed — not a production blocker.`
                : "All configured required model components are present."
        }
        onClick={goSetupOrSourceManager}
      />
      <StatusBadge
        kind={!health ? "Checking" : mapProviderStatus(provider, providerReady)}
        label={!health ? "Providers…" : providerStatusLabel(provider, providerReady)}
        data-testid="status-provider"
        title={
          providerCap?.message
          || provider?.selectedModel
          || provider?.status
          || "Co-Director local provider health"
        }
        onClick={goProvider}
      />
      <StatusBadge
        kind={gpu === null ? "Checking" : mapGpuOk(gpu.ok)}
        label={gpu === null ? "GPU…" : gpuHealthLabel(gpu.ok)}
        data-testid="status-gpu"
        title={gpu?.title || "GPU probe via nvidia-smi"}
      />
      <CapabilityStatusBadge projectId={projectId} onClick={goSetupOrSourceManager} />
      {queued != null && (
        <StatusBadge
          kind={queued ? "NeedsAttention" : "Ready"}
          label={`${queued} Job${queued === 1 ? "" : "s"} Queued`}
          data-testid="status-jobs"
          onClick={goJobs}
        />
      )}
      <BetaRuntimeStatus compact={compact} />
    </div>
  );
}
