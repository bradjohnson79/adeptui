import { useEffect, useRef } from "react";
import { api } from "../../api";
import type {
  ApiModelsSectionMeta,
  DiscoveredApiModel,
  Modality,
  ModelDescriptor,
  ResolvedSelection,
} from "../../modelRegistry/contracts";
import { buildAiGuidedSetupPath } from "../../setup/navigation";
import { StatusBadge } from "../ui";
import { InstallStatusChip } from "../install/InstallStatusChip";
import type { ProductionDockApi } from "./useProductionDock";

function setupComponentIdForModel(modelId: string): string | null {
  if (modelId === "hunyuan-video-15" || (modelId.includes("hunyuan") && modelId.includes("15"))) {
    return "hunyuan_video_15";
  }
  if (modelId === "hunyuan-video-13b" || (modelId.includes("hunyuan") && modelId.includes("13"))) {
    return "hunyuan_video_13b";
  }
  if (modelId.includes("index-tts") || modelId.includes("indextts")) return "index_tts2";
  if (modelId.includes("wan")) return "wan_models";
  if (modelId.includes("ltx")) return "ltx_checkpoint";
  if (modelId === "qwen-image-2512-local") return "qwen_image_2512_models";
  if (modelId === "flux-local") return "flux1_dev_local";
  if (modelId === "flux-schnell-local") return "flux1_schnell_local";
  if (modelId === "flux-kontext-dev-local") return "flux1_kontext_dev_local";
  if (modelId === "zimage-local") return "zimage_models";
  if (modelId.startsWith("krea2")) return "krea2_models";
  if (modelId === "sana-15-local") return "sana_15_local";
  if (modelId === "sdxl-local") return "sdxl_local";
  if (modelId === "sd35-large-local") return "sd35_large_local";
  if (modelId === "cogview-4-local") return "cogview4_local";
  if (modelId === "hidream-local") return "hidream_local";
  if (modelId === "lumina-image-2-local") return "lumina_image_2_local";
  if (modelId === "pixart-sigma-local") return "pixart_sigma_local";
  if (modelId === "kolors-local") return "kolors_local";
  if (modelId === "omnigen-local") return "omnigen_local";
  if (modelId === "janus-pro-local") return "janus_pro_local";
  if (modelId === "hunyuan-image-local") return "hunyuan_image_local";
  return null;
}

export function readinessKind(
  model: ModelDescriptor | DiscoveredApiModel,
): "Ready" | "Unavailable" | "NeedsAttention" | "Checking" {
  const readiness = (model as DiscoveredApiModel).readiness;
  if (readiness === "Ready" || model.executable) return "Ready";
  if (model.capabilityLabel === "Loading") return "Checking";
  if (
    readiness === "Unsupported" ||
    readiness === "Permission Denied" ||
    readiness === "Temporarily Unavailable" ||
    model.capabilityLabel === "Unavailable" ||
    model.capabilityLabel === "Error"
  ) {
    return "Unavailable";
  }
  return "NeedsAttention";
}

export function provenanceLine(resolved?: ResolvedSelection | null) {
  if (!resolved?.provenance) return "Checking readiness…";
  const p = resolved.provenance;
  const parts = [
    p.activeLabel || "No model selected",
    p.source ? `from ${p.source}` : null,
    p.gpu ? `GPU ${p.gpu}` : null,
    p.executable ? "Ready to run" : p.blockedReason || "Not ready",
  ].filter(Boolean);
  return parts.join(" · ");
}

function providerDisplayName(providerId?: string | null) {
  if (!providerId) return null;
  if (providerId === "kie") return "Kie.ai";
  if (providerId === "wavespeed") return "WaveSpeed.ai";
  if (providerId === "fal") return "fal.ai";
  return providerId;
}

function openSetupWizard(projectId?: string | null, componentId?: string | null) {
  window.location.assign(
    buildAiGuidedSetupPath({
      projectId: projectId || undefined,
      componentId: componentId || undefined,
      source: "production_dock",
    }),
  );
}

function videoStatusHint(model: ModelDescriptor): string | null {
  if (model.id === "minimax-h3") {
    if (model.capabilityLabel === "Testing") return "Default · Private Local · Owner Only · Experimental";
    if (model.capabilityLabel === "Requires Setup" || !model.executable) {
      return "Default · MiniMax unavailable — choose another generator";
    }
    return "Default";
  }
  if (model.id === "hunyuan-video-1.5-local") return "Optional Hunyuan";
  if (model.id === "hunyuan-video-13b-local") return "Advanced Hunyuan";
  if (model.id === "wan-local") return "Optional";
  return null;
}

function LocalModelRow({
  model,
  activeId,
  onSelect,
  onStartRuntime,
  projectId,
}: {
  model: ModelDescriptor;
  activeId: string | null;
  onSelect: () => void;
  onStartRuntime?: () => void;
  projectId?: string | null;
}) {
  const active = activeId === model.id;
  const h3PrivateReady = model.id === "minimax-h3" && model.capabilityLabel === "Testing";
  const comingSoon = model.capabilityLabel === "Unavailable" && model.id !== "minimax-h3";
  const needsSetup =
    model.capabilityLabel === "Requires Setup" ||
    (model.id === "minimax-h3" && !h3PrivateReady);
  const dockerStopped =
    model.executionClass === "docker_local" && !model.executable && model.capabilityLabel !== "Unavailable";
  const hint = videoStatusHint(model);
  const setupComponentId = setupComponentIdForModel(model.id);
  return (
    <li>
      <button
        type="button"
        className={`production-dock-model-item${active ? " is-active" : ""}${comingSoon || dockerStopped ? " is-disabled" : ""}`}
        data-execution-class={model.executionClass || (model.locality === "hosted" ? "hosted_api" : "native_local")}
        data-testid={model.id === "minimax-h3" ? "production-dock-minimax-h3" : undefined}
        aria-label={
          comingSoon
            ? `${model.label} — Unavailable`
            : dockerStopped
              ? `${model.label} — Container Stopped — Start Runtime`
            : needsSetup
              ? `${model.label} — requires Setup / license clearance`
              : h3PrivateReady
                ? `${model.label} — Private Local · Owner Only · Experimental`
                : `Select ${model.label}`
        }
        aria-pressed={active}
        aria-disabled={comingSoon}
        disabled={comingSoon}
        onClick={() => {
          if (comingSoon) return;
          if (dockerStopped) {
            onStartRuntime?.();
            return;
          }
          if (needsSetup) {
            openSetupWizard(projectId, setupComponentId);
            return;
          }
          onSelect();
        }}
      >
        <div className="production-dock-model-item__row">
          <span className="production-dock-model-item__label">
            {active || model.id === "minimax-h3" ? "✓ " : "○ "}
            {model.label}
          </span>
          <StatusBadge kind={readinessKind(model)} label={model.capabilityLabel} compact />
        </div>
        {setupComponentId ? (
          <div className="production-dock-model-item__meta">
            <InstallStatusChip
              componentId={setupComponentId}
              href={buildAiGuidedSetupPath({
                projectId,
                componentId: setupComponentId,
                source: "production_dock",
              })}
            />
          </div>
        ) : null}
        <span className="production-dock-model-item__meta">
          {model.executionClass === "docker_local" ? "Docker Local" : "Native Local"}
          {hint ? ` · ${hint}` : ""}
          {model.estimatedVramGb != null ? ` · ~${model.estimatedVramGb} GB VRAM` : ""}
          {dockerStopped ? " · Start Runtime" : ""}
          {needsSetup ? " · Open Setup to install" : ""}
        </span>
      </button>
      {dockerStopped ? (
        <div className="production-dock-api-empty__actions">
          <button
            type="button"
            className="production-dock-secondary-btn"
            data-testid={`start-runtime-${model.runtimeId || model.id}`}
            onClick={() => onStartRuntime?.()}
          >
            Start Runtime
          </button>
          <a className="production-dock-secondary-btn" href="/runtime-manager">
            Runtime Manager
          </a>
        </div>
      ) : null}
    </li>
  );
}

function ApiModelRow({
  model,
  activeId,
  onSelect,
}: {
  model: DiscoveredApiModel;
  activeId: string | null;
  onSelect: () => void;
}) {
  const active = activeId === model.id;
  const selectable = model.selectable !== false && Boolean(model.executable);
  const readiness = model.readiness || model.capabilityLabel;
  const provider = providerDisplayName(model.providerId);

  return (
    <li>
      <button
        type="button"
        className={`production-dock-model-item${active ? " is-active" : ""}${selectable ? "" : " is-disabled"}`}
        aria-label={selectable ? `Select ${model.label}` : `${model.label} — ${readiness}`}
        aria-pressed={active}
        aria-disabled={!selectable}
        disabled={!selectable}
        onClick={() => {
          if (!selectable) return;
          onSelect();
        }}
      >
        <div className="production-dock-model-item__row">
          <span className="production-dock-model-item__label">
            {active ? "✓ " : "○ "}
            {model.label.replace(/\s*—\s*.+$/, "") || model.label}
          </span>
          <StatusBadge kind={readinessKind(model)} label={String(readiness)} compact />
        </div>
        <span className="production-dock-model-item__meta">
          {provider || "API"}
          {!selectable && readiness ? ` · ${readiness}` : ""}
        </span>
      </button>
    </li>
  );
}

function ApiEmptyState({
  meta,
  modality,
  onRetry,
  projectId,
}: {
  meta?: ApiModelsSectionMeta;
  modality: Modality;
  onRetry: () => void;
  projectId?: string | null;
}) {
  const message =
    meta?.emptyMessage ||
    "No API models available.\n\nCheck your API key or add a provider\nthrough the Setup Wizard.";
  return (
    <div className="production-dock-api-empty" data-testid={`production-dock-api-empty-${modality}`}>
      {message.split("\n").map((line, i) =>
        line ? (
          <p key={i} className={i === 0 ? "production-dock-api-empty__title" : "production-dock-muted"}>
            {line}
          </p>
        ) : (
          <br key={i} />
        ),
      )}
      <div className="production-dock-api-empty__actions">
        <button
          type="button"
          className="production-dock-secondary-btn"
          onClick={() => openSetupWizard(projectId, "fal_key")}
        >
          Open Setup Wizard
        </button>
        <button type="button" className="production-dock-secondary-btn" onClick={onRetry}>
          Retry Discovery
        </button>
      </div>
    </div>
  );
}

export function ModelMenuDrawer({
  open,
  title,
  modality,
  dock,
  onClose,
}: {
  open: boolean;
  title: string;
  modality: Modality;
  dock: ProductionDockApi;
  onClose: () => void;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const sections = dock.sections[modality];
  const localModels = sections?.local ?? (dock.models[modality] ?? []).filter((m) => m.locality === "local");
  const nativeModels = localModels.filter((m) => (m.executionClass || "native_local") === "native_local");
  const dockerModels = localModels.filter((m) => m.executionClass === "docker_local");
  const apiModels = sections?.api ?? [];
  const apiMeta = sections?.apiMeta ?? dock.apiMeta[modality];
  const resolved = dock.resolved[modality] ?? dock.status?.modalities?.[modality] ?? null;
  const activeId = resolved?.activeModelId ?? null;
  const activeProvider = providerDisplayName(apiMeta?.activeProviderId);

  async function startDockerRuntime(model: ModelDescriptor) {
    const rid = model.runtimeId || model.id.replace(/^docker-runtime:/, "");
    try {
      await api.dockerRuntime.start(rid);
      await dock.retryDiscovery();
    } catch {
      window.location.assign("/runtime-manager");
    }
  }

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        onClose();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    panelRef.current?.focus();
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  const loading = dock.loading && localModels.length === 0 && apiModels.length === 0;

  return (
    <div
      ref={panelRef}
      className="production-dock-drawer"
      role="dialog"
      aria-modal="true"
      aria-label={title}
      tabIndex={-1}
      data-testid={`production-dock-menu-${modality}`}
    >
      <div className="production-dock-drawer__header">
        <h3>{title}</h3>
        <button type="button" className="production-dock-collapse-btn" aria-label={`Close ${title}`} onClick={onClose}>
          ×
        </button>
      </div>
      <p className="production-dock-drawer__provenance">{provenanceLine(resolved)}</p>
      {activeProvider ? (
        <p className="production-dock-muted production-dock-drawer__provider">Active provider: {activeProvider}</p>
      ) : null}

      {loading ? (
        <p className="production-dock-muted">Loading models…</p>
      ) : (
        <>
          <section className="production-dock-model-section" aria-label="Native Local Models" data-testid={`dock-native-${modality}`}>
            <h4 className="production-dock-model-section__title">Native Local</h4>
            {nativeModels.length === 0 ? (
              <p className="production-dock-muted">No native local models listed for this category yet.</p>
            ) : (
              <ul className="production-dock-model-list">
                {nativeModels.map((model) => (
                  <LocalModelRow
                    key={model.id}
                    model={model}
                    activeId={activeId}
                    projectId={dock.projectId}
                    onSelect={() => {
                      void dock.selectModel(modality, model.id).then(onClose);
                    }}
                  />
                ))}
              </ul>
            )}
          </section>

          <section className="production-dock-model-section" aria-label="Docker Local Models" data-testid={`dock-docker-${modality}`}>
            <h4 className="production-dock-model-section__title">Docker Local</h4>
            {dockerModels.length === 0 ? (
              <p className="production-dock-muted">
                No Docker runtimes registered.{" "}
                <a href="/runtime-manager">Open Runtime Manager</a>
              </p>
            ) : (
              <ul className="production-dock-model-list">
                {dockerModels.map((model) => (
                  <LocalModelRow
                    key={model.id}
                    model={model}
                    activeId={activeId}
                    projectId={dock.projectId}
                    onStartRuntime={() => {
                      void startDockerRuntime(model);
                    }}
                    onSelect={() => {
                      // No silent substitute — selection only when executable
                      if (!model.executable) {
                        void startDockerRuntime(model);
                        return;
                      }
                      void dock.selectModel(modality, model.id).then(onClose);
                    }}
                  />
                ))}
              </ul>
            )}
          </section>

          <section className="production-dock-model-section" aria-label="Hosted API Models" data-testid={`dock-hosted-${modality}`}>
            <h4 className="production-dock-model-section__title">Hosted API</h4>
            {apiModels.length === 0 ? (
              <ApiEmptyState
                meta={apiMeta}
                modality={modality}
                projectId={dock.projectId}
                onRetry={() => {
                  void dock.retryDiscovery().then(() => undefined);
                }}
              />
            ) : (
              <ul className="production-dock-model-list">
                {apiModels.map((model) => (
                  <ApiModelRow
                    key={model.id}
                    model={model}
                    activeId={activeId}
                    onSelect={() => {
                      void dock.selectModel(modality, model.id).then(onClose);
                    }}
                  />
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  );
}
