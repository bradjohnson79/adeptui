/**
 * Bind a scene-time Timed Prompt segment to the overlapping execution window (batchBlock).
 * Filmmaker owns the prompt; Co-Director owns windows — this is resolution only, not authorship.
 */
import type { BatchBlock } from "./contracts";

export type PromptTimeRange = {
  start: number;
  length: number;
};

export function executionWindowSpans(
  batches: BatchBlock[] | null | undefined,
): Array<{ batch: BatchBlock; start: number; end: number }> {
  const sorted = [...(batches || [])].sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
  let cursor = 0;
  return sorted.map((batch) => {
    const start = cursor;
    const end = cursor + Math.max(0, Number(batch.duration?.plannedDuration || 0));
    cursor = end;
    return { batch, start, end };
  });
}

export function resolveExecutionWindowForPrompt(
  batches: BatchBlock[] | null | undefined,
  prompt: PromptTimeRange | null | undefined,
): BatchBlock | null {
  if (!prompt) return null;
  const spans = executionWindowSpans(batches);
  if (!spans.length) return null;
  const start = Number(prompt.start) || 0;
  for (const { batch, start: a, end } of spans) {
    if (start + 1e-6 >= a && start < end - 1e-9) return batch;
  }
  return spans[spans.length - 1]?.batch || spans[0]?.batch || null;
}
