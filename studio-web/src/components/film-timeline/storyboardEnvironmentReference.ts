/**
 * The current project's Storyboard as a Timeline Environment reference.
 *
 * MiniMax H3 Base Optimized is reference-to-video and accepts up to nine
 * pictures (maximumReferenceImages). A storyboard is the ordered frames that
 * already have Library images. Empty slots are not frames. Those pictures are
 * environment references, in board order, and the storyboard id stays on each
 * one so the shot remembers which board they came from.
 */

export type StoryboardFrameRef = {
  assetId: string;
  panelId: string;
  order: number;
};

export type StoryboardEnvironmentCandidate = {
  documentId: string;
  projectId: string;
  title: string;
  aspectRatio: string;
  frames: StoryboardFrameRef[];
};

export type StoryboardWorkspaceLike = {
  document?: {
    id?: string;
    projectId?: string;
    title?: string;
    aspectRatio?: string;
    panelOrder?: string[];
  } | null;
  panels?: Array<{ panelId?: string; assetId?: string | null }>;
};

export type StoryboardResolve =
  | { ok: true; candidate: StoryboardEnvironmentCandidate }
  | { ok: false; reason: "NO_STORYBOARD" | "OTHER_PROJECT" | "EMPTY_STORYBOARD" | "MISSING_PANEL" | "MISSING_FRAME"; detail?: string };

export type StoryboardReferenceSave = {
  assetId: string;
  type: "environment";
  label: string;
  tag: string;
  source: string;
  role: string;
};

export function resolveStoryboardEnvironment(
  projectId: string,
  workspace: StoryboardWorkspaceLike | null | undefined,
  availableAssetIds?: ReadonlySet<string>,
): StoryboardResolve {
  const document = workspace?.document;
  const documentId = String(document?.id || "").trim();
  if (!document || !documentId) return { ok: false, reason: "NO_STORYBOARD" };
  const owner = String(document.projectId || "").trim();
  if (owner && owner !== projectId) return { ok: false, reason: "OTHER_PROJECT", detail: owner };

  const panels = workspace?.panels || [];
  const byId = new Map(panels.map((panel) => [String(panel.panelId || ""), panel]));
  const order = (document.panelOrder || []).map((id) => String(id || "").trim()).filter(Boolean);
  const sequence = order.length ? order : panels.map((panel) => String(panel.panelId || "")).filter(Boolean);
  const frames: StoryboardFrameRef[] = [];
  for (const panelId of sequence) {
    const panel = byId.get(panelId);
    if (!panel) return { ok: false, reason: "MISSING_PANEL", detail: panelId };
    const assetId = String(panel.assetId || "").trim();
    if (!assetId) continue;
    if (availableAssetIds && !availableAssetIds.has(assetId)) {
      return { ok: false, reason: "MISSING_FRAME", detail: assetId };
    }
    frames.push({ assetId, panelId, order: frames.length + 1 });
  }
  if (!frames.length) return { ok: false, reason: "EMPTY_STORYBOARD" };
  return {
    ok: true,
    candidate: {
      documentId,
      projectId,
      title: String(document.title || "Storyboard").trim() || "Storyboard",
      aspectRatio: String(document.aspectRatio || "16:9"),
      frames,
    },
  };
}

/** One existing Timeline environment reference per frame, in board order. */
export function storyboardEnvironmentSaves(candidate: StoryboardEnvironmentCandidate): StoryboardReferenceSave[] {
  const source = `storyboard:${candidate.documentId}`;
  return candidate.frames.map((frame) => ({
    assetId: frame.assetId,
    type: "environment" as const,
    label: `${candidate.title} ${frame.order}`,
    tag: `Storyboard${frame.order}`,
    source,
    role: `frame:${frame.order}`,
  }));
}
