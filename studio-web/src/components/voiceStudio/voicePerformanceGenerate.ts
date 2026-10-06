import type { VoicePerformanceCapabilities, VoicePerformanceTake } from "../../contracts/voicePerformanceM410";

export type VoicePerformanceGenerationProgress = {
  source: "take_level";
  completed: number;
  total: number;
  percent: number;
  active: boolean;
  currentTakeNumber?: number | null;
  label: string;
  batchId?: string | null;
};

export function voicePerformanceCanGenerateTakes(opts: {
  hasApprovedVoiceIdentity: boolean;
  capabilities: Pick<VoicePerformanceCapabilities, "ready"> | null;
}): boolean {
  if (!opts.hasApprovedVoiceIdentity) return false;
  if (opts.capabilities == null) return true;
  return Boolean(opts.capabilities.ready);
}

export function voicePerformanceRuntimeNotice(
  capabilities: Pick<VoicePerformanceCapabilities, "ready" | "message"> | null,
): { kind: "checking" | "blocked" | "ready"; message: string } {
  if (capabilities == null) {
    return { kind: "checking", message: "Checking the local voice worker…" };
  }
  if (!capabilities.ready) {
    return {
      kind: "blocked",
      message: capabilities.message || "Voice generation failed: local voice worker unavailable.",
    };
  }
  return { kind: "ready", message: capabilities.message || "" };
}

/** Discrete take-level % only. Never fabricate smooth engine percentages. */
export function voicePerformanceTakePercent(opts: {
  status?: string | null;
  explicit?: number | null;
  generating?: boolean;
  completed?: number;
  total?: number;
}): number {
  const explicit = opts.explicit;
  if (typeof explicit === "number" && Number.isFinite(explicit)) {
    const raw = explicit <= 1 ? explicit * 100 : explicit;
    return Math.max(0, Math.min(100, Math.round(raw)));
  }
  const total = Math.max(0, Math.round(opts.total || 0));
  const completed = Math.max(0, Math.round(opts.completed || 0));
  if (total > 0) {
    return Math.max(0, Math.min(100, Math.round((completed / total) * 100)));
  }
  const status = String(opts.status || "").toLowerCase();
  if (status === "completed" || status === "approved") return 100;
  if (status === "failed" || status === "cancelled" || status === "rejected") return 0;
  if (status === "running" || status === "queued" || opts.generating) return 0;
  return 0;
}

export function formatVoicePerformanceTakeStatus(status: string | null | undefined): string {
  const value = String(status || "").toLowerCase();
  if (value === "queued") return "Preparing";
  if (value === "running") return "Generating";
  if (value === "completed") return "Ready";
  if (value === "failed") return "Failed";
  if (value === "cancelled") return "Cancelled";
  if (value === "approved") return "Approved";
  if (value === "rejected") return "Rejected";
  return value ? value.replace(/^\w/, (char) => char.toUpperCase()) : "Unknown";
}

export function isPendingVoicePerformanceTake(take: Pick<VoicePerformanceTake, "id">): boolean {
  return String(take.id || "").startsWith("pending-take-");
}

export function pendingVoicePerformanceTakes(opts: {
  recordId?: string | null;
  count: number;
  startNumber?: number;
  labelStartNumber?: number;
  createdAt?: string;
  batchId?: string;
}): VoicePerformanceTake[] {
  const count = Math.max(0, Math.min(8, Math.round(opts.count || 0)));
  const startNumber = Math.max(1, Math.round(opts.startNumber || 1));
  const labelStart = Math.max(1, Math.round(opts.labelStartNumber || 1));
  const createdAt = opts.createdAt || new Date().toISOString();
  const recordId = String(opts.recordId || "pending");
  const batchId = opts.batchId || `pending-batch-${createdAt}`;
  return Array.from({ length: count }, (_, index) => {
    const takeNumber = startNumber + index;
    const labelNumber = labelStart + index;
    return {
      id: `pending-take-${createdAt}-${index}`,
      recordId,
      takeNumber,
      label: `Take ${labelNumber}`,
      status: index === 0 ? "running" : "queued",
      directionSnapshot: {
        _generationBatch: {
          batchId,
          batchIndex: index + 1,
          batchTotal: count,
          takeNumber,
        },
      },
      createdAt,
      updatedAt: createdAt,
    };
  });
}

export function dropPendingVoicePerformanceTakes(
  takes: VoicePerformanceTake[] | null | undefined,
): VoicePerformanceTake[] {
  return (takes || []).filter((take) => !isPendingVoicePerformanceTake(take));
}

export function sortVoicePerformanceTakes(
  takes: VoicePerformanceTake[] | null | undefined,
): VoicePerformanceTake[] {
  return [...(takes || [])].sort(
    (left, right) =>
      left.takeNumber - right.takeNumber ||
      String(left.createdAt || "").localeCompare(String(right.createdAt || "")),
  );
}

/**
 * Merge by takeNumber so pending slots become the real take without reshuffling.
 * Real (non-pending) rows always win for the same takeNumber.
 */
export function mergeVoicePerformanceTakes(
  current: VoicePerformanceTake[],
  incoming: VoicePerformanceTake[] | null | undefined,
): VoicePerformanceTake[] {
  const byNumber = new Map<number, VoicePerformanceTake>();
  const byId = new Map<string, VoicePerformanceTake>();

  const consider = (take: VoicePerformanceTake | null | undefined) => {
    if (!take?.id) return;
    const existingById = byId.get(take.id);
    if (existingById && isPendingVoicePerformanceTake(existingById) && !isPendingVoicePerformanceTake(take)) {
      byId.set(take.id, take);
    } else if (!existingById) {
      byId.set(take.id, take);
    } else if (!isPendingVoicePerformanceTake(take)) {
      byId.set(take.id, take);
    }

    const num = Number(take.takeNumber);
    if (!Number.isFinite(num)) return;
    const existing = byNumber.get(num);
    if (!existing) {
      byNumber.set(num, take);
      return;
    }
    const existingPending = isPendingVoicePerformanceTake(existing);
    const nextPending = isPendingVoicePerformanceTake(take);
    if (existingPending && !nextPending) {
      byNumber.set(num, take);
      return;
    }
    if (!existingPending && nextPending) return;
    byNumber.set(num, take);
  };

  for (const take of current || []) consider(take);
  for (const take of incoming || []) consider(take);

  return sortVoicePerformanceTakes([...byNumber.values()]);
}

export function voicePerformanceBatchProgress(opts: {
  takes: VoicePerformanceTake[];
  expectedTotal?: number;
  batchStartNumber?: number;
  generating?: boolean;
  serverProgress?: Partial<VoicePerformanceGenerationProgress> | null;
}): VoicePerformanceGenerationProgress {
  const server = opts.serverProgress;
  if (
    server &&
    typeof server.percent === "number" &&
    Number.isFinite(server.percent) &&
    typeof server.total === "number" &&
    server.total > 0 &&
    server.source !== "fabricated"
  ) {
    const total = Math.max(0, Math.round(server.total));
    const completed = Math.max(0, Math.min(total, Math.round(server.completed || 0)));
    const percent = Math.max(0, Math.min(100, Math.round(server.percent)));
    const active = Boolean(server.active ?? opts.generating);
    return {
      source: "take_level",
      completed,
      total,
      percent: active ? percent : percent || (completed >= total ? 100 : percent),
      active,
      currentTakeNumber: server.currentTakeNumber ?? null,
      label:
        server.label ||
        (active
          ? `Generating Take ${Math.min(total, completed + 1)} of ${total}…`
          : completed >= total && total > 0
            ? "Generation complete"
            : ""),
      batchId: server.batchId ?? null,
    };
  }

  const start = Math.max(1, Math.round(opts.batchStartNumber || 1));
  const expected = Math.max(0, Math.round(opts.expectedTotal || 0));
  const batchTakes = sortVoicePerformanceTakes(opts.takes).filter((take) => {
    if (!expected) return true;
    return take.takeNumber >= start && take.takeNumber < start + expected;
  });
  const total = expected || batchTakes.length;
  const terminal = new Set(["completed", "approved", "failed", "cancelled", "rejected"]);
  const completed = batchTakes.filter((take) => terminal.has(String(take.status || "").toLowerCase())).length;
  const running = batchTakes.find((take) => String(take.status || "").toLowerCase() === "running");
  const queued = batchTakes.find((take) => String(take.status || "").toLowerCase() === "queued");
  const active = Boolean(opts.generating || running || queued);
  const percent = total > 0 ? Math.max(0, Math.min(100, Math.round((completed / total) * 100))) : 0;
  const currentTakeNumber = running?.takeNumber ?? queued?.takeNumber ?? null;
  const currentIndex = currentTakeNumber != null ? currentTakeNumber - start + 1 : completed + 1;
  return {
    source: "take_level",
    completed,
    total,
    percent: active ? percent : total > 0 && completed >= total ? 100 : percent,
    active,
    currentTakeNumber,
    label: active
      ? `Generating Take ${Math.max(1, Math.min(total || 1, currentIndex))} of ${total || 1}…`
      : total > 0 && completed >= total
        ? "Generation complete"
        : "",
    batchId: null,
  };
}

export function nextVoicePerformanceTakeNumber(takes: VoicePerformanceTake[] | null | undefined): number {
  const real = dropPendingVoicePerformanceTakes(takes);
  if (!real.length) return 1;
  return Math.max(...real.map((take) => Number(take.takeNumber) || 0)) + 1;
}
