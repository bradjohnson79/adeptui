export const VOICE_PORTRAIT_ROLE_PRIORITY = [
  "hero_identity",
  "hero_portrait",
  "neutral_portrait",
  "closeup_front",
  "full_body_front",
  "reference_image",
] as const;

export type VoicePortraitRef = {
  asset_id?: string | null;
  assetId?: string | null;
  reference_role?: string | null;
  canonical?: boolean | null;
  approval_status?: string | null;
};

function assetIdOf(item: VoicePortraitRef): string {
  return String(item.asset_id || item.assetId || "").trim();
}

function roleOf(item: VoicePortraitRef): string {
  return String(item.reference_role || "").trim();
}

/** Prefer canonical + approved hero, then any matching role, then a generic reference image. */
export function choosePortraitAssetId(refs: VoicePortraitRef[] | undefined): string | undefined {
  const list = Array.isArray(refs) ? refs.filter((item) => assetIdOf(item)) : [];
  if (!list.length) return undefined;
  const approvedHero = list.find(
    (item) =>
      (roleOf(item) === "hero_identity" || roleOf(item) === "hero_portrait") &&
      item.canonical === true &&
      String(item.approval_status || "").toLowerCase() === "approved",
  );
  if (approvedHero) return assetIdOf(approvedHero);
  for (const role of VOICE_PORTRAIT_ROLE_PRIORITY) {
    const match = list.find((item) => roleOf(item) === role);
    if (match) return assetIdOf(match);
  }
  return assetIdOf(list[0]);
}
