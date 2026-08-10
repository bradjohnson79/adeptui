/** Workspace persistence helpers for Adept UI Studio */
import {
  resolveWorkspace,
  type EditorTab,
} from "./core/workspaces";

export { ALL_TABS, resolveWorkspace, type EditorTab } from "./core/workspaces";

const KEY = "adept_ui_last_workspace";
const RECENT_KEY = "adept_ui_recent_projects";

/** Ops/setup chrome and the project landing page — never resume destinations. */
const NON_RESUME_WORKSPACES = new Set<EditorTab>(["setup", "home"]);

function asResumeWorkspace(tab: EditorTab | null | undefined): EditorTab | null {
  if (!tab) return null;
  if (NON_RESUME_WORKSPACES.has(tab)) return null;
  return tab;
}

/**
 * Workspace memory is PER PROJECT (lastWorkspaceByProject). A plain Open
 * Project never resumes silently — this store only feeds the intentional
 * "Continue" affordance on the project landing page. One project's memory
 * must never contaminate another's.
 */
function readMap(): Record<string, string> {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return {};
    const data = JSON.parse(raw);
    if (data && typeof data === "object") {
      // Legacy single-record shape: { projectId, tab } → migrate into the map.
      if (typeof data.projectId === "string" && typeof data.tab === "string") {
        return { [data.projectId]: data.tab };
      }
      return data as Record<string, string>;
    }
    return {};
  } catch {
    return {};
  }
}

export function loadLastWorkspace(projectId: string): EditorTab | null {
  const tab = readMap()[projectId];
  return asResumeWorkspace(resolveWorkspace(tab));
}

export function saveLastWorkspace(projectId: string, tab: EditorTab) {
  try {
    // Wave 4C: always persist canonical workspace id (director → timeline).
    const canonical = resolveWorkspace(tab) || tab;
    // Setup Wizard / project landing must not hijack the resume destination.
    if (NON_RESUME_WORKSPACES.has(canonical)) return;
    const map = readMap();
    map[projectId] = canonical;
    localStorage.setItem(KEY, JSON.stringify(map));
  } catch {
    /* ignore */
  }
}

export function pushRecentProject(id: string, name: string) {
  try {
    const raw = localStorage.getItem(RECENT_KEY);
    const list: { id: string; name: string }[] = raw ? JSON.parse(raw) : [];
    const next = [{ id, name }, ...list.filter((p) => p.id !== id)].slice(0, 12);
    localStorage.setItem(RECENT_KEY, JSON.stringify(next));
  } catch {
    /* ignore */
  }
}

export function loadRecentProjects(): { id: string; name: string }[] {
  try {
    const raw = localStorage.getItem(RECENT_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function replaceRecentProjects(projects: { id: string; name: string }[]) {
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(projects.slice(0, 12)));
  } catch {
    /* ignore */
  }
}

/**
 * Drop any project IDs from the per-project workspace map and the recent-projects
 * list that no longer exist on the server. Deleted projects must never remain
 * active navigation targets (e.g. after a creator-data reset or project deletion
 * on another device). Returns the number of stale entries removed.
 */
export function pruneDeletedProjects(validIds: Set<string>): number {
  let removed = 0;
  try {
    const map = readMap();
    const nextMap: Record<string, string> = {};
    for (const [pid, tab] of Object.entries(map)) {
      if (validIds.has(pid)) {
        nextMap[pid] = tab;
      } else {
        removed += 1;
      }
    }
    if (removed > 0) {
      localStorage.setItem(KEY, JSON.stringify(nextMap));
    }
  } catch {
    /* ignore */
  }
  try {
    const raw = localStorage.getItem(RECENT_KEY);
    if (raw) {
      const list: { id: string; name: string }[] = JSON.parse(raw);
      const nextList = list.filter((p) => {
        if (validIds.has(p.id)) return true;
        removed += 1;
        return false;
      });
      if (nextList.length !== list.length) {
        localStorage.setItem(RECENT_KEY, JSON.stringify(nextList));
      }
    }
  } catch {
    /* ignore */
  }
  return removed;
}

export const ASPECT_PRESETS = [
  "1:1",
  "4:3",
  "3:2",
  "16:10",
  "16:9",
  "18:9",
  "21:9",
  "9:16",
  "2.39:1",
  "custom",
] as const;

export type AspectPreset = (typeof ASPECT_PRESETS)[number];

export const FPS_OPTIONS = ["auto", 12, 16, 18, 24, 25, 30, 48, 50, 60] as const;

export const STYLE_PRESETS = [
  "Cinematic",
  "Anime",
  "Photorealistic",
  "Documentary",
  "Fantasy",
  "Sci-Fi",
  "Horror",
] as const;

export const IMAGE_STYLE_PRESETS = [
  "Photorealistic",
  "Cinematic",
  "Anime",
  "Oil Painting",
  "Comic",
  "Concept Art",
  "Storyboard",
  "Sketch",
  "Pixar",
  "Clay Render",
] as const;

export function aspectCssValue(aspect?: string | null): string {
  if (!aspect || aspect === "custom") return "16 / 9";
  if (aspect === "2.39:1") return "2.39 / 1";
  return aspect.replace(":", " / ");
}

export function sizeFromAspect(
  aspect: string,
  baseLong = 1280
): { width: number; height: number } {
  const map: Record<string, [number, number]> = {
    "1:1": [1, 1],
    "4:3": [4, 3],
    "3:2": [3, 2],
    "16:10": [16, 10],
    "16:9": [16, 9],
    "18:9": [18, 9],
    "21:9": [21, 9],
    "9:16": [9, 16],
    "2.39:1": [239, 100],
  };
  const [a, b] = map[aspect] || [16, 9];
  if (a >= b) {
    const width = baseLong;
    const height = Math.round((baseLong * b) / a / 8) * 8;
    return { width, height: Math.max(64, height) };
  }
  const height = baseLong;
  const width = Math.round((baseLong * a) / b / 8) * 8;
  return { width: Math.max(64, width), height };
}

export function resolutionToSize(label: string, aspect = "16:9"): { width: number; height: number } {
  const long =
    label === "4K" ? 3840 : label === "1440p" ? 2560 : label === "1080p" ? 1920 : label === "720p" ? 1280 : 1280;
  return sizeFromAspect(aspect, long);
}
