/** W47 Docker Runtime Extensions — FE contract parity (schema_version 1). */

export const DOCKER_RUNTIME_SCHEMA_VERSION = 1;

export type RuntimeClassification = "core_mandatory" | "official_optional" | "user_added";
export type ExecutionClass = "native_local" | "docker_local" | "hosted_api";
export type RuntimeReadiness =
  | "unverified"
  | "requires_repair"
  | "tested_locally"
  | "ready"
  | "unavailable";
export type RuntimeLifecycleState =
  | "absent"
  | "created"
  | "starting"
  | "running"
  | "stopping"
  | "stopped"
  | "error";
export type UninstallOption =
  | "ui_only"
  | "container"
  | "container_and_image"
  | "container_image_and_private";

export interface DockerRuntimeDescriptor {
  id: string;
  name: string;
  version?: string;
  classification: RuntimeClassification;
  ownership?: string;
  modality?: string;
  readiness: RuntimeReadiness;
  lifecycle: RuntimeLifecycleState;
  executionClass: ExecutionClass;
  image?: string;
  imageDigest?: string | null;
  containerId?: string | null;
  hostPort?: number | null;
  healthOk?: boolean;
  gpuReady?: boolean;
  minimumVramGb?: number;
  lastError?: string | null;
  uninstallAllowed?: boolean;
  models?: string[];
  nodes?: string[];
  workflows?: string[];
  disabled?: boolean;
}

export interface PlatformStatus {
  readyForInstall?: boolean;
  dockerDesktop?: boolean;
  daemon?: boolean;
  wsl2?: boolean;
  nvidiaToolkit?: boolean;
  simulate?: boolean;
  error?: string | null;
  [key: string]: unknown;
}

export interface RuntimeSecurityScanReport {
  ok: boolean;
  blocked: string[];
  warnings: string[];
}

export interface RuntimeInstallationPlan {
  runtimeId: string;
  steps: string[];
  security: RuntimeSecurityScanReport;
  validation: { ok: boolean; errors: string[]; warnings: string[] };
  estimatedDiskGb?: number;
}

export interface RuntimeUninstallPlan {
  runtimeId: string;
  option: UninstallOption;
  allowed: boolean;
  blockedReason?: string | null;
  preserveShared?: string[];
  steps?: string[];
  usage?: RuntimeUsageReport;
}

export interface RuntimeUsageReport {
  runtimeId: string;
  activeJobs?: number;
  dockBindings?: string[];
  sharedArtifacts?: string[];
  projectAssetsPreserved?: boolean;
}

export type AddCustomCapabilitySource =
  | "import_image"
  | "compose"
  | "adept_package"
  | "comfy_workflow"
  | "register_existing";
