const REQUIRED_FIRST_RUN_IDS = ["python", "ffmpeg", "comfyui"] as const;

const BLOCKING_REQUIRED_STATUSES = new Set([
  "error",
  "installing",
  "checking",
  "unknown",
  "not_installed",
  "download_unavailable",
  "source_pending",
]);

export type FirstRunComponent = {
  id?: string;
  component_id?: string;
  status?: string;
};

export type FirstRunScan = {
  alreadyReady?: { id: string; name: string }[];
  essentialNeeded?: { id: string; name: string; status?: string }[];
  essentialBlockerCount?: number;
  optionalAbsentCount?: number;
  baselineImageWorkflow?: "ready" | "blocked" | "not_required";
  baselineVideoWorkflow?: "ready" | "blocked" | "not_required";
  installationProfile?: "local" | "api" | "hybrid" | null;
  estimatedDownloadBytes?: number;
  estimatedInstallBytes?: number;
  freeBytes?: number | null;
  storageShortfall?: boolean;
  nodeCatalogChecked?: boolean;
};

/** Discovered models and keys are not a profile. Only a saved value is named. */
export function installationProfileLabel(value?: string | null): string {
  if (value === "local") return "Local";
  if (value === "api") return "API";
  if (value === "hybrid") return "Hybrid";
  return "Not chosen yet";
}

function workflowSatisfied(value: FirstRunScan["baselineImageWorkflow"]): boolean {
  return value === "ready" || value === "not_required";
}

/** The server scan is the completion authority. Optional absence is not a blocker. */
export function scanAllowsCompletion(scan?: FirstRunScan | null): boolean {
  return scan?.essentialBlockerCount === 0
    && workflowSatisfied(scan.baselineImageWorkflow)
    && workflowSatisfied(scan.baselineVideoWorkflow);
}

/**
 * The wizard opens only while setup has not been saved as complete.
 * A missing local model or ComfyUI does not reopen it after completion.
 */
export function setupWizardRequired(status: {
  firstRunSetupComplete?: boolean;
  firstRunScan?: FirstRunScan | null;
} | null | undefined): boolean {
  if (!status) return false;
  return status.firstRunSetupComplete !== true;
}

/** Python, FFmpeg, and ComfyUI only. The image and video baseline is firstRunScan. */
export function requiredFirstRunReady(components: FirstRunComponent[]): boolean {
  const byId = new Map(components.map((component) => [component.id || component.component_id, component]));
  return REQUIRED_FIRST_RUN_IDS.every((id) => {
    const row = byId.get(id);
    return Boolean(row?.status) && !BLOCKING_REQUIRED_STATUSES.has(row?.status || "");
  });
}

/**
 * Choose the workspace only after a successful flag read.
 * A failed read stays on Home so an already-complete record is not treated as a new first run.
 * A successful read that is not explicitly complete opens the wizard.
 */
export function bootHandoffTarget(
  firstRunSetupComplete: boolean | undefined,
  statusReadFailed: boolean,
): "/setup" | "/" {
  if (statusReadFailed) return "/";
  return firstRunSetupComplete === true ? "/" : "/setup";
}

let rememberedComplete: boolean | undefined;

export function rememberFirstRunComplete(value: boolean | undefined): void {
  if (value === true || value === false) rememberedComplete = value;
}

export function rememberedFirstRunComplete(): boolean | undefined {
  return rememberedComplete;
}
