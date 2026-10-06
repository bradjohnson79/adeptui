export function pickCanonicalVoiceRecord<
  T extends { characterId?: string; voiceIdentityId?: string; approvedTakeId?: string; updatedAt?: string },
>(
  records: T[],
  characterId: string,
  voiceIdentityId?: string | null,
  options?: { requireApprovedTake?: boolean },
): T | null {
  if (!voiceIdentityId) return null;
  const matching = records
    .filter((record) => {
      if (String(record.characterId || "") !== characterId) return false;
      if (record.voiceIdentityId !== voiceIdentityId) return false;
      if (options?.requireApprovedTake && !record.approvedTakeId) return false;
      return true;
    })
    .sort((left, right) => String(right.updatedAt || "").localeCompare(String(left.updatedAt || "")));
  return matching[0] || null;
}
