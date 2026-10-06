/** Pending plan brief view model — from deliberation_decision SSE. */

export type PendingPlanStepView = {
  stepId?: string;
  title?: string;
  goal?: string;
  capabilityId?: string;
  status?: string;
  dependsOn?: string[];
  routeLock?: Record<string, unknown>;
};

export type PendingProductionPlanView = {
  planId?: string;
  goal?: string;
  summary?: string;
  steps?: PendingPlanStepView[];
  wave4PlanId?: string;
  parentExecutionId?: string;
};

export type SelectivePreflightView = {
  required?: boolean;
  expensive?: boolean;
  strict?: boolean;
  multiStep?: boolean;
  checks?: string[];
  notes?: string[];
  runtimeNeeds?: string[];
};

export type PendingPlanBriefView = {
  briefId?: string;
  planId?: string;
  stepId?: string;
  summary?: string;
  projectId?: string;
  capability?: string;
  expiresAt?: string;
  state?: string;
  invalidationRules?: string[];
  productionPlan?: PendingProductionPlanView | null;
  selectivePreflight?: SelectivePreflightView | null;
  responsePurpose?: string;
  act?: string;
  reasonCodes?: string[];
  /** Server-declared freshness; client also rechecks expiresAt. */
  fresh?: boolean;
};

export function isPendingBriefFresh(brief: PendingPlanBriefView | null | undefined, nowMs = Date.now()): boolean {
  if (!brief) return false;
  if (brief.fresh === false) return false;
  const state = String(brief.state || "").toUpperCase();
  const freshStates = new Set([
    "AWAITING_CONFIRMATION",
    "PENDING",
    "AWAITING",
    "PLANNING",
    "AWAITING_REQUIRED_INPUT",
  ]);
  if (state && !freshStates.has(state)) return false;
  const expires = brief.expiresAt;
  if (!expires) return brief.fresh !== false;
  const exp = Date.parse(expires);
  if (Number.isNaN(exp)) return false;
  return nowMs <= exp;
}

export function summarizePendingRoute(brief: PendingPlanBriefView): string {
  const lock =
    brief.productionPlan?.steps?.[0]?.routeLock ||
    (brief as { routeLock?: Record<string, unknown> }).routeLock ||
    {};
  const provider = String((lock as Record<string, unknown>).provider || "");
  const model = String(
    (lock as Record<string, unknown>).modelId ||
      (lock as Record<string, unknown>).model ||
      "",
  );
  const level = String((lock as Record<string, unknown>).level || "");
  const bits = [provider, model, level].filter(Boolean);
  return bits.join(" · ");
}

/** Pure helper for unit tests — build view from SSE payload. */
export function pendingBriefFromDeliberationEvent(event: {
  pendingBrief?: Record<string, unknown>;
  pendingBriefFresh?: boolean;
  productionPlan?: Record<string, unknown>;
  selectivePreflight?: Record<string, unknown>;
  responsePlan?: { purpose?: string };
  act?: string;
  reasonCodes?: string[];
}): PendingPlanBriefView | null {
  const raw = event.pendingBrief;
  if (!raw || typeof raw !== "object") return null;
  const planId = String(raw.planId || "");
  const summary = String(raw.summary || "");
  if (!planId && !summary && !raw.briefId) return null;
  return {
    briefId: String(raw.briefId || ""),
    planId,
    stepId: String(raw.stepId || ""),
    summary,
    projectId: String(raw.projectId || ""),
    capability: String(raw.capability || ""),
    expiresAt: String(raw.expiresAt || ""),
    state: String(raw.state || "AWAITING_CONFIRMATION"),
    invalidationRules: Array.isArray(raw.invalidationRules)
      ? (raw.invalidationRules as string[])
      : [],
    productionPlan: (event.productionPlan as PendingProductionPlanView) ||
      (raw.productionPlanSnapshot as PendingProductionPlanView) ||
      null,
    selectivePreflight: (event.selectivePreflight as SelectivePreflightView) || null,
    responsePurpose: event.responsePlan?.purpose || "",
    act: event.act || "",
    reasonCodes: list(event.reasonCodes),
    fresh: event.pendingBriefFresh !== false,
  };
}

function list(v: string[] | undefined): string[] {
  return Array.isArray(v) ? v.map(String) : [];
}
