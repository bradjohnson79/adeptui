/** Hydrate durable chat cards for leftover / failed execution packs.

Session load only rehydrates non-terminal packs via /active/latest, so a leftover
that already failed (pack.error=null, child JOB_NOT_FOUND) has no overlay and no
chat card. This helper turns GET /executions (not active/latest) into error cards.

Never remounts agent_work. Never lifts child.error onto pack.error.
*/
import type { CoDirectorMessage, CoDirectorMessageExecution } from './types';
import { capabilityActionLabel } from './liveExecutionSync';

export type ListedExecutionChild = {
  job_id?: string;
  child_index?: number;
  label?: string;
  status?: string;
  asset_id?: string | null;
  error?: string | null;
  progress?: number;
  stage?: string;
};

export type ListedExecutionPack = {
  execution_id?: string;
  capability?: string;
  status?: string;
  progress?: number;
  completed?: number;
  completed_children?: number;
  total?: number;
  total_children?: number;
  surface_type?: string;
  collection_id?: string | null;
  result_asset_ids?: string[];
  error?: string | null;
  child_jobs?: ListedExecutionChild[];
  created_at?: string;
  updated_at?: string;
  /** Optional plan / tool args when Systems lands them on the pack. */
  plan_data?: Record<string, unknown> | null;
  sourceAssetId?: string | null;
  batchBlockId?: string | null;
};

const MAX_FAILED_CARDS = 8;

function capabilityLabel(capability: string | undefined): string {
  return capabilityActionLabel(capability, 'Execution');
}

export function isFailedExecutionPack(pack: ListedExecutionPack | null | undefined): boolean {
  return Boolean(pack?.execution_id) && String(pack?.status || '').toLowerCase() === 'failed';
}

export function isMissingJobLeftover(
  pack: { error?: string | null; child_jobs?: Array<{ error?: string | null }> | null } | null | undefined,
): boolean {
  if (!pack) return false;
  const parts = [pack.error, ...(pack.child_jobs || []).map((child) => child.error)];
  return parts.some((value) => /JOB_NOT_FOUND|no longer available/i.test(String(value || '')));
}

export function isDismissedExecutionPack(pack: ListedExecutionPack | null | undefined): boolean {
  const status = String(pack?.status || '').toLowerCase();
  return status === 'cancelled' && /DISMISSED/i.test(String(pack?.error || ''));
}

export function messageCoversExecution(message: CoDirectorMessage, executionId: string): boolean {
  if (!executionId) return false;
  if (message.execution?.execution_id === executionId) return true;
  if (typeof message.id === 'string' && message.id.includes(executionId)) return true;
  return false;
}


/** ORDER 19: detail lines when Add-asset fail pack is missing sourceAssetId / batchBlockId. */
export function missingAddAssetHints(pack: ListedExecutionPack | null | undefined): string[] {
  const hints: string[] = [];
  if (!pack) return hints;
  const plan = pack.plan_data && typeof pack.plan_data === "object" ? pack.plan_data : {};
  const source =
    pack.sourceAssetId ??
    (typeof plan.sourceAssetId === "string" ? plan.sourceAssetId : null) ??
    (typeof plan.source_asset_id === "string" ? plan.source_asset_id : null);
  const batch =
    pack.batchBlockId ??
    (typeof plan.batchBlockId === "string" ? plan.batchBlockId : null) ??
    (typeof plan.batch_block_id === "string" ? plan.batch_block_id : null);
  const textBlob = [
    pack.error,
    ...((pack.child_jobs || []).map((c) => c.error)),
    JSON.stringify(plan),
  ]
    .map((v) => String(v || "").toLowerCase())
    .join("\n");
  const cap = String(pack.capability || "").toLowerCase();
  const isAddAsset = cap.includes("add_asset") || cap.includes("place_asset");
  if (!isAddAsset) return hints;
  const mentionsSource = /sourceassetid|source_asset_id/.test(textBlob);
  const mentionsBatch = /batchblockid|batch_block_id/.test(textBlob);
  if (!source || (mentionsSource && /missing|required/.test(textBlob))) {
    hints.push("Missing sourceAssetId");
  }
  if (mentionsBatch && (!batch || /missing|required/.test(textBlob))) {
    hints.push("Missing batchBlockId");
  }
  return hints;
}

export function failedPackToChatMessage(pack: ListedExecutionPack): CoDirectorMessage | null {
  const executionId = typeof pack.execution_id === 'string' ? pack.execution_id : '';
  if (!executionId) return null;
  const children = Array.isArray(pack.child_jobs) ? pack.child_jobs : [];
  const completed =
    typeof pack.completed === 'number'
      ? pack.completed
      : typeof pack.completed_children === 'number'
        ? pack.completed_children
        : children.filter((c) => String(c.status || '').toLowerCase() === 'completed').length;
  const total =
    typeof pack.total === 'number'
      ? pack.total
      : typeof pack.total_children === 'number'
        ? pack.total_children
        : children.length;
  const execution: CoDirectorMessageExecution = {
    execution_id: executionId,
    capability: pack.capability,
    status: pack.status,
    progress: pack.progress,
    completed,
    total,
    surface_type: pack.surface_type,
    collection_id: pack.collection_id ?? null,
    result_asset_ids: Array.isArray(pack.result_asset_ids) ? pack.result_asset_ids : undefined,
    // Keep pack.error as-is (null for leftover JOB_NOT_FOUND). Do not lift child.error.
    error: typeof pack.error === 'string' ? pack.error : null,
    child_jobs: children.map((c) => ({
      job_id: c.job_id,
      child_index: c.child_index,
      label: c.label,
      status: c.status,
      asset_id: c.asset_id ?? null,
      error: typeof c.error === 'string' ? c.error : null,
      progress: c.progress,
      stage: c.stage,
    })),
  };
  const createdAt = pack.updated_at || pack.created_at || new Date().toISOString();
  return {
    id: 'exec-leftover-' + executionId,
    role: 'assistant',
    content: (() => {
      if (isMissingJobLeftover(pack)) {
        return capabilityLabel(pack.capability) + ' — no longer available. Dismiss this card.';
      }
      const base =
        capabilityLabel(pack.capability) + ' — failed. You can retry or adjust and try again.';
      const hints = missingAddAssetHints(pack);
      return hints.length ? `${base} (${hints.join("; ")})` : base;
    })(),
    createdAt,
    messageType: 'error',
    execution,
  };
}

export function isForeignToCharacterCreator(pack: ListedExecutionPack | null | undefined): boolean {
  const cap = String(pack?.capability || '').toLowerCase();
  const surface = String(pack?.surface_type || '').toLowerCase();
  if (
    surface.includes('ers') ||
    surface.includes('scene') ||
    surface.includes('atlas') ||
    cap.includes('ers') ||
    cap.includes('scene.') ||
    cap.includes('zimage') ||
    cap.includes('atlas')
  ) {
    return true;
  }
  return false;
}

export function isCharacterCreatorCapability(capability?: string | null): boolean {
  const cap = String(capability || '').toLowerCase();
  return cap.startsWith('character.') || cap.includes('visual_sheet') || cap.includes('character_sheet');
}

export function mergeFailedExecutionCards(
  messages: CoDirectorMessage[],
  packs: ListedExecutionPack[] | null | undefined,
): CoDirectorMessage[] {
  const incoming = Array.isArray(packs) ? packs : [];
  const failed = incoming
    .filter((pack) => isFailedExecutionPack(pack) && !isDismissedExecutionPack(pack) && String(pack.error || '') !== 'DISMISSED')
    .filter((pack) => !isForeignToCharacterCreator(pack))
    .slice(0, MAX_FAILED_CARDS);
  if (!failed.length) return messages;
  const extras: CoDirectorMessage[] = [];
  for (const pack of failed.slice().reverse()) {
    const executionId = pack.execution_id as string;
    if (messages.some((m) => messageCoversExecution(m, executionId))) continue;
    if (extras.some((m) => messageCoversExecution(m, executionId))) continue;
    const card = failedPackToChatMessage(pack);
    if (card) extras.push(card);
  }
  return extras.length ? [...messages, ...extras] : messages;
}
