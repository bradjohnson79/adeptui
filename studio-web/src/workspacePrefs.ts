/** Workspace persistence helpers for Adept UI Generation Studio */
import {
  resolveWorkspace,
  type EditorTab,
} from "./core/workspaces";

export { ALL_TABS, resolveWorkspace, type EditorTab } from "./core/workspaces";

const KEY = "adept_ui_last_workspace";
const RECENT_KEY = "adept_ui_recent_projects";

export function loadLastWorkspace(projectId: string): EditorTab | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const data = JSON.parse(raw) as { projectId?: string; tab?: string };
    if (data.projectId !== projectId) return null;
    return resolveWorkspace(data.tab);
  } catch {
    return null;
  }
}

export function saveLastWorkspace(projectId: string, tab: EditorTab) {
  try {
    localStorage.setItem(KEY, JSON.stringify({ projectId, tab }));
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
