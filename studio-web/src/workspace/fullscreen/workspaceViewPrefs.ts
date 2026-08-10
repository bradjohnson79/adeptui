import type { WorkspaceId, WorkspaceViewMode, WorkspaceViewPreference, WorkspaceViewportMode } from "./types";

const STORAGE_KEY = "adept_workspace_view_prefs_v1";

const DEFAULTS: Record<WorkspaceId, WorkspaceViewPreference> = {
  timeline: { workspaceId: "timeline", lastViewMode: "STANDARD", panelSizes: {}, collapsedPanels: [] },
  codirector: { workspaceId: "codirector", lastViewMode: "STANDARD", panelSizes: {}, collapsedPanels: [] },
  magi: { workspaceId: "magi", lastViewMode: "STANDARD", panelSizes: {}, collapsedPanels: [] },
};

function readAll(): Record<WorkspaceId, WorkspaceViewPreference> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULTS };
    const parsed = JSON.parse(raw) as Partial<Record<WorkspaceId, WorkspaceViewPreference>>;
    return {
      timeline: { ...DEFAULTS.timeline, ...(parsed.timeline || {}) },
      codirector: { ...DEFAULTS.codirector, ...(parsed.codirector || {}) },
      magi: { ...DEFAULTS.magi, ...(parsed.magi || {}) },
    };
  } catch {
    return { ...DEFAULTS };
  }
}

function writeAll(all: Record<WorkspaceId, WorkspaceViewPreference>) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(all));
  } catch {
    /* ignore quota */
  }
}

export function loadWorkspaceViewPreference(workspaceId: WorkspaceId): WorkspaceViewPreference {
  return readAll()[workspaceId];
}

export function saveWorkspaceViewPreference(
  workspaceId: WorkspaceId,
  patch: Partial<Omit<WorkspaceViewPreference, "workspaceId">>,
): WorkspaceViewPreference {
  const all = readAll();
  const next = { ...all[workspaceId], ...patch, workspaceId };
  // Never persist FULLSCREEN as auto-restore target for browser FS (gesture required).
  if (next.lastViewMode === "FULLSCREEN") {
    next.lastViewMode = "EXPANDED";
  }
  all[workspaceId] = next;
  writeAll(all);
  return next;
}

export function rememberViewportMode(workspaceId: WorkspaceId, mode: WorkspaceViewportMode) {
  return saveWorkspaceViewPreference(workspaceId, { lastViewMode: mode });
}

export function rememberExpandedLayout(
  workspaceId: WorkspaceId,
  panelSizes: Record<string, number>,
  collapsedPanels: string[],
) {
  return saveWorkspaceViewPreference(workspaceId, {
    lastViewMode: "EXPANDED",
    panelSizes,
    collapsedPanels,
  });
}

export function viewportModeFromPreference(pref: WorkspaceViewPreference): WorkspaceViewportMode {
  return pref.lastViewMode === "EXPANDED" ? "EXPANDED" : "STANDARD";
}

export function asPersistedViewMode(mode: WorkspaceViewMode): WorkspaceViewMode {
  return mode === "FULLSCREEN" ? "EXPANDED" : mode;
}
