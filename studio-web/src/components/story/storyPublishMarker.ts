/**
 * Persisted 'last published to Wiki' marker for Story entries (CDX-059).
 *
 * StoryEntryEditor's unpublished-changes indicator used to derive from an
 * in-memory snapshot that reset on reload, so any reload flipped a published
 * story back to 'unpublished changes'. The published snapshot is now persisted
 * locally, keyed by project id + story entry id, so reloads (and editor
 * remounts) restore the correct dirty state.
 *
 * The marker is a best-effort per-browser record of the exact Story values the
 * creator last published (Save to Wiki). It is only compared field-by-field
 * against the loaded Story entry; it never writes to the server.
 */

export type PublishedStorySnapshot = {
  title: string;
  logline: string;
  shortSummary: string;
  longSummary: string;
};

export type PublishedStorySnapshotMap = Record<string, PublishedStorySnapshot>;

export const STORY_PUBLISHED_KEY_PREFIX = "adept.story.lastPublished.v1";

export function storyPublishedStorageKey(projectId: string): string {
  return `${STORY_PUBLISHED_KEY_PREFIX}:${projectId}`;
}

type StorageLike = Pick<Storage, "getItem" | "setItem" | "removeItem">;

function browserStorage(): StorageLike | null {
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      return window.localStorage;
    }
  } catch {
    /* storage unavailable (SSR / privacy mode) — marker simply won't persist */
  }
  return null;
}

/**
 * Load the persisted published snapshot map for a project (empty map when
 * absent, corrupt, or when no storage is available).
 */
export function loadPublishedSnapshots(
  projectId: string,
  storage?: StorageLike | null,
): PublishedStorySnapshotMap {
  const store = storage ?? browserStorage();
  if (!store) return {};
  try {
    const raw = store.getItem(storyPublishedStorageKey(projectId));
    if (!raw) return {};
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    const out: PublishedStorySnapshotMap = {};
    for (const [key, value] of Object.entries(parsed as Record<string, unknown>)) {
      if (value && typeof value === "object" && !Array.isArray(value)) {
        const v = value as Record<string, unknown>;
        out[key] = {
          title: typeof v.title === "string" ? v.title : "",
          logline: typeof v.logline === "string" ? v.logline : "",
          shortSummary: typeof v.shortSummary === "string" ? v.shortSummary : "",
          longSummary: typeof v.longSummary === "string" ? v.longSummary : "",
        };
      }
    }
    return out;
  } catch {
    return {};
  }
}

/**
 * Persist the published snapshot map for a project. No-op when storage is
 * unavailable (quota / privacy mode) — dirty state degrades to in-memory only.
 */
export function persistPublishedSnapshots(
  projectId: string,
  snaps: PublishedStorySnapshotMap,
  storage?: StorageLike | null,
): void {
  const store = storage ?? browserStorage();
  if (!store) return;
  try {
    store.setItem(storyPublishedStorageKey(projectId), JSON.stringify(snaps));
  } catch {
    /* ignore quota / availability errors */
  }
}

/**
 * Remove the persisted snapshot map for a project (currently unused by the
 * editor; provided for completeness and tests).
 */
export function removePublishedSnapshots(
  projectId: string,
  storage?: StorageLike | null,
): void {
  const store = storage ?? browserStorage();
  if (!store) return;
  try {
    store.removeItem(storyPublishedStorageKey(projectId));
  } catch {
    /* ignore */
  }
}
