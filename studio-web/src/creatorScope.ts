/** Shared Global asset-scope contract for Character / Prop / Environment. */

export const PROFILE_NAME_ALREADY_EXISTS = "PROFILE_NAME_ALREADY_EXISTS";

export const ENVIRONMENT_NAME_ALREADY_EXISTS_MESSAGE =
  "An environment with this name already exists in this project. Open the existing one or choose a different name.";

/** Comparison key only. Keep the creator's capitalization on screen. */
export function normalizeProfileName(name: string | null | undefined): string {
  return String(name || "")
    .trim()
    .split(/\s+/)
    .join(" ")
    .toLowerCase();
}

export const CREATOR_SCOPE_HELP =
  "Global assets are available in every project. If Global is off, this asset is available only in the project where it was created.";

export function readIsGlobal(payload: unknown): boolean {
  if (!payload || typeof payload !== "object") return false;
  const row = payload as Record<string, unknown>;
  if (row.isGlobal != null) return Boolean(row.isGlobal);
  if (row.is_global != null) return Boolean(row.is_global);
  return false;
}

export function owningProjectId(payload: unknown): string {
  if (!payload || typeof payload !== "object") return "";
  const row = payload as Record<string, unknown>;
  return String(row.owningProjectId || row.owning_project_id || row.project_id || row.projectId || "").trim();
}

export function entityId(payload: unknown): string {
  if (!payload || typeof payload !== "object") return "";
  const row = payload as Record<string, unknown>;
  return String(row.id || row.sheetId || row.characterId || row.propId || "").trim();
}

export function findVisibleNameCollision<T>(
  items: T[],
  name: string,
  excludeId = "",
  getName: (item: T) => string = (item) => {
    if (!item || typeof item !== "object") return "";
    const row = item as Record<string, unknown>;
    return String(row.display_label || row.name || row.tag || "");
  },
): T | undefined {
  const key = normalizeProfileName(name);
  if (!key) return undefined;
  const skip = String(excludeId || "").trim();
  return items.find((item) => {
    const id = entityId(item);
    if (skip && id === skip) return false;
    return normalizeProfileName(getName(item)) === key;
  });
}

export function groupScopeItems<T>(
  items: T[],
  projectId: string,
  ownerOf: (item: T) => string = (item) => owningProjectId(item),
): { project: T[]; global: T[] } {
  const pid = String(projectId || "").trim();
  const project: T[] = [];
  const global: T[] = [];
  const seen = new Set<string>();
  for (const item of items) {
    const id = entityId(item);
    if (id && seen.has(id)) continue;
    if (id) seen.add(id);
    const owner = ownerOf(item);
    if (owner === pid) project.push(item);
    else if (readIsGlobal(item)) global.push(item);
  }
  return { project, global };
}

export function scopeLabel(name: string, payload: unknown, currentProjectId: string): string {
  const owner = owningProjectId(payload);
  if (readIsGlobal(payload) && owner && owner !== currentProjectId) {
    return `${name}  Global`;
  }
  return name;
}

export function characterOwnedByProject(payload: unknown, projectId: string): boolean {
  const owner = owningProjectId(payload);
  const pid = String(projectId || "").trim();
  if (!owner || !pid) return true;
  return owner === pid;
}

/** First project-owned character. Never auto-selects a foreign Global. */
export function pickOwnedCharacterId<T>(
  items: T[],
  projectId: string,
  currentId = "",
): string {
  const pid = String(projectId || "").trim();
  const current = String(currentId || "").trim();
  const owned = items.filter((item) => characterOwnedByProject(item, pid));
  if (current && items.some((item) => entityId(item) === current)) return current;
  return entityId(owned[0]) || "";
}

/** ORDER 18 Owner law: Global props are available and editable from every project. Delete stays home-only. */
export const PROP_GLOBAL_SCOPE_HELP =
  "Global props are available in every project and can be edited from any project. Delete stays on the project that created them.";

/** True when this project may mutate the prop (save / generate / PRS). Global → any project; else home only. */
export function propEditableInProject(payload: unknown, projectId: string): boolean {
  if (readIsGlobal(payload)) return true;
  return characterOwnedByProject(payload, projectId);
}

/** Detect stale home-only *edit* OWNER_REQUIRED copy (not delete). */
export function isStalePropHomeOnlyEditMessage(message: string | null | undefined): boolean {
  const text = String(message || "").toLowerCase();
  if (!text) return false;
  if (text.includes("can only be deleted")) return false;
  return (
    text.includes("can only be edited from the project that created") ||
    text.includes("global props can only be edited")
  );
}
