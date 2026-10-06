/** Shared Character Sheet destinations — Library + Image Generator. */

export type GoTab = (tab: string, extra?: Record<string, string>) => void;

export function seedImageGeneratorFromSheet(assetId: string) {
  const id = String(assetId || "").trim();
  if (!id) return;
  try {
    sessionStorage.setItem("adept_cis_seed", JSON.stringify({ assetId: id }));
  } catch {
    /* ignore quota / private mode */
  }
}

export function openCharacterSheetInLibrary(onGoTab: GoTab | undefined, assetId: string) {
  const id = String(assetId || "").trim();
  if (!id) return;
  onGoTab?.("library", { assetId: id });
}

export function openCharacterSheetInImageGenerator(
  onGoTab: GoTab | undefined,
  args: { characterId: string; assetId: string },
) {
  const assetId = String(args.assetId || "").trim();
  const characterId = String(args.characterId || "").trim();
  if (!assetId) return;
  seedImageGeneratorFromSheet(assetId);
  onGoTab?.("imagegen", {
    ...(characterId ? { characterId } : {}),
    assetId,
  });
}
