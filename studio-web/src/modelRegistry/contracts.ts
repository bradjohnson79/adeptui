/** Production Dock — frontend types mirroring shared contracts (frozen M42). */

export type PreferenceScope = "system" | "user" | "project";

export type ProductionRuntimeSource = "local" | "api" | "hybrid";

export type CpuFallbackPolicy = "disabled" | "ask" | "lightweight_only";

export type CapabilityLabel =
  | "Certified"
  | "Testing"
  | "Available"
  | "Unavailable"
  | "Unsupported"
  | "Requires Setup"
  | "Loading"
  | "Error";

export type LocalLifecycle =
  | "Installed"
  | "Loading"
  | "Loaded"
  | "Unloading"
  | "VRAM insufficient"
  | "Worker offline"
  | "Dependency error"
  | "CPU-only framework detected";

export type Modality = "llm" | "video" | "image" | "audio";

export type ModelRoutingPreferenceKind =
  | "local_preferred"
  | "hosted_preferred"
  | "ask_before_switching"
  | "manual_only";

export type ThemePreference = "aurora-night" | "aurora-day" | "system";

export type HostedProviderId = "kie" | "wavespeed" | "fal" | "automatic";

export type ExecutionClass = "native_local" | "docker_local" | "hosted_api";

export interface ModelDescriptor {
  id: string;
  modality: Modality;
  label: string;
  locality: "local" | "hosted";
  /** W47: Native Local / Docker Local / Hosted API honesty */
  executionClass?: ExecutionClass;
  runtimeId?: string;
  providerId?: string;
  capabilityLabel: CapabilityLabel;
  lifecycle?: LocalLifecycle;
  supports: string[];
  doesNotSupport: string[];
  estimatedVramGb?: number;
  gpuCompatible: boolean;
  executable: boolean;
  selectable?: boolean;
  readiness?: string;
  providerModelId?: string;
}

export interface DiscoveredApiModel extends ModelDescriptor {
  readiness?: string;
  selectable?: boolean;
  accountAccessible?: boolean;
  adapterAvailable?: boolean;
}

export interface ApiModelsSectionMeta {
  activeProviderId?: string | null;
  emptyReason?: string | null;
  emptyMessage?: string | null;
  summary?: Record<string, unknown>;
  updatedAt?: string | null;
}

export interface ModalityModelSections {
  local: ModelDescriptor[];
  api: DiscoveredApiModel[];
  apiMeta?: ApiModelsSectionMeta;
}

export interface ModelRoutingPreference {
  modality: Modality;
  preference: ModelRoutingPreferenceKind;
  availableModelIds: string[];
  activeModelId?: string | null;
  fallbackModelId?: string | null;
  allowFallback: boolean;
}

export interface PreferenceProvenance {
  activeModelId?: string | null;
  activeLabel: string;
  source: PreferenceScope;
  fallbackPolicy: string;
  gpu: "Ready" | "Unavailable" | "Unknown";
  executable: boolean;
  blockedReason?: string | null;
  runtime?: string | null;
  providerId?: string | null;
  cpuFallbackPolicy: CpuFallbackPolicy;
}

export interface ResolvedSelection {
  modality: Modality;
  activeModelId?: string | null;
  activeLabel: string;
  availableModelIds: string[];
  fallbackModelId?: string | null;
  allowFallback: boolean;
  provenance: PreferenceProvenance;
}

export interface ActiveModelSelection {
  modality: Modality;
  activeModelId?: string | null;
  availableModelIds: string[];
  fallbackModelId?: string | null;
  allowFallback: boolean;
  provenance: Pick<PreferenceProvenance, "source" | "executable" | "gpu"> &
    Partial<PreferenceProvenance>;
}

export interface UserGlobalPreferences {
  theme: ThemePreference;
  dockCollapsed: boolean;
  dockAutoCollapse: boolean;
  runtimeSource: ProductionRuntimeSource;
  runtimeLocalEnabled: boolean;
  runtimeApiEnabled: boolean;
  defaultHostedProviderId: HostedProviderId;
  cpuFallbackPolicy: CpuFallbackPolicy;
  llmRouting?: ModelRoutingPreference;
  videoRouting?: ModelRoutingPreference;
  imageRouting?: ModelRoutingPreference;
  audioRouting?: ModelRoutingPreference;
}

export interface ProjectPreferences {
  projectId: string;
  activeVideoModelId?: string | null;
  activeImageModelId?: string | null;
  activeAudioModelId?: string | null;
  activeLlmModelId?: string | null;
  resolution?: string | null;
  quality?: string | null;
  generatorLocks?: Record<string, unknown>;
}

export interface ProductionControlStatus {
  ok: boolean;
  runtimeSource: ProductionRuntimeSource;
  localAvailable: boolean;
  apiAvailable: boolean;
  hostedProviderConnected: boolean;
  activeHostedProviderId?: string | null;
  modalities: Partial<Record<Modality, ResolvedSelection>>;
  queueSummary?: {
    gpuQueued: number;
    hostedQueued: number;
    active: number;
  };
  healthRows?: ProductionHealthRow[];
}

export interface ProductionHealthRow {
  id: string;
  label: string;
  status: CapabilityLabel | string;
  detail?: string | null;
}

export interface ProductionControlGate {
  productionDockGo: boolean;
  requiredFlags: Record<string, boolean>;
  message?: string | null;
}

export interface ProductionQueueJob {
  id: string;
  label: string;
  status: string;
  kind?: string | null;
  projectId?: string | null;
  modality?: Modality | string | null;
  createdAt?: string | null;
  retryable?: boolean;
  cancellable?: boolean;
  workspaceRoute?: string | null;
}

export interface ProductionQueueSnapshot {
  jobs: ProductionQueueJob[];
  gpuQueued: number;
  hostedQueued: number;
  active: number;
}

export interface ProviderSwitchPreview {
  fromProviderId?: string | null;
  toProviderId: string;
  impactSummary: string;
  affectedModalities: Modality[];
  requiresConfirmation: boolean;
}

export interface ProviderSwitchConfirmBody {
  token: string;
  confirmed: boolean;
}

export type ProductionDockMenu =
  | "llm"
  | "video"
  | "image"
  | "audio"
  | "models"
  | "settings"
  | "diagnostics"
  | "queue"
  | null;
