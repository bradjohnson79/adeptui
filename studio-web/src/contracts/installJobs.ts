import type { DownloadOperation } from "../setup/types";

export type InstallState =
  | "not_installed"
  | "source_required"
  | "awaiting_confirmation"
  | "queued"
  | "preparing"
  | "downloading"
  | "verifying_download"
  | "installing"
  | "configuring"
  | "verifying_install"
  | "ready"
  | "paused"
  | "cancelled"
  | "repair_required"
  | "failed"
  | string;

export type StallStatus = "none" | "possible_stall" | "interrupted" | "waiting_for_source";

export interface InstallJobError {
  code?: string | null;
  kind?: string | null;
  title?: string | null;
  message: string;
  userMessage?: string | null;
  technicalMessage?: string | null;
  details?: string[] | null;
  affectedFiles?: string[] | null;
  affectedDependencies?: string[] | null;
  retryable?: boolean | null;
  repairable?: boolean | null;
  recommendedAction?: string | null;
  suggestedAction?: string | null;
  logReference?: string | null;
  helpUrl?: string | null;
}

export interface InstallPhaseStep {
  id: string;
  label: string;
  status: "complete" | "active" | "pending" | "failed" | string;
}

export interface InstallHeartbeat {
  jobId: string;
  lastProgressAt: string;
  lastBytesDownloaded?: number | null;
  lastPhaseChangeAt: string;
  workerAlive: boolean;
  networkActive?: boolean | null;
}

export interface InstallJobProgress {
  phase?: string | null;
  phaseLabel?: string | null;
  percent?: number | null;
  indeterminate?: boolean | null;
  bytesDownloaded?: number | null;
  bytesTotal?: number | null;
  speedBytesPerSecond?: number | null;
  etaSeconds?: number | null;
  currentFile?: string | null;
  currentStep?: string | null;
  stepIndex?: number | null;
  stepCount?: number | null;
  phaseSteps?: InstallPhaseStep[] | null;
  stallStatus?: StallStatus | null;
  stallLabel?: string | null;
  details?: Record<string, unknown> | null;
}

export interface InstallRecoveryAction {
  action: string;
  label: string;
  description?: string;
  enabled?: boolean;
  destructive?: boolean;
}

export interface InstallJobCapabilities {
  canPause?: boolean;
  canResume?: boolean;
  canCancel?: boolean;
  canRetry?: boolean;
  canRepair?: boolean;
  canVerify?: boolean;
  canOpenDetails?: boolean;
  message?: string | null;
}

export interface InstallJob {
  id: string;
  componentId: string;
  componentName?: string | null;
  state: InstallState;
  phase?: string | null;
  message?: string | null;
  providerId?: string | null;
  sourceId?: string | null;
  projectId?: string | null;
  destinationRoot?: string | null;
  destination?: string | null;
  installId?: string | null;
  installKind?: string | null;
  kind?: string | null;
  progress?: InstallJobProgress | null;
  error?: InstallJobError | null;
  capabilities?: InstallJobCapabilities | null;
  recoveryActions?: InstallRecoveryAction[] | null;
  heartbeat?: InstallHeartbeat | null;
  stallStatus?: StallStatus | null;
  stallLabel?: string | null;
  phaseSteps?: InstallPhaseStep[] | null;
  metadata?: Record<string, unknown> | null;
  raw?: Record<string, unknown> | null;
  source?: Record<string, unknown> | null;
  createdAt?: string | null;
  updatedAt?: string | null;
  startedAt?: string | null;
  completedAt?: string | null;
  lastVerifiedAt?: string | null;
}

export function installJobPercent(job: InstallJob): number | null {
  if (job.state === "ready" || job.state === "completed") return 100;
  const raw = job.progress?.percent;
  if (raw == null || !Number.isFinite(raw)) return null;
  const normalized = raw <= 1 ? raw * 100 : raw;
  // Never show 100% until final health check passes.
  return Math.max(0, Math.min(99, normalized));
}

export function isInstallJobTerminal(job: InstallJob): boolean {
  return ["ready", "completed", "cancelled"].includes(job.state);
}

/** Jobs that should remain visible on Setup / Source Manager cards. */
export function isInstallJobActive(job: InstallJob): boolean {
  if (
    ["failed", "repair_required", "paused", "source_required", "awaiting_confirmation", "configuring"].includes(
      job.state,
    )
  ) {
    return true;
  }
  if (job.stallStatus && job.stallStatus !== "none") return true;
  return !isInstallJobTerminal(job);
}

export function installJobStateLabel(job: InstallJob): string {
  if (job.stallLabel) return job.stallLabel;
  if (job.progress?.stallLabel) return job.progress.stallLabel;
  const phase = job.progress?.phaseLabel || job.progress?.phase || job.phase;
  if (phase && phase !== job.state) return String(phase).replace(/_/g, " ");
  switch (job.state) {
    case "queued":
      return "Queued";
    case "preparing":
      return "Preparing";
    case "source_required":
      return "Source required";
    case "awaiting_confirmation":
      return "Awaiting confirmation";
    case "downloading":
      return "Downloading";
    case "verifying_download":
      return "Verifying files";
    case "installing":
      return "Installing";
    case "configuring":
      return "Configuring";
    case "verifying_install":
      return "Final health check";
    case "paused":
      return "Paused";
    case "failed":
      return "Install failed";
    case "repair_required":
      return "Repair required";
    case "ready":
      return "Ready";
    case "cancelled":
      return "Cancelled";
    default:
      return String(job.state).replace(/_/g, " ");
  }
}

export function installJobBadge(job: InstallJob | null | undefined): string {
  if (!job) return "Not installed";
  if (job.stallStatus === "possible_stall") return "Possible Stall";
  if (job.stallStatus === "interrupted") return "Interrupted";
  if (job.stallStatus === "waiting_for_source") return "Waiting for Source";
  if (job.state === "ready") return "Ready";
  if (job.state === "repair_required") return "Repair Required";
  if (job.state === "failed") return "Failed";
  if (job.state === "downloading") return "Downloading";
  if (job.state === "source_required") return "Blocked";
  return installJobStateLabel(job);
}

export function installJobFromDownloadOperation(operation: DownloadOperation): InstallJob {
  const failed = operation.phase === "failed" || operation.phase === "interrupted";
  const paused = operation.phase === "paused";
  const ready = operation.phase === "installed";

  return {
    id: operation.id,
    componentId: operation.componentId,
    componentName: operation.componentId,
    state: ready
      ? "ready"
      : failed
        ? "failed"
        : paused
          ? "paused"
          : (operation.phase || "queued"),
    phase: operation.phase,
    providerId: operation.providerId ?? null,
    sourceId: operation.sourceId ?? null,
    destinationRoot: operation.paths?.finalDestination ?? operation.paths?.stagingDirectory ?? null,
    installId: operation.installId ?? null,
    progress: {
      phase: operation.phase,
      phaseLabel: operation.phase ? operation.phase.replace(/_/g, " ") : null,
      percent: operation.progress?.percent ?? null,
      indeterminate: operation.progress?.percent == null,
      bytesDownloaded: operation.progress?.bytesDownloaded ?? null,
      bytesTotal: operation.progress?.bytesTotal ?? null,
      speedBytesPerSecond: operation.progress?.speedBytesPerSecond ?? null,
      etaSeconds: operation.progress?.etaSeconds ?? null,
      currentFile: operation.progress?.currentArtifact ?? null,
    },
    error: operation.failure?.message
      ? {
          kind: operation.failure.category ?? null,
          code: operation.failure.category ?? null,
          message: operation.failure.message,
          userMessage: operation.failure.message,
          recommendedAction: operation.failure.recommendedAction ?? null,
          retryable: true,
          repairable: operation.failure.recommendedAction === "repair",
        }
      : null,
    capabilities: {
      canPause: operation.capabilities?.canPause,
      canResume: operation.capabilities?.canResume,
      canCancel: operation.capabilities?.canCancel,
      canRetry: failed,
      canRepair: operation.failure?.recommendedAction === "repair",
      message: operation.capabilities?.message ?? null,
    },
    metadata: { origin: "download" },
    createdAt: operation.createdAt ?? null,
    updatedAt: operation.updatedAt ?? null,
  };
}
