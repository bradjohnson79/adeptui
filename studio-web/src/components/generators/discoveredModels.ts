/**
 * Shared hosted-catalog fetch for Character / Prop / later Co-Director
 * video, audio, and LLM surfaces. Does not invent a picker — callers render.
 *
 * One-line reuse: fetchDiscoveredHostedModelRows("video")
 * API: GET /api/hosted-providers/discovered-models?modality=...
 */
import { api } from "../../api";

export const DISCOVERED_HOSTED_MODALITIES = ["image", "video", "audio", "llm"] as const;
export type DiscoveredHostedModality = (typeof DISCOVERED_HOSTED_MODALITIES)[number];

export function discoveredHostedModelRows(payload: unknown): Record<string, unknown>[] {
  const src = (payload || {}) as { models?: unknown; items?: unknown };
  const rows = src.models || src.items || [];
  return Array.isArray(rows) ? (rows as Record<string, unknown>[]) : [];
}

export async function fetchDiscoveredHostedModelRows(
  modality?: DiscoveredHostedModality | string,
): Promise<Record<string, unknown>[]> {
  const discovered = await api.hostedProvidersDiscoveredModels(modality).catch(() => null);
  return discoveredHostedModelRows(discovered);
}
