import {
  coDirectorProjectPath,
  isStandaloneBibleWorkspace,
  resolveWorkspace,
} from "../core/workspaces";
import {
  SCENE_QUERY_KEY,
  buildCoDirectorSearch,
  buildTimelineSearch,
  isTimelineShellWorkspace,
  shouldPersistSelectedScene,
} from "../sceneSelection";

export type ProjectWorkspaceLocation = {
  pathname: string;
  search: string;
};

/** Express / Standard handoff scene: explicit extra wins, then the bound scene. */
export function resolveHandoffSceneId(
  extra?: Record<string, string>,
  currentSceneId?: string | null,
): string | undefined {
  const value = String(extra?.sceneId || extra?.scene || currentSceneId || "").trim();
  return value || undefined;
}

/**
 * Single Express → Standard workspace location authority.
 * Requires a project id. Never emits a project-less path.
 */
export function buildProjectWorkspaceLocation(args: {
  projectId: string | null | undefined;
  tab: string;
  sceneId?: string | null;
  extra?: Record<string, string>;
}): ProjectWorkspaceLocation | null {
  const projectId = String(args.projectId || "").trim();
  if (!projectId) return null;
  const resolved = resolveWorkspace(args.tab);
  if (!resolved) return null;
  const sceneId = resolveHandoffSceneId(args.extra, args.sceneId);
  if (isStandaloneBibleWorkspace(resolved)) {
    const search = buildCoDirectorSearch({ projectId, sceneId, workspace: resolved });
    const path = coDirectorProjectPath(projectId);
    const [pathname, pathSearch] = path.split("?");
    if (search) return { pathname, search };
    return { pathname, search: pathSearch ? `?${pathSearch}` : "" };
  }
  const extra = args.extra;
  const search = isTimelineShellWorkspace(resolved)
    ? buildTimelineSearch({
        workspace: resolved,
        sceneId,
        extra,
      })
    : (() => {
        const params = new URLSearchParams();
        if (resolved !== "home") params.set("workspace", resolved);
        if (extra) {
          for (const [key, value] of Object.entries(extra)) {
            if (!value || key === "sceneId" || key === "scene") continue;
            params.set(key, value);
          }
        }
        if (sceneId && shouldPersistSelectedScene(resolved)) {
          params.set(SCENE_QUERY_KEY, sceneId);
        }
        const next = params.toString();
        return next ? `?${next}` : "";
      })();
  return { pathname: `/project/${projectId}`, search };
}

/** Express launchers must not invent their own route strings. */
export function openExpressStandardWorkspace(
  onGoTab: ((tab: string, extra?: Record<string, string>) => void) | undefined,
  tab: string,
  sceneId?: string | null,
  extra?: Record<string, string>,
) {
  const scene = resolveHandoffSceneId(extra, sceneId);
  const nextExtra = extra ? { ...extra } : undefined;
  if (scene) {
    onGoTab?.(tab, { ...nextExtra, sceneId: scene });
    return;
  }
  onGoTab?.(tab, nextExtra);
}
