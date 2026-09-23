export type HealthCriticality = "critical" | "high" | "standard" | "optional";
export type HealthCategory =
  | "core"
  | "project"
  | "creative_studio"
  | "provider"
  | "runtime"
  | "persistence"
  | "jobs"
  | "integration";
export type HealthStatus =
  | "healthy"
  | "ready"
  | "connected"
  | "busy"
  | "starting"
  | "slow"
  | "degraded"
  | "warning"
  | "blocked"
  | "failed"
  | "offline"
  | "timed_out"
  | "not_installed"
  | "disabled"
  | "not_configured"
  | "not_tested"
  | "experimental"
  | "unknown"
  | "not_applicable";

export type CoDirectorStatusIndicator =
  | "Operational"
  | "Degraded"
  | "Blocked"
  | "Not Checked"
  | "Checking";

export interface RecoveryAction {
  id: string;
  label: string;
  description?: string;
  kind: "open_route" | "open_panel" | "open_logs" | "refresh" | "confirm_api";
  path?: string | null;
  panel?: string | null;
  endpoint?: string | null;
  method?: string | null;
  requiresConfirmation?: boolean;
}

export interface StatusRegistryCheck {
  id: string;
  title: string;
  description: string;
  category: HealthCategory;
  criticality: HealthCriticality;
  standard: boolean;
  deep: boolean;
  projectScoped: boolean;
  sceneScoped: boolean;
  recoveryActions: RecoveryAction[];
}

export interface StatusCheckResult {
  checkId: string;
  title: string;
  category: HealthCategory;
  criticality: HealthCriticality;
  status: HealthStatus;
  score: number;
  summary: string;
  message: string;
  durationMs: number;
  timeoutMs?: number | null;
  awaitedDependency?: string | null;
  lastHealthyAt?: string | null;
  warnings: string[];
  blockers: string[];
  recoveryActions: RecoveryAction[];
  details: Record<string, unknown>;
  checkedAt: string;
  timedOut: boolean;
  partial: boolean;
  stale?: boolean;
  readinessClass?: string | null;
  v11Requirement?: string | null;
  workflowScope?: string | null;
  productionEffect?: string | null;
  severity?: string | null;
}

export interface StatusCategoryTally {
  category: HealthCategory;
  label: string;
  total: number;
  healthy: number;
  warnings: number;
  blocked: number;
}

export interface StatusExplainability {
  band: string;
  dominantChecks: string[];
  blockers: string[];
  warnings: string[];
  reasons: string[];
}

export interface StatusRunSummary {
  statusIndicator: CoDirectorStatusIndicator;
  score: number;
  band: string;
  mode: "standard" | "deep";
  totalChecks: number;
  healthyChecks: number;
  warningChecks: number;
  blockedChecks: number;
  checkedAt: string;
  scoreExplanation: string;
  scoreSemantics?: string;
  readinessPolicyVersion?: string;
}

export interface StatusRun {
  runId: string;
  mode: "standard" | "deep";
  projectId?: string | null;
  sceneId?: string | null;
  workspace?: string | null;
  startedAt: string;
  completedAt: string;
  partial: boolean;
  cancelled: boolean;
  summary: StatusRunSummary;
  categories: StatusCategoryTally[];
  explainability: StatusExplainability;
  results: StatusCheckResult[];
  readOnly?: boolean;
  mutatesRuntime?: boolean;
  mutatesConfig?: boolean;
  installsModels?: boolean;
  forceRefresh?: boolean;
}

export interface StatusCheckRequest {
  projectId?: string;
  sceneId?: string;
  workspace?: string;
  checkIds?: string[];
  forceRefresh?: boolean;
}
