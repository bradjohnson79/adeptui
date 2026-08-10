export interface ProductionPlanStep {
  stepId: string;
  order?: number;
  title: string;
  description?: string;
  state?: string;
  dependsOn?: string[];
  executionAvailability?: string;
  proposedToolId?: string | null;
  category?: string;
}

export interface ProductionPlanBlocker {
  blockerId: string;
  title: string;
  description?: string;
  severity?: string;
  state?: string;
  stepId?: string | null;
}

export interface PlanApprovalRequirement {
  requirementId: string;
  approvalType?: string;
  status?: string;
  reason?: string;
}

export interface ProductionPlan {
  planId: string;
  projectId: string;
  title: string;
  objective?: string;
  description?: string;
  state: string;
  version: number;
  unapproved?: boolean;
  steps?: ProductionPlanStep[];
  blockers?: ProductionPlanBlocker[];
  approvalRequirements?: PlanApprovalRequirement[];
  capabilitySnapshot?: {
    readiness?: string;
    capabilities?: Array<{ capabilityId: string; status?: string; available?: boolean; reason?: string | null }>;
  };
  updatedAt?: string;
  revisionReason?: string | null;
}

export interface PlanReadinessReport {
  snapshotReadiness?: string;
  currentReadiness?: string;
  changedCapabilities?: string[];
  requiresRefresh?: boolean;
}

export interface PlanEventRow {
  eventId?: string;
  eventType?: string;
  planVersion?: number;
  summary?: string;
  createdAt?: string;
}

export interface PlanVersionRow {
  planId?: string;
  version: number;
  state?: string;
  revisionReason?: string | null;
  createdAt?: string | null;
}

export function envelopeData<T = Record<string, unknown>>(inv: { result?: Record<string, unknown> | null }): T | null {
  const result = inv.result;
  if (!result || typeof result !== "object") return null;
  const data = (result as { data?: unknown }).data;
  if (data && typeof data === "object") return data as T;
  return result as T;
}
