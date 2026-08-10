/**
 * Capability registry types and presentation helpers.
 *
 * Mirrors `studio-api/app/capabilities/models.py`. The frontend must never re-derive
 * readiness from `/api/health`, `/api/setup/status`, or the Source Manager overview — those
 * answer narrower questions, and deriving readiness in the UI is how the three surfaces
 * drifted apart in the first place. `GET /api/capabilities` is the single answer.
 */

export type CapabilityStatus =
  | "not_implemented"
  | "ui_only"
  | "backend_only"
  | "partially_wired"
  | "mock_verified"
  | "locally_verified"
  | "production_ready"
  | "blocked"
  | "degraded"
  | "not_configured"
  | "unknown"
  | "deferred_version_1_2";

export interface Capability {
  id: string;
  displayName: string;
  subsystem: string;
  status: CapabilityStatus;
  /** True only for locally_verified / production_ready / degraded. Nothing else is offered. */
  available: boolean;
  configured: boolean;
  healthy: boolean;
  readOnly: boolean;
  requiresApproval: boolean;
  dependencies: string[];
  reasonCode?: string | null;
  message: string;
  recommendedAction?: string | null;
  /** Setup / Source Manager component ids a blocker action can act on. */
  componentIds: string[];
  serviceRef?: string | null;
  httpRef?: string | null;
  scope: "global" | "project" | string;
  summary: string;
  details: Record<string, unknown>;
  lastCheckedAt: string;
}

export interface CapabilityBlocker {
  capabilityId: string;
  displayName: string;
  subsystem: string;
  status: CapabilityStatus;
  reasonCode?: string | null;
  message: string;
  recommendedAction?: string | null;
  componentIds: string[];
}

export interface CapabilitySnapshot {
  schemaVersion: number;
  projectId?: string | null;
  generatedAt: string;
  correlationId: string;
  counts: Partial<Record<CapabilityStatus, number>>;
  capabilities: Capability[];
  blockers: CapabilityBlocker[];
  /** Capability ids a caller (including Co-Director) may invoke right now. */
  callable: string[];
  /** Version 1.1 readiness denominator (excludes deferred_version_1_2). */
  readinessTotal?: number;
  /** Roadmap-deferred capability ids. */
  deferred?: string[];
  probeWarnings: string[];
}

export interface ComfyHealth {
  reachable: boolean;
  status: "ready" | "degraded" | "unreachable" | string;
  baseUrl: string;
  version?: string | null;
  devices: { name: string; type: string; vramTotalMb: number | null; vramFreeMb: number | null }[];
  nodeCatalogAvailable: boolean;
  nodeTypeCount: number;
  reasonCode?: string | null;
  message: string;
  recommendedAction?: string | null;
  models: {
    componentId: string;
    name: string;
    required: boolean;
    present: boolean;
    issueCode?: string | null;
    summary?: string;
    version?: string | null;
  }[];
  missingModelComponentIds: string[];
  checkedAt: string;
}

export interface WorkflowDescriptor {
  id: string;
  family: string;
  modality: string;
  capabilities: string[];
  templateVersion: string;
  engine: string;
  requiredInputs: string[];
  requiredNodeTypes: string[];
  requiredModelComponentIds: string[];
  modelRequirementsKnown: boolean;
}

export interface WorkflowReadiness extends WorkflowDescriptor {
  status: "ready" | "blocked" | "unknown";
  reasonCode?: string | null;
  message: string;
  recommendedAction?: string | null;
  nodeCatalogAvailable: boolean;
  missingExtensions: string[];
  missingModels: { componentId: string; name: string; issueCode?: string | null; summary?: string }[];
  modelComponents: { componentId: string; name: string; present: boolean }[];
  checkedAt: string;
}

/** Statuses that mean "an operator has to change something". */
export const BLOCKING_STATUSES: CapabilityStatus[] = ["blocked", "not_configured"];

const STATUS_LABELS: Record<CapabilityStatus, string> = {
  not_implemented: "Not implemented",
  ui_only: "UI only",
  backend_only: "Backend only",
  partially_wired: "Partially wired",
  mock_verified: "Mock verified",
  locally_verified: "Verified locally",
  production_ready: "Production ready",
  blocked: "Blocked",
  degraded: "Degraded",
  not_configured: "Not configured",
  unknown: "Unknown",
  deferred_version_1_2: "Coming in Version 1.2",
};

export function capabilityStatusLabel(status: CapabilityStatus): string {
  return STATUS_LABELS[status] ?? status;
}

/** Maps a capability status onto the existing `status-badge` ok/warn/bad vocabulary. */
export function capabilityStatusTone(status: CapabilityStatus): "ok" | "warn" | "bad" {
  if (status === "locally_verified" || status === "production_ready") return "ok";
  // Roadmap deferral is informational — never Failed / Missing / Blocked styling.
  if (status === "deferred_version_1_2") return "ok";
  if (status === "blocked") return "bad";
  if (status === "not_configured" || status === "degraded" || status === "unknown") return "warn";
  return "warn";
}

const ACTION_LABELS: Record<string, string> = {
  open_source_manager: "Open Source Manager",
  add_source_url: "Add Source URL",
  install_comfyui_extensions: "View required components",
  start_comfyui: "Start ComfyUI",
  start_ollama: "Start Ollama",
  select_model: "Select a model",
  choose_data_directory: "Choose data directory",
  run_diagnostics: "Run diagnostics",
  verify_model_path: "Verify model path",
  run_verification_render: "Run a verification render",
  open_project: "Open a project",
  reload_project: "Reload the project",
  use_real_provider: "Switch to a real provider",
  review_capability: "Review capability",
  list_capabilities: "View all capabilities",
  none: "No action available",
};

export function recommendedActionLabel(action?: string | null): string | null {
  if (!action) return null;
  return ACTION_LABELS[action] ?? action.replace(/_/g, " ");
}

export function isBlocking(status: CapabilityStatus): boolean {
  return BLOCKING_STATUSES.includes(status);
}

/**
 * Component ids named by blockers, de-duplicated and in first-seen order, so the Setup
 * Wizard and Source Manager can offer a "view required components" jump without guessing.
 */
export function blockedComponentIds(snapshot: CapabilitySnapshot | null): string[] {
  if (!snapshot) return [];
  const seen: string[] = [];
  for (const blocker of snapshot.blockers) {
    for (const componentId of blocker.componentIds) {
      if (!seen.includes(componentId)) seen.push(componentId);
    }
  }
  return seen;
}

/** Blockers on capabilities that a given subsystem cares about. */
export function blockersForSubsystems(
  snapshot: CapabilitySnapshot | null,
  subsystems: string[],
): CapabilityBlocker[] {
  if (!snapshot) return [];
  return snapshot.blockers.filter((blocker) => subsystems.includes(blocker.subsystem));
}
