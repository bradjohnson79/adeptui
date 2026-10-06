/** Creator-written Timed Prompt text. Continuation stubs are not a Scene Prompt. */

const CONTINUATION_PREFIX = "[CONTINUATION";

export function authoredScenePromptFromTimedPrompts(
  master: {
    batchBlocks?: Array<{
      order?: number | null;
      promptSegments?: Array<{ start?: number | null; text?: string | null }> | null;
    }> | null;
  } | null
  | undefined,
): string {
  const parts: { order: number; start: number; text: string }[] = [];
  (master?.batchBlocks || []).forEach((batch, index) => {
    const order = Number(batch.order ?? index);
    for (const segment of batch.promptSegments || []) {
      const text = String(segment.text || "").trim();
      if (!text || text.startsWith(CONTINUATION_PREFIX)) continue;
      parts.push({
        order: Number.isFinite(order) ? order : index,
        start: Number(segment.start) || 0,
        text,
      });
    }
  });
  parts.sort((a, b) => a.order - b.order || a.start - b.start);
  return parts.map((part) => part.text).join("\n\n");
}
