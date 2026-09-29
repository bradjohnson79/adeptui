/** Canonical whole-scene Take letters: A…Z then Z1, Z2… Never AA/AB. */

export function sceneTakeLetter(index: number): string {
  if (!Number.isInteger(index) || index < 1) {
    throw new Error("take index must be >= 1");
  }
  if (index <= 26) return String.fromCharCode(64 + index);
  return `Z${index - 26}`;
}

/** A take is listed only after a generation has finished, or while one is rendering. */
export function sceneTakeIsListed(take: {
  status?: string | null;
  resultAssetId?: string | null;
  publishedAssetId?: string | null;
  batches?: Array<{ assetId?: string | null }> | null;
} | null | undefined): boolean {
  if (!take) return false;
  if (take.status === "rendering") return true;
  if (String(take.resultAssetId || "").trim()) return true;
  if (String(take.publishedAssetId || "").trim()) return true;
  return (take.batches || []).some((member) => Boolean(String(member.assetId || "").trim()));
}

export function sceneTakeDisplayLabel(label?: string | null): string {
  const text = String(label || "").trim();
  if (!text) return "Take";
  return text.toLowerCase().startsWith("take ") ? text : `Take ${text}`;
}
