import type { PreviewComposition } from "../components/timeline-master/TimelinePreviewComposer";

/**
 * Bottom-center Re-Take and Full Screen stay on the Preview Monitor.
 * They are not limited to a finished render.
 */
export function shouldShowPreviewVideoMenu(_args: {
  sceneMode?: string | null;
  composition?: PreviewComposition | null;
  hasGeneratedTakeAtPlayhead?: boolean;
}): boolean {
  return true;
}
