import type { SceneTake, SceneTimelineMaster } from "./contracts";
import { resolveSceneTake } from "./playableVisualTakes";
import { isSceneRenderActive } from "./sceneRenderProgress";
import { sceneTakeDisplayLabel, sceneTakeIsListed } from "./sceneTakes";

/** Existing Timeline scene-card vocabulary. Do not invent a second status system. */
export type SceneTimelineStatusWord = "Draft" | "Ready" | "Working" | "Needs Attention";

/** Preview heading vocabulary: scene-card words plus take/publish words already used on Timeline. */
export type PreviewTakeStatusWord = SceneTimelineStatusWord | "Published" | "Rendering";

export function sceneTimelineStatusWord(
  master: SceneTimelineMaster | null | undefined,
): SceneTimelineStatusWord {
  const statuses = (master?.batchBlocks || []).map((batch) => batch.status);
  if (statuses.includes("Failed")) return "Needs Attention";
  if (statuses.includes("Generating") || statuses.includes("Waiting")) return "Working";
  if (statuses.includes("Queued") && isSceneRenderActive(master)) return "Working";
  if (statuses.includes("Ready") || statuses.includes("Approved") || statuses.includes("CandidateReady")) return "Ready";
  return "Draft";
}

function takeHasDisplayedResult(take: SceneTake | null | undefined): boolean {
  if (!take) return false;
  if (String(take.resultAssetId || "").trim()) return true;
  return (take.batches || []).some((member) => Boolean(String(member.assetId || "").trim()));
}

/**
 * Take actually on the Preview Monitor.
 * Preview of another take is ignored until that take has a displayed result.
 * A rendering take that is not yet shown does not steal the label.
 */
export function resolveDisplayedSceneTake(
  master: SceneTimelineMaster | null | undefined,
  previewTakeId?: string | null,
): SceneTake | null {
  const current = resolveSceneTake(master, null);
  const previewingOther = Boolean(previewTakeId && previewTakeId !== master?.currentSceneTakeId);
  if (previewingOther) {
    const preview = resolveSceneTake(master, previewTakeId);
    if (takeHasDisplayedResult(preview)) return preview;
    return current;
  }
  return resolveSceneTake(master, previewTakeId) || current;
}

function viewedTakeStatusWord(
  master: SceneTimelineMaster | null | undefined,
  take: SceneTake,
): PreviewTakeStatusWord {
  const publishedTakeId = String(master?.scenePublish?.takeId || "").trim();
  const publishedAsset = String(master?.scenePublish?.publishedAssetId || "").trim();
  if (publishedTakeId && publishedTakeId === take.id && publishedAsset) {
    return "Published";
  }
  if (take.status === "rendering" && take.id === master?.activeSceneTakeId) {
    return "Rendering";
  }

  const otherTakeRendering = Boolean(master?.activeSceneTakeId && master.activeSceneTakeId !== take.id);
  if (!otherTakeRendering) {
    return sceneTimelineStatusWord(master);
  }

  const memberStatuses = (take.batches || []).map((member) => String(member.status || ""));
  if (memberStatuses.includes("Failed")) return "Needs Attention";
  if (memberStatuses.includes("Ready") || memberStatuses.includes("Approved")) return "Ready";

  const resting = (master?.batchBlocks || []).map((batch) =>
    batch.status === "Generating" || batch.status === "Queued" ? "Draft" : batch.status,
  );
  if (resting.includes("Failed") && take.status !== "ready") return "Needs Attention";
  if (resting.includes("Ready") || resting.includes("Approved")) return "Ready";
  return "Draft";
}

/** `{Scene/Preview Status} - {Take Label}` for the take actually being viewed. Null when no takes exist. */
export function formatPreviewTakeStatusLabel(
  master: SceneTimelineMaster | null | undefined,
  previewTakeId?: string | null,
): string | null {
  const take = resolveDisplayedSceneTake(master, previewTakeId);
  if (!take || !sceneTakeIsListed(take)) return null;
  const status = viewedTakeStatusWord(master, take);
  return `${status} - ${sceneTakeDisplayLabel(take.label)}`;
}
