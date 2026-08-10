/**
 * Recent Production destinations — session-scoped jump list for the Production menu.
 */
import { WORKSPACES, type EditorTab } from "./workspaces";

const STORAGE_KEY = "adept_production_recent";
const MAX_RECENT = 6;

export type ProductionRecentItem = {
  tab: EditorTab;
  label: string;
  projectId?: string;
  projectName?: string;
  at: number;
};

function readAll(): ProductionRecentItem[] {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as ProductionRecentItem[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeAll(items: ProductionRecentItem[]) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(items.slice(0, MAX_RECENT)));
  } catch {
    /* ignore */
  }
}

export function pushProductionRecent(input: {
  tab: EditorTab;
  projectId?: string;
  projectName?: string;
  label?: string;
}): void {
  const label = input.label || WORKSPACES[input.tab]?.label || String(input.tab);
  const next: ProductionRecentItem = {
    tab: input.tab,
    label,
    projectId: input.projectId,
    projectName: input.projectName,
    at: Date.now(),
  };
  const rest = readAll().filter(
    (r) => !(r.tab === next.tab && (r.projectId || "") === (next.projectId || "")),
  );
  writeAll([next, ...rest]);
}

export function loadProductionRecent(projectId?: string): ProductionRecentItem[] {
  const all = readAll();
  if (!projectId) return all.slice(0, MAX_RECENT);
  // Prefer same-project entries, then fill with others
  const same = all.filter((r) => r.projectId === projectId);
  const other = all.filter((r) => r.projectId !== projectId);
  return [...same, ...other].slice(0, MAX_RECENT);
}
