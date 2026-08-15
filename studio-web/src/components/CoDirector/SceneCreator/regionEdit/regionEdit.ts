/**
 * Scene Creator Inpaint / Region Edit helpers.
 * Capability labels are frozen product truth — not inferred from txt2img.
 */
import type { SceneCinematographerPack } from "../cinematographer/cameraCommandEngine";
import type { SceneShot, SceneShotCandidate } from "../types";

export type RegionEditOperation = "remove" | "replace" | "add" | "modify";
export type RegionEditCapabilityLabel = "Native Inpaint" | "Image Edit" | "Unsupported";

export const UNSUPPORTED_REGION_EDIT_MESSAGE =
  "This generator cannot edit a region. Choose Z-Image for Native Inpaint.";

export const VISUAL_INHERITANCE_BLOCKED_MESSAGE =
  "This generator cannot keep the painted correction. Choose Z-Image or FLUX for Final Quality Render.";

export const REGION_EDIT_OPERATIONS: { id: RegionEditOperation; label: string }[] = [
  { id: "remove", label: "Remove" },
  { id: "replace", label: "Replace" },
  { id: "add", label: "Add" },
  { id: "modify", label: "Modify" },
];

const FAMILY_CAPS: Record<
  string,
  { supportsInpaint: boolean; supportsEditing: boolean; label: RegionEditCapabilityLabel }
> = {
  zimage: { supportsInpaint: true, supportsEditing: true, label: "Native Inpaint" },
  flux: { supportsInpaint: false, supportsEditing: true, label: "Image Edit" },
  qwen2512: { supportsInpaint: false, supportsEditing: false, label: "Unsupported" },
  qwen: { supportsInpaint: false, supportsEditing: false, label: "Unsupported" },
  illustrious: { supportsInpaint: false, supportsEditing: false, label: "Unsupported" },
};

export function regionEditCapability(family: string): {
  family: string;
  supportsInpaint: boolean;
  supportsEditing: boolean;
  label: RegionEditCapabilityLabel;
} {
  const key = (family || "").trim().toLowerCase();
  const caps = FAMILY_CAPS[key];
  if (caps) return { family: key, ...caps };
  return { family: key, supportsInpaint: false, supportsEditing: false, label: "Unsupported" };
}

export type RegionEditSource = {
  sourceAssetId: string;
  parentCandidateId?: string;
  cameraStateVersion?: number | null;
  fromPreview?: boolean;
};

export type RegionEditSourceOption = {
  id: string;
  assetId: string;
  label: string;
  stage: "preview" | "final";
  cameraStateVersion?: number | null;
  parentCandidateId?: string;
  fromPreview?: boolean;
};

export function listRegionEditSources(input: {
  shot: SceneShot | null;
  cinematographer?: SceneCinematographerPack | null;
  selectedCameraId?: string;
}): RegionEditSourceOption[] {
  const out: RegionEditSourceOption[] = [];
  const seen = new Set<string>();
  const add = (option: RegionEditSourceOption) => {
    if (!option.assetId || seen.has(option.assetId)) return;
    seen.add(option.assetId);
    out.push(option);
  };

  const cameras = input.cinematographer?.cameras || [];
  const selected =
    cameras.find((c) => c.cameraId === input.selectedCameraId) ||
    cameras.find((c) => c.lineage?.locked) ||
    cameras.find((c) => c.lineage?.previewStatus === "ready");
  const previewId = selected?.lineage?.previewAssetId || "";
  const previewReady = selected?.lineage?.previewStatus === "ready" || Boolean(selected?.lineage?.locked);
  if (previewId && previewReady) {
    add({
      id: `preview:${previewId}`,
      assetId: previewId,
      label: "Low-Res Preview",
      stage: "preview",
      cameraStateVersion: selected?.lineage?.previewStateVersion ?? selected?.cameraStateVersion ?? null,
      fromPreview: true,
    });
  }

  const shot = input.shot;
  const approved = shot?.candidates.find((c) => c.id === shot.approved_candidate_id);
  if (approved?.asset_id) {
    const draft = (approved.quality_profile || "").toLowerCase() === "draft" || approved.kind === "region_edit";
    add({
      id: `approved:${approved.id}`,
      assetId: approved.asset_id,
      label: approved.kind === "region_edit" ? `Approved ${approved.take_label || "Edit"}` : "Approved Preview",
      stage: draft ? "preview" : "final",
      cameraStateVersion: approved.camera_state_version ?? null,
      parentCandidateId: approved.id,
    });
  }

  for (const cand of shot?.candidates || []) {
    if (!cand.asset_id) continue;
    const draft = (cand.quality_profile || "").toLowerCase() === "draft";
    add({
      id: `take:${cand.id}`,
      assetId: cand.asset_id,
      label: cand.take_label || `Take ${cand.index + 1}`,
      stage: draft || cand.kind === "region_edit" ? inferRegionEditStage({ sourceAssetId: cand.asset_id, fromPreview: draft }, cand) : "final",
      cameraStateVersion: cand.camera_state_version ?? null,
      parentCandidateId: cand.id,
    });
  }
  return out;
}

export function countApprovedRegionEdits(shot: SceneShot | null): number {
  if (!shot) return 0;
  const edits = ((shot.take_memory?.userCorrection?.region_edits as Array<Record<string, unknown>>) || []).filter(
    (edit) => edit.approved || edit.candidate_id === shot.approved_candidate_id,
  );
  const approvedKind = shot.candidates.filter((c) => c.kind === "region_edit" && c.id === shot.approved_candidate_id);
  return Math.max(edits.length, approvedKind.length);
}

export function formatInpaintCollapsedSummary(shot: SceneShot | null, hasMask: boolean): string {
  const approved = countApprovedRegionEdits(shot);
  if (approved === 1) return "1 approved edit";
  if (approved > 1) return `${approved} approved edits`;
  const latest = [...(shot?.candidates || [])].reverse().find((c) => c.kind === "region_edit");
  if (latest?.status === "complete") return `${latest.take_label || "Inpaint"} — Ready`;
  if (latest?.status === "queued" || latest?.status === "generating") return "Generating…";
  if (hasMask) return "Mask Ready";
  return "";
}

export function resolveRegionEditSource(input: {
  shot: SceneShot | null;
  cinematographer?: SceneCinematographerPack | null;
  selectedCameraId?: string;
}): RegionEditSource | null {
  const shot = input.shot;
  const approved = shot?.candidates.find((c) => c.id === shot.approved_candidate_id);
  if (approved?.asset_id) {
    return {
      sourceAssetId: approved.asset_id,
      parentCandidateId: approved.id,
      cameraStateVersion: approved.camera_state_version ?? null,
    };
  }

  const cameras = input.cinematographer?.cameras || [];
  const selected =
    cameras.find((c) => c.cameraId === input.selectedCameraId) ||
    cameras.find((c) => c.lineage?.locked) ||
    cameras.find((c) => c.lineage?.previewStatus === "ready");
  const previewId = selected?.lineage?.previewAssetId || "";
  const previewReady = selected?.lineage?.previewStatus === "ready" || Boolean(selected?.lineage?.locked);
  if (previewId && previewReady) {
    const parent = (shot?.candidates || []).find((c) => c.asset_id === previewId);
    return {
      sourceAssetId: previewId,
      parentCandidateId: parent?.id,
      cameraStateVersion: selected?.lineage?.previewStateVersion ?? selected?.cameraStateVersion ?? null,
      fromPreview: true,
    };
  }

  const latest = [...(shot?.candidates || [])].reverse().find((c) => c.asset_id);
  if (latest?.asset_id) {
    return {
      sourceAssetId: latest.asset_id,
      parentCandidateId: latest.id,
      cameraStateVersion: latest.camera_state_version ?? null,
    };
  }
  return null;
}

export function isMaskStale(input: {
  maskSourceAssetId: string;
  currentSourceAssetId: string;
  maskCameraVersion?: number | null;
  currentCameraVersion?: number | null;
}): boolean {
  if (!input.maskSourceAssetId || !input.currentSourceAssetId) return false;
  if (input.maskSourceAssetId !== input.currentSourceAssetId) return true;
  if (
    input.maskCameraVersion != null &&
    input.currentCameraVersion != null &&
    input.maskCameraVersion !== input.currentCameraVersion
  ) {
    return true;
  }
  return false;
}

export function shotWithSelectedFamily(
  shot: SceneShot | null | undefined,
  family: string,
): SceneShot | null {
  if (!shot) return null;
  const live = (family || shot.generator?.local_family || "").trim();
  if (!live || live === shot.generator?.local_family) return shot;
  return { ...shot, generator: { ...shot.generator, local_family: live } };
}

export function compileRegionEditFinalPrompt(
  shot: Pick<SceneShot, "prompt" | "intent" | "approved_candidate_id" | "candidates" | "take_memory" | "generator">,
  basePrompt = "",
): { prompt: string; sourceAssetId?: string; strategy: "A" | "B" | "C"; visualInheritanceBlocked?: boolean } {
  const edits = ((shot.take_memory?.userCorrection?.region_edits as Array<Record<string, unknown>>) || []).filter(
    (e) => e.approved || e.candidate_id === shot.approved_candidate_id,
  );
  const clauses: string[] = [];
  for (const edit of edits) {
    const op = String(edit.operation || "");
    const text = String(edit.prompt || "").trim();
    if (op === "remove") {
      clauses.push(text ? `Do not include the removed extra. ${text}` : "Do not include the removed extra.");
    } else if (op === "replace") {
      clauses.push(`Replace the marked region: ${text}`);
    } else if (op === "add") {
      clauses.push(`Add in the marked region: ${text}`);
    } else if (op === "modify") {
      clauses.push(`Modify the marked region: ${text}`);
    }
  }
  const prompt = `${basePrompt || shot.prompt || shot.intent || ""} ${clauses.join(" ")}`.trim();
  const approved = shot.candidates.find((c) => c.id === shot.approved_candidate_id);
  const family = shot.generator?.local_family || approved?.family || "";
  const caps = regionEditCapability(family);
  if (approved?.kind === "region_edit" && approved.asset_id && (caps.supportsEditing || caps.supportsInpaint)) {
    return { prompt, sourceAssetId: approved.asset_id, strategy: "A" };
  }
  if (approved?.kind === "region_edit" && approved.asset_id) {
    return { prompt, strategy: "C", visualInheritanceBlocked: true };
  }
  return { prompt, strategy: "B" };
}

export function inferRegionEditStage(source: RegionEditSource | null, parent?: SceneShotCandidate): "preview" | "final" {
  if (source?.fromPreview) return "preview";
  if ((parent?.quality_profile || "").toLowerCase() === "draft") return "preview";
  return "final";
}

export function approvedLookBlocksFinal(shot: SceneShot | null | undefined): boolean {
  if (!shot?.approved_candidate_id) return false;
  const cand = shot.candidates.find((c) => c.id === shot.approved_candidate_id);
  if (!cand) return false;
  const quality = (cand.quality_profile || "").toLowerCase();
  if (quality === "draft" || quality === "preview") return false;
  return true;
}

export function exportMaskPngFromEditor(root: HTMLElement | null): string {
  if (!root) return "";
  const canvases = root.querySelectorAll("canvas");
  const mask = canvases[1] as HTMLCanvasElement | undefined;
  if (!mask) return "";
  return mask.toDataURL("image/png").replace(/^data:image\/png;base64,/, "");
}
