/**
 * Keep the Co-Director chat execution card honest against the live work surface.
 *
 * The viewport polls advanceExecution; the chat bubble used to freeze on the
 * first SSE snapshot (Preparing / childjobstatus.queued / 0/1). This helper
 * overlays the same live pack onto that message.
 */
import type { CoDirectorAssistantMessageType, CoDirectorMessage, CoDirectorMessageExecution } from "./types";
import type { WorkSurfaceState } from "./AgentWorkSurface/types";

const TERMINAL = new Set(["completed", "failed", "cancelled"]);

/** Strip Python/TS enum prefixes: "ChildJobStatus.queued" → "queued". */
export function normalizeJobStatus(raw: string | undefined | null): string {
  const value = String(raw || "").trim().toLowerCase();
  if (!value) return "";
  const tail = value.includes(".") ? value.slice(value.lastIndexOf(".") + 1) : value;
  if (tail === "done") return "completed";
  return tail;
}

export function messageKindForStatus(status: string | undefined | null): CoDirectorAssistantMessageType {
  const normalized = normalizeJobStatus(status);
  if (normalized === "completed") return "completion";
  if (normalized === "failed" || normalized === "cancelled") return "error";
  return "execution_status";
}

/** Human label for a capability id (e.g. timeline.add_asset → "Add asset"). */
export function capabilityActionLabel(
  capability: string | undefined,
  fallback = "Working on your request",
): string {
  if (!capability) return fallback;
  const short = capability.split(".").pop()?.replace(/_/g, " ") || capability;
  const generating = short.replace(/generate/i, "Generating");
  return generating.charAt(0).toUpperCase() + generating.slice(1);
}

function capabilityLabel(capability: string | undefined): string {
  return capabilityActionLabel(capability, "Working on your request");
}

export function executionStatusText(execution: CoDirectorMessageExecution): string {
  const completed = execution.completed ?? 0;
  const total = execution.total ?? 0;
  const status = normalizeJobStatus(execution.status);
  const label = capabilityLabel(execution.capability);

  if (status === "completed") {
    return total ? `${label} — ${completed}/${total} complete. Done.` : `${label} — Done.`;
  }
  if (status === "failed") {
    const base = `${label} — failed. You can retry or adjust and try again.`;
    const plan = (execution.plan_data || {}) as Record<string, unknown>;
    const errBlob = `${execution.error || ""} ${JSON.stringify(plan)}`.toLowerCase();
    const cap = String(execution.capability || "").toLowerCase();
    if (cap.includes("add_asset") || cap.includes("place_asset")) {
      const hints: string[] = [];
      const hasSource = Boolean(String(plan.sourceAssetId || plan.source_asset_id || "").trim());
      if (!hasSource || (/sourceassetid|source_asset_id/.test(errBlob) && /missing|required/.test(errBlob))) {
        hints.push("Missing sourceAssetId");
      }
      if (/batchblockid|batch_block_id/.test(errBlob) && (/missing|required/.test(errBlob) || !String(plan.batchBlockId || plan.batch_block_id || "").trim())) {
        hints.push("Missing batchBlockId");
      }
      const uniq = [...new Set(hints)];
      if (uniq.length) return `${base} (${uniq.join("; ")})`;
    }
    return base;
  }
  if (status === "cancelled") {
    return `${label} — stopped.`;
  }
  const plan = (execution.plan_data || {}) as Record<string, unknown>;
  if (status === "preview" && (plan.sceneProduction || plan.preparationReady)) {
    return String(plan.creatorAck || "Timeline shot ready.");
  }
  if (status === "preview") {
    return "Prepared. Generation has not started.";
  }
  if (status === "queued") {
    return total ? `Queued — ${completed}/${total} complete.` : "Queued.";
  }
  if (status === "running" && total) {
    return `Generating — ${completed}/${total} complete.`;
  }
  if (total && status === "running") return `${label} — ${completed}/${total} complete.`;
  return `${label} — working…`;
}

function mappedChildren(live: WorkSurfaceState): CoDirectorMessageExecution["child_jobs"] {
  return (live.child_jobs || []).map((child) => ({
    job_id: child.job_id,
    child_index: child.child_index,
    label: child.label,
    status: normalizeJobStatus(child.status) || child.status,
    asset_id: child.asset_id ?? null,
    error: child.error ?? null,
    progress: child.progress,
    stage: child.stage,
  }));
}

function fingerprint(execution: CoDirectorMessageExecution): string {
  return JSON.stringify({
    id: execution.execution_id,
    status: normalizeJobStatus(execution.status),
    completed: execution.completed ?? 0,
    total: execution.total ?? 0,
    progress: execution.progress ?? 0,
    assets: execution.result_asset_ids || [],
    error: execution.error || "",
    children: (execution.child_jobs || []).map((child) => [
      child.job_id,
      normalizeJobStatus(child.status),
      child.asset_id || "",
      child.stage || "",
    ]),
    job: execution.generationJob
      ? [
          normalizeJobStatus(execution.generationJob.status),
          execution.generationJob.stage || "",
          execution.generationJob.progressPercent ?? null,
          execution.generationJob.outputAsset || "",
        ]
      : null,
  });
}

export function mergeLiveExecution(
  frozen: CoDirectorMessageExecution,
  live: WorkSurfaceState | null | undefined,
): CoDirectorMessageExecution {
  if (!frozen?.execution_id || !live?.execution_id) return normalizeFrozenExecution(frozen);
  if (frozen.execution_id !== live.execution_id) return normalizeFrozenExecution(frozen);
  if (live.mode === "normal") return normalizeFrozenExecution(frozen);

  const children = mappedChildren(live);
  const completedFromChildren = children.filter((child) => normalizeJobStatus(child.status) === "completed").length;
  const completedFromAssets = live.result_asset_ids?.length || 0;
  const total = children.length || frozen.total || completedFromAssets || 0;
  const completed = Math.max(completedFromChildren, completedFromAssets, frozen.completed ?? 0);
  const status = normalizeJobStatus(live.status) || normalizeJobStatus(frozen.status) || frozen.status;
  const resultIds = live.result_asset_ids?.length ? live.result_asset_ids : frozen.result_asset_ids;
  const progress = typeof live.progress === "number" ? live.progress : frozen.progress;
  const progressPercent =
    typeof live.progress === "number"
      ? live.progress <= 1
        ? Math.round(live.progress * 100)
        : Math.round(live.progress)
      : frozen.generationJob?.progressPercent;

  const generationJob = frozen.generationJob
    ? {
        ...frozen.generationJob,
        status: status || frozen.generationJob.status,
        stage: TERMINAL.has(status)
          ? status === "completed"
            ? "Complete"
            : status === "failed"
              ? "Failed"
              : "Cancelled"
          : frozen.generationJob.stage,
        progressPercent: TERMINAL.has(status) && status === "completed" ? 100 : progressPercent,
        outputAsset: resultIds?.[0] ?? frozen.generationJob.outputAsset,
        error: live.error ?? frozen.generationJob.error,
      }
    : frozen.generationJob;

  return {
    ...frozen,
    status,
    progress,
    completed,
    total,
    result_asset_ids: resultIds,
    child_jobs: children.length ? children : normalizeFrozenExecution(frozen).child_jobs,
    error: live.error ?? frozen.error,
    generationJob,
    capability: frozen.capability || live.capability,
    surface_type: frozen.surface_type || live.surface_type,
    collection_id: live.collection_id ?? frozen.collection_id,
  };
}

export function normalizeFrozenExecution(execution: CoDirectorMessageExecution): CoDirectorMessageExecution {
  const children = (execution.child_jobs || []).map((child) => ({
    ...child,
    status: normalizeJobStatus(child.status) || child.status,
  }));
  const completed = children.filter((child) => normalizeJobStatus(child.status) === "completed").length;
  return {
    ...execution,
    status: normalizeJobStatus(execution.status) || execution.status,
    completed: execution.completed ?? (children.length ? completed : execution.completed),
    total: execution.total ?? (children.length || execution.total),
    child_jobs: children.length ? children : execution.child_jobs,
    generationJob: execution.generationJob
      ? {
          ...execution.generationJob,
          status: normalizeJobStatus(execution.generationJob.status) || execution.generationJob.status,
        }
      : execution.generationJob,
  };
}

export function dedupeExecutionMessages(messages: CoDirectorMessage[]): CoDirectorMessage[] {
  const seen = new Set<string>();
  const next: CoDirectorMessage[] = [];
  for (const message of messages) {
    const executionId = message.execution?.execution_id;
    if (!executionId) {
      next.push(message);
      continue;
    }
    if (seen.has(executionId)) continue;
    seen.add(executionId);
    next.push(message);
  }
  return next.length === messages.length ? messages : next;
}

export function applyLiveExecutionToMessages(
  messages: CoDirectorMessage[],
  live: WorkSurfaceState | null | undefined,
): CoDirectorMessage[] {
  if (!live?.execution_id || live.mode === "normal") return messages;
  let changed = false;
  const next = dedupeExecutionMessages(messages).map((message) => {
    if (message.execution?.execution_id !== live.execution_id) return message;
    const merged = mergeLiveExecution(message.execution, live);
    const kind = messageKindForStatus(merged.status);
    // Intelligence mission 2026-09-19 (RC3): the message CONTENT is no longer
    // rewritten by the live poller. Execution state renders from the
    // `execution` payload (ExecutionSummaryCard), so the stored text stays the
    // honest snapshot the SSE delivered — it can never leak live progress
    // lines into conversational memory.
    if (fingerprint(message.execution) === fingerprint(merged) && message.messageType === kind) {
      return message;
    }
    changed = true;
    return {
      ...message,
      messageType: kind,
      execution: merged,
    };
  });
  return changed ? next : messages;
}
