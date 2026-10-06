/**
 * Scene card identity vs metadata.
 *
 * UUID is identity. Name is editable metadata.
 * Removal fallback follows canonical timeline order (next, else previous).
 */

export const SCENE_NAME_MAX = 200;

export function normalizeSceneName(
  raw: string,
): { ok: true; name: string } | { ok: false; reason: string } {
  const name = String(raw ?? "").trim();
  if (!name) return { ok: false, reason: "Enter a scene name." };
  if (name.length > SCENE_NAME_MAX) {
    return { ok: false, reason: `Scene names can be up to ${SCENE_NAME_MAX} characters.` };
  }
  return { ok: true, name };
}

/** Next scene in current ordering, otherwise previous. */
export function neighborSceneId(
  sceneIds: readonly string[],
  removedId: string,
): string | undefined {
  const ids = sceneIds.map((id) => String(id || "").trim()).filter(Boolean);
  const index = ids.indexOf(String(removedId || "").trim());
  if (index < 0) return ids[0];
  return ids[index + 1] || ids[index - 1] || undefined;
}

export function isSceneDeleteAlreadyGone(error: unknown): boolean {
  if (!error || typeof error !== "object") return false;
  const status = "status" in error ? Number((error as { status?: number }).status) : 0;
  const code = "code" in error ? String((error as { code?: string }).code || "") : "";
  return status === 404 || code === "SCENE_NOT_FOUND";
}
