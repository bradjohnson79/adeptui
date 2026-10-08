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
  baselineImageWorkflow?: "ready" | "blocked";
  baselineVideoWorkflow?: "ready" | "blocked";
  estimatedDownloadBytes?: number;
  estimatedInstallBytes?: number;
  freeBytes?: number | null;
  storageShortfall?: boolean;
  nodeCatalogChecked?: boolean;
};

/** The server scan is the completion authority. Optional absence is not a blocker. */
export function scanAllowsCompletion(scan?: FirstRunScan | null): boolean {
  return scan?.essentialBlockerCount === 0
    && scan.baselineImageWorkflow === "ready"
    && scan.baselineVideoWorkflow === "ready";
}

/**
 * The installer modal opens only while the essential baseline is incomplete.
 * A missing scan does not count as incomplete unless the saved flag is explicitly false.
 * A ready scan never reopens the modal, even before the flag write returns.
 */
export function setupWizardRequired(status: {
  firstRunSetupComplete?: boolean;
  firstRunScan?: FirstRunScan | null;
} | null | undefined): boolean {
  if (!status) return false;
  if (status.firstRunScan) return !scanAllowsCompletion(status.firstRunScan);
  return status.firstRunSetupComplete === false;
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
