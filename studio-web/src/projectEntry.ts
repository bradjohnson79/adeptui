import { buildAiGuidedSetupPath, type SetupEntrySource } from "./setup/navigation";
import type { Project } from "./types";
import { loadRecentProjects, replaceRecentProjects } from "./workspacePrefs";

export type PendingProjectEntry =
  | {
      kind: "project";
      workspace?: string | null;
      tab?: string | null;
      returnTo?: string | null;
    }
  | {
      kind: "co-director";
      returnTo?: string | null;
    }
  | {
      kind: "setup";
      setupMode?: "ai_guided" | "guided" | "manual" | string | null;
      setupComponent?: string | null;
      setupSource?: SetupEntrySource | string | null;
      returnTo?: string | null;
    };

type BuildHomeCreateProjectPathArgs = {
  suggestedName?: string | null;
  pendingEntry?: PendingProjectEntry | null;
};

const PENDING_KIND_PARAM = "pendingKind";
const PENDING_WORKSPACE_PARAM = "pendingWorkspace";
const PENDING_TAB_PARAM = "pendingTab";
const PENDING_SETUP_MODE_PARAM = "pendingSetupMode";
const PENDING_SETUP_COMPONENT_PARAM = "pendingSetupComponent";
const PENDING_SETUP_SOURCE_PARAM = "pendingSetupSource";
const PENDING_RETURN_TO_PARAM = "pendingReturnTo";

function sanitizeReturnToPath(value?: string | null): string | null {
  if (!value || !value.startsWith("/") || value.startsWith("//")) {
    return null;
  }
  return value;
}

export function getEligibleProjectId(projects: Array<Pick<Project, "id" | "archived">>): string | null {
  const recentProjects = loadRecentProjects();
  // While Home is still loading, projects may be []. Do not treat that as
  // "every recent project is stale" or we wipe the creator's active context.
  if (!projects.length) {
    return recentProjects[0]?.id ?? null;
  }
  const eligibleProjects = projects.filter((project) => !project.archived);
  const eligibleIds = new Set(eligibleProjects.map((project) => project.id));
  const staleRecentProjects = recentProjects.filter((project) => !eligibleIds.has(project.id));
  if (staleRecentProjects.length) {
    replaceRecentProjects(recentProjects.filter((project) => eligibleIds.has(project.id)));
  }
  const recentEligibleProject = recentProjects.find((project) => eligibleIds.has(project.id));
  return recentEligibleProject?.id ?? eligibleProjects[0]?.id ?? null;
}

export function buildHomeCreateProjectPath({
  suggestedName,
  pendingEntry,
}: BuildHomeCreateProjectPathArgs = {}): string {
  const params = new URLSearchParams();
  params.set("create", "1");
  if (suggestedName) {
    params.set("createName", suggestedName);
  }
  if (pendingEntry) {
    params.set(PENDING_KIND_PARAM, pendingEntry.kind);
    if (pendingEntry.returnTo) {
      params.set(PENDING_RETURN_TO_PARAM, pendingEntry.returnTo);
    }
    if (pendingEntry.kind === "project") {
      if (pendingEntry.workspace) {
        params.set(PENDING_WORKSPACE_PARAM, pendingEntry.workspace);
      }
      if (pendingEntry.tab) {
        params.set(PENDING_TAB_PARAM, pendingEntry.tab);
      }
    } else if (pendingEntry.kind === "setup") {
      if (pendingEntry.setupMode) {
        params.set(PENDING_SETUP_MODE_PARAM, pendingEntry.setupMode);
      }
      if (pendingEntry.setupComponent) {
        params.set(PENDING_SETUP_COMPONENT_PARAM, pendingEntry.setupComponent);
      }
      if (pendingEntry.setupSource) {
        params.set(PENDING_SETUP_SOURCE_PARAM, pendingEntry.setupSource);
      }
    }
  }
  return `/?${params.toString()}`;
}

export function readPendingProjectEntry(params: URLSearchParams): PendingProjectEntry | null {
  const pendingKind = params.get(PENDING_KIND_PARAM);
  if (pendingKind === "project") {
    return {
      kind: "project",
      workspace: params.get(PENDING_WORKSPACE_PARAM),
      tab: params.get(PENDING_TAB_PARAM),
      returnTo: sanitizeReturnToPath(params.get(PENDING_RETURN_TO_PARAM)),
    };
  }
  if (pendingKind === "co-director") {
    return {
      kind: "co-director",
      returnTo: sanitizeReturnToPath(params.get(PENDING_RETURN_TO_PARAM)),
    };
  }
  if (pendingKind === "setup") {
    return {
      kind: "setup",
      setupMode: params.get(PENDING_SETUP_MODE_PARAM),
      setupComponent: params.get(PENDING_SETUP_COMPONENT_PARAM),
      setupSource: params.get(PENDING_SETUP_SOURCE_PARAM),
      returnTo: sanitizeReturnToPath(params.get(PENDING_RETURN_TO_PARAM)),
    };
  }
  return null;
}

export function buildSetupPendingEntry(params: URLSearchParams): PendingProjectEntry | null {
  const setupMode = params.get("setupMode");
  if (!setupMode) {
    return null;
  }
  return {
    kind: "setup",
    setupMode,
    setupComponent: params.get("setupComponent") || params.get("componentId"),
    setupSource: params.get("setupSource"),
    returnTo: sanitizeReturnToPath(params.get(PENDING_RETURN_TO_PARAM)),
  };
}

export function buildPendingProjectCancelDestination(pendingEntry?: PendingProjectEntry | null): string {
  const returnTo = sanitizeReturnToPath(pendingEntry?.returnTo);
  if (returnTo) {
    return returnTo;
  }
  return "/";
}

export function buildPendingProjectDestination(projectId: string, pendingEntry?: PendingProjectEntry | null): string {
  const encodedProjectId = encodeURIComponent(projectId);
  if (!pendingEntry) {
    return `/project/${encodedProjectId}`;
  }
  if (pendingEntry.kind === "co-director") {
    return `/co-director?projectId=${encodedProjectId}`;
  }
  if (pendingEntry.kind === "setup") {
    if (!pendingEntry.setupMode || pendingEntry.setupMode === "ai_guided") {
      return buildAiGuidedSetupPath({
        projectId,
        componentId: pendingEntry.setupComponent,
        source: pendingEntry.setupSource,
      });
    }
    const params = new URLSearchParams();
    params.set("workspace", "setup");
    params.set("setupMode", pendingEntry.setupMode);
    if (pendingEntry.setupComponent) {
      params.set("setupComponent", pendingEntry.setupComponent);
    }
    if (pendingEntry.setupSource) {
      params.set("setupSource", pendingEntry.setupSource);
    }
    return `/project/${encodedProjectId}?${params.toString()}`;
  }
  const params = new URLSearchParams();
  if (pendingEntry.workspace) {
    params.set("workspace", pendingEntry.workspace);
  }
  if (pendingEntry.tab) {
    params.set("tab", pendingEntry.tab);
  }
  const query = params.toString();
  return query ? `/project/${encodedProjectId}?${query}` : `/project/${encodedProjectId}`;
}
