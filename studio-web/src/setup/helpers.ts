import type {
  DiagnosticRecommendation,
  SetupComponentState,
  SetupComponentStatus,
  SetupOperationPhase,
  SetupOverallStatus,
  SetupPrimaryActionKind,
  SetupSummaryCounts,
} from "./types";

export const STATE_LABELS: Record<SetupComponentState, string> = {
  unknown: "Unknown",
  checking: "Checking…",
  ready: "Ready",
  not_installed: "Not Installed",
  update_available: "Update Available",
  installing: "Installing…",
  error: "Needs Attention",
  download_unavailable: "Download Unavailable",
  source_pending: "Source Pending",
};

export const PHASE_LABELS: Record<SetupOperationPhase, string> = {
  installing: "Installing…",
  updating: "Updating…",
  repairing: "Repairing…",
  configuring: "Configuring…",
  verifying: "Checking Installation…",
  validating: "Validating…",
  downloading: "Downloading…",
  verifying_download: "Verifying download…",
  extracting: "Extracting…",
  verifying_install: "Verifying install…",
  completed: "Complete",
  failed: "Failed",
};

export const OVERALL_LABELS: Record<SetupOverallStatus, string> = {
  ready: "Ready to Generate",
  preparing: "Preparing Studio",
  additional_setup_required: "Additional Setup Required",
  needs_attention: "Needs Attention",
};

export function componentStateLabel(component: SetupComponentStatus): string {
  if (component.component_kind === "credential" || component.installer === "credentials") {
    if (component.status === "ready") return "Verified";
    if (component.issue_code === "credential_invalid") return "Key Rejected";
    if (component.issue_code === "credential_unverified") return "Not Verified";
    if (component.status === "not_installed" || component.issue_code === "credential_missing") {
      return "Not Configured";
    }
  }
  if (component.status === "source_pending") {
    if (component.distribution_status === "planned") return "Coming Soon";
    return component.distribution_label || "Source Pending";
  }
  if (component.issue_code === "source_not_published") {
    return component.distribution_label || "Source Pending";
  }
  if (component.issue_code === "source_not_configured") {
    return "Source Not Configured";
  }
  if (component.issue_code === "download_http_error" || component.issue_code?.startsWith("download_")) {
    if (component.status === "error") {
      if (component.issue_code === "download_checksum_failed" || component.issue_code === "required_files_missing") {
        return "Verification Failed";
      }
      if (
        component.issue_code !== "download_source_missing"
        && component.issue_code !== "source_not_configured"
        && component.issue_code !== "source_not_published"
      ) {
        return "Download Failed";
      }
    }
  }
  return component.operation_phase
    ? (PHASE_LABELS[component.operation_phase] ?? STATE_LABELS[component.status])
    : STATE_LABELS[component.status];
}

export function summarizeComponents(components: SetupComponentStatus[]): SetupSummaryCounts {
  return components.reduce<SetupSummaryCounts>(
    (summary, component) => {
      if (component.status === "ready" || component.status === "update_available") {
        summary.ready += 1;
      } else if (
        component.status === "not_installed"
        || component.status === "unknown"
        || component.status === "download_unavailable"
        || component.status === "source_pending"
      ) {
        summary.not_installed += 1;
      } else if (component.status === "error") {
        summary.needs_attention += 1;
      }
      return summary;
    },
    { ready: 0, not_installed: 0, needs_attention: 0 },
  );
}

export function overallStatus(components: SetupComponentStatus[]): SetupOverallStatus {
  const required = components.filter((component) => component.required);
  if (required.some((component) => component.status === "installing" || component.status === "checking")) {
    return "preparing";
  }
  if (required.some((component) => component.status === "error")) {
    return "needs_attention";
  }
  if (required.some((component) => component.status === "not_installed" || component.status === "unknown")) {
    return "additional_setup_required";
  }
  return "ready";
}

export function primaryActionKind(component: SetupComponentStatus): SetupPrimaryActionKind | null {
  return component.primary_action?.kind ?? component.primary_action?.action ?? null;
}

export const RECOMMENDATION_LABELS: Record<DiagnosticRecommendation, string> = {
  none: "No Action Required",
  install: "Download and Install",
  repair: "Repair Installation",
  reinstall: "Reinstall",
  update: "Update Now",
  correct_path: "Locate Existing Files",
  grant_permission: "Grant Permission",
  configure: "Configure API Key",
  manual_help: "View Details",
  link_existing: "Link Existing Folder",
  choose_install_location: "Choose Install Location",
  refresh_source: "Check Again",
  add_source_url: "Add Source URL",
};

/** Exponential backoff for setup polling after consecutive network failures. */
export function nextPollDelayMs(
  consecutiveFailures: number,
  baseMs = 1200,
  maxMs = 30000,
): number {
  if (consecutiveFailures <= 0) return baseMs;
  const exp = Math.min(consecutiveFailures, 6);
  return Math.min(maxMs, baseMs * 2 ** (exp - 1));
}

export function isNetworkUnavailableError(error: unknown): boolean {
  if (!error) return false;
  const message = error instanceof Error ? error.message : String(error);
  return (
    /failed to fetch/i.test(message)
    || /networkerror/i.test(message)
    || /err_connection_refused/i.test(message)
    || /connection refused/i.test(message)
    || /econnrefused/i.test(message)
    || /network request failed/i.test(message)
  );
}

export function formatBytes(bytes?: number | null): string | null {
  if (bytes == null || bytes < 0) return null;
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value >= 10 || unit === 0 ? value.toFixed(0) : value.toFixed(1)} ${units[unit]}`;
}

export function formatComponentSize(component: SetupComponentStatus): string | null {
  if (
    component.show_download_sizes === false
    || component.component_kind === "credential"
    || component.installer === "credentials"
  ) {
    return null;
  }
  const isPack = component.installer === "asset_pack" || component.verifier === "asset_pack";
  const downloadBytes = component.expected_download_bytes
    ?? component.download_bytes
    ?? component.download_size_bytes
    ?? (component.download_size_mb != null ? component.download_size_mb * 1024 * 1024 : null);
  const installedBytes = component.installed_bytes ?? component.installed_size_bytes ?? 0;
  const download = formatBytes(downloadBytes)
    ?? (component.download_size_mb ? `${component.download_size_mb} MB` : null);
  if (isPack) {
    if (component.status === "source_pending" && !component.source_available) {
      return download ? `Estimated size: ${download} (official download not published yet)` : null;
    }
    const installed = formatBytes(installedBytes) ?? "0 B";
    if (download) return `Download size: ${download} · Installed size: ${installed}`;
    return `Installed size: ${installed}`;
  }
  const installed = installedBytes > 0 ? formatBytes(installedBytes) : null;
  if (download && installed) return `${download} download · ${installed} installed`;
  return download ? `${download} download` : installed ? `${installed} installed` : null;
}

export function formatDuration(seconds?: number | null): string {
  if (seconds == null || seconds < 0) return "Estimating…";
  if (seconds < 60) return "Less than a minute remaining";
  const minutes = Math.ceil(seconds / 60);
  if (minutes < 60) return `About ${minutes} min remaining`;
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  return `About ${hours} hr${remainder ? ` ${remainder} min` : ""} remaining`;
}

export function progressPercent(progress?: number | null): number {
  if (progress == null || !Number.isFinite(progress)) return 0;
  const normalized = progress <= 1 ? progress * 100 : progress;
  return Math.max(0, Math.min(100, normalized));
}
