import type { BatchBlock, CandidateVersion } from "./contracts";

/** Latest generated candidate with an assetId (createdAt ascending → last wins). */
export function latestGeneratedCandidate(batch: BatchBlock | null | undefined): CandidateVersion | null {
  if (!batch) return null;
  const latest = [...(batch.candidateVersions || [])]
    .filter((candidate) => Boolean(String(candidate.assetId || "").trim()))
    .sort((a, b) => String(a.createdAt || "").localeCompare(String(b.createdAt || "")))
    .at(-1);
  return latest || null;
}

/** Playable current take for Re-Take — GENERATED candidate, not Approved-only. */
export function hasGeneratedTakeForRetake(batch: BatchBlock | null | undefined): boolean {
  return Boolean(String(latestGeneratedCandidate(batch)?.assetId || "").trim());
}

export function resolveRetakeSource(batch: BatchBlock | null | undefined): {
  currentTakeId?: string;
  assetId: string | null;
} {
  const candidate = latestGeneratedCandidate(batch);
  const assetId = String(candidate?.assetId || "").trim() || null;
  if (!assetId || !candidate) return { assetId: null };
  const takeId = String(candidate.takeId || candidate.id || "").trim();
  return {
    assetId,
    ...(takeId ? { currentTakeId: takeId } : {}),
  };
}

/** Accurate empty copy — never "Approve a take first". */
export function retakeEmptyCopy(hasTake: boolean, hasValidRange: boolean): string {
  if (!hasTake) {
    return "Generate a take first. Re-Take replaces a marked part of the current take.";
  }
  if (!hasValidRange) {
    return "Mark In and Mark Out on the current take first.";
  }
  return "";
}
