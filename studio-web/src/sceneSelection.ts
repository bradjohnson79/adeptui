/**
 * Timeline selected-scene authority.
 *
 * Precedence for an explicit Timeline route:
 *   1. URL scene id (sceneId | scene_id | scene)
 *   2. persisted selected scene for this project + workspace
 *   3. current-session selection
 *   4. first valid scene (final fallback only)
 *
 * Browser storage holds only { projectId, workspace, sceneId }.
 * Director / database remains authoritative for Timeline contents.
 */
import { resolveWorkspace } from "./core/workspaces";

export const SELECTED_SCENE_STORAGE_KEY = "adept_ui_last_selected_scene";
export const SCENE_QUERY_KEY = "sceneId";
export const SCENE_QUERY_ALIASES = ["sceneId", "scene_id", "scene"] as const;

export type ResolveSelectedSceneInput = {
  sceneIds: readonly string[];
  urlSceneId?: string | null;
  persistedSceneId?: string | null;
  sessionSceneId?: string | null;
};

const NON_SCENE_WORKSPACES = new Set(["home", "setup"]);

export function persistWorkspaceKey(workspace: string | null | undefined): string {
  const resolved = resolveWorkspace(workspace) || String(workspace || "").trim();
  if (resolved === "one" || resolved === "three" || resolved === "timeline" || resolved === "director") {
    return "timeline";
  }
  return resolved;
}

export function shouldPersistSelectedScene(workspace: string | null | undefined): boolean {
  const resolved = resolveWorkspace(workspace) || String(workspace || "").trim();
  return Boolean(resolved) && !NON_SCENE_WORKSPACES.has(resolved);
}

export function isTimelineShellWorkspace(workspace: string | null | undefined): boolean {
  return persistWorkspaceKey(workspace) === "timeline";
}

export function parseSceneIdFromSearch(search: string | null | undefined): string | null {
  if (!search) return null;
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  for (const key of SCENE_QUERY_ALIASES) {
    const raw = (params.get(key) || "").trim();
    if (raw) return raw;
  }
  return null;
}

export function resolveSelectedScene(input: ResolveSelectedSceneInput): string | undefined {
  const valid = new Set(
    (input.sceneIds || []).map((id) => String(id || "").trim()).filter(Boolean),
  );
  if (valid.size === 0) return undefined;
  const pick = (id?: string | null): string | undefined => {
    const value = String(id || "").trim();
    return value && valid.has(value) ? value : undefined;
  };
  return (
    pick(input.urlSceneId) ||
    pick(input.persistedSceneId) ||
    pick(input.sessionSceneId) ||
    [...valid][0]
  );
}

type SceneStore = Record<string, Record<string, string>>;

function readStore(): SceneStore {
  try {
    const raw = localStorage.getItem(SELECTED_SCENE_STORAGE_KEY);
    if (!raw) return {};
    const data = JSON.parse(raw);
    if (!data || typeof data !== "object" || Array.isArray(data)) return {};
    const next: SceneStore = {};
    for (const [projectId, workspaces] of Object.entries(data as Record<string, unknown>)) {
      if (!projectId || !workspaces || typeof workspaces !== "object" || Array.isArray(workspaces)) continue;
      const row: Record<string, string> = {};
      for (const [workspace, sceneId] of Object.entries(workspaces as Record<string, unknown>)) {
        if (typeof sceneId === "string" && sceneId.trim()) row[workspace] = sceneId.trim();
      }
      if (Object.keys(row).length) next[projectId] = row;
    }
    return next;
  } catch {
    return {};
  }
}

function writeStore(store: SceneStore): void {
  localStorage.setItem(SELECTED_SCENE_STORAGE_KEY, JSON.stringify(store));
}

export function loadLastSelectedScene(
  projectId: string,
  workspace: string | null | undefined,
): string | null {
  const pid = String(projectId || "").trim();
  if (!pid) return null;
  const key = persistWorkspaceKey(workspace);
  if (!key) return null;
  return readStore()[pid]?.[key] || null;
}

export function saveLastSelectedScene(
  projectId: string,
  workspace: string | null | undefined,
  sceneId: string,
): void {
  try {
    if (!shouldPersistSelectedScene(workspace)) return;
    const pid = String(projectId || "").trim();
    const sid = String(sceneId || "").trim();
    const key = persistWorkspaceKey(workspace);
    if (!pid || !sid || !key) return;
    const store = readStore();
    store[pid] = { ...(store[pid] || {}), [key]: sid };
    writeStore(store);
  } catch {
    /* private mode / quota */
  }
}

export function clearLastSelectedScene(
  projectId: string,
  workspace: string | null | undefined,
): void {
  try {
    const pid = String(projectId || "").trim();
    const key = persistWorkspaceKey(workspace);
    if (!pid || !key) return;
    const store = readStore();
    if (!store[pid]?.[key]) return;
    delete store[pid][key];
    if (!Object.keys(store[pid]).length) delete store[pid];
    writeStore(store);
  } catch {
    /* ignore */
  }
}

export function pruneSelectedScenes(validProjectIds: Set<string>): number {
  try {
    const store = readStore();
    let removed = 0;
    const next: SceneStore = {};
    for (const [projectId, workspaces] of Object.entries(store)) {
      if (!validProjectIds.has(projectId)) {
        removed += Object.keys(workspaces).length;
        continue;
      }
      next[projectId] = workspaces;
    }
    if (removed > 0) writeStore(next);
    return removed;
  } catch {
    return 0;
  }
}

export function buildTimelineSearch(args: {
  workspace: string;
  sceneId?: string | null;
  extra?: Record<string, string>;
  currentSearch?: string | null;
}): string {
  const params = new URLSearchParams();
  // This builder writes the workspace it is given. resolveWorkspace folds
  // txt2vid / one / three onto timeline before a creator URL is built.
  const workspace = String(args.workspace || "").trim();
  if (workspace && workspace !== "home") params.set("workspace", workspace);
  const extra = args.extra || {};
  for (const [key, value] of Object.entries(extra)) {
    if (!value || SCENE_QUERY_ALIASES.includes(key as (typeof SCENE_QUERY_ALIASES)[number])) continue;
    params.set(key, value);
  }
  const sceneId = String(args.sceneId || parseSceneIdFromSearch(args.currentSearch) || "").trim();
  if (sceneId && isTimelineShellWorkspace(workspace)) {
    params.set(SCENE_QUERY_KEY, sceneId);
  }
  const search = params.toString();
  return search ? `?${search}` : "";
}

export function buildCoDirectorSearch(args: {
  projectId?: string | null;
  sceneId?: string | null;
  workspace?: string | null;
}): string {
  const params = new URLSearchParams();
  const projectId = String(args.projectId || "").trim();
  if (projectId) params.set("projectId", projectId);
  const workspace = persistWorkspaceKey(args.workspace);
  if (workspace && workspace !== "home") {
    params.set("workspace", workspace === "timeline" ? "timeline" : workspace);
  }
  const sceneId = String(args.sceneId || "").trim();
  if (sceneId) params.set("sceneId", sceneId);
  const search = params.toString();
  return search ? `?${search}` : "";
}
