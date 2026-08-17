/**
 * Co-Director Action Layer
 *
 * Guiding principle: anything manual in Adept UI should be reachable via Co-Director
 * when expressible as an action. Pause only for visual precision, low confidence,
 * destructive ops, costly renders, or restricted permissions.
 *
 * Master Sheet = what exists; Spatial = where; Storyboard = how framed;
 * Director = Prompt Timeline (creates shots); Editor = assembles the film.
 */

export type PermissionLevel = "read" | "suggest" | "prepare" | "execute";
export type PermissionPolicy = "always_allow" | "ask_once" | "always_ask" | "never";

export type ActionCategory =
  | "navigate"
  | "search"
  | "project"
  | "scene"
  | "generate"
  | "library"
  | "spatial"
  | "mastersheet"
  | "avatar"
  | "director"
  | "timeline"
  | "editor"
  | "destructive"
  | "model_download"
  | "memory";

export type CostHint = "free" | "light" | "render" | "download";

export type ActionDef = {
  id: string;
  label: string;
  description: string;
  category: ActionCategory;
  permission: PermissionLevel;
  reversible: boolean;
  cost: CostHint;
  /** Input schema keys (lightweight; validated at execute time) */
  inputs: string[];
};

export type PlannedStep = {
  id: string;
  actionId: string;
  label: string;
  inputs: Record<string, unknown>;
  status: "pending" | "running" | "done" | "failed" | "skipped" | "checkpoint";
  checkpointMessage?: string;
  error?: string;
  result?: unknown;
  /** Reuse candidates from asset-first search */
  reuseAssets?: { id: string; tag: string; kind: string }[];
};

/**
 * CDX-088 (Phase 7): ActionPlan is a LEGACY type only — the frontend plan state
 * (CoDirectorSession `plan`) is permanently null in the live flow and no code
 * path may set it to a non-null ActionPlan. Backend intelligence plans
 * (intelligence_plan SSE / production_plan.* tools) are the only authoritative
 * plan surface. planFromIntention / RECIPE_STUBS were removed in Phase 7.
 */
export type ActionPlan = {
  id: string;
  title: string;
  intention: string;
  steps: PlannedStep[];
  createdAt: string;
  pausedAt?: string;
};

export type AuditEntry = {
  id: string;
  at: string;
  actionId: string;
  label: string;
  ok: boolean;
  undoGroup?: string;
  detail?: string;
};

export const ACTION_REGISTRY: ActionDef[] = [
  {
    id: "createProject",
    label: "Create project",
    description: "Create a new production",
    category: "project",
    permission: "execute",
    reversible: false,
    cost: "free",
    inputs: ["name"],
  },
  {
    id: "openProject",
    label: "Open project",
    description: "Navigate to a project",
    category: "navigate",
    permission: "read",
    reversible: true,
    cost: "free",
    inputs: ["projectId"],
  },
  {
    id: "updateProjectSettings",
    label: "Update project settings",
    description: "Patch project fields",
    category: "project",
    permission: "execute",
    reversible: true,
    cost: "free",
    inputs: ["projectId", "patch"],
  },
  {
    id: "duplicateProject",
    label: "Duplicate project",
    description: "Clone a project",
    category: "project",
    permission: "execute",
    reversible: false,
    cost: "light",
    inputs: ["projectId"],
  },
  {
    id: "archiveProject",
    label: "Archive project",
    description: "Hide project from library",
    category: "destructive",
    permission: "execute",
    reversible: true,
    cost: "free",
    inputs: ["projectId"],
  },
  {
    id: "createScene",
    label: "Create scene",
    description: "Add a scene to the project",
    category: "scene",
    permission: "execute",
    reversible: true,
    cost: "free",
    inputs: ["projectId", "name"],
  },
  {
    id: "updateScene",
    label: "Update scene",
    description: "Patch scene fields",
    category: "scene",
    permission: "execute",
    reversible: true,
    cost: "free",
    inputs: ["projectId", "sceneId", "patch"],
  },
  {
    id: "goToWorkspace",
    label: "Go to workspace",
    description: "Switch editor tab",
    category: "navigate",
    permission: "read",
    reversible: true,
    cost: "free",
    inputs: ["tab"],
  },
  {
    id: "searchLibrary",
    label: "Search library",
    description: "List/search project assets",
    category: "search",
    permission: "read",
    reversible: true,
    cost: "free",
    inputs: ["projectId", "q"],
  },
  {
    id: "resolveLibraryLocation",
    label: "Resolve library location",
    description: "Resolve NL or path (e.g. Audio/Music) to canonical folder",
    category: "library",
    permission: "read",
    reversible: true,
    cost: "free",
    inputs: ["projectId", "query", "path", "systemKey"],
  },
  {
    id: "planLibraryStorage",
    label: "Plan library storage",
    description: "Preflight canonical storage location before generation",
    category: "library",
    permission: "prepare",
    reversible: true,
    cost: "free",
    inputs: ["projectId", "task", "path", "systemKey", "entityType", "entityName"],
  },
  {
    id: "queueImageGeneration",
    label: "Queue ImageGen",
    description: "Start an image generation job",
    category: "generate",
    permission: "execute",
    reversible: false,
    cost: "render",
    inputs: ["projectId", "prompt"],
  },
  {
    id: "queueVideoGeneration",
    label: "Queue Txt2Vid",
    description: "Start a text-to-video job",
    category: "generate",
    permission: "execute",
    reversible: false,
    cost: "render",
    inputs: ["projectId", "prompt"],
  },
  {
    id: "createSpatialFromMasterSheet",
    label: "Create Spatial from Master Sheet",
    description: "Translate master sheet ingredients into a spatial map stub",
    category: "spatial",
    permission: "prepare",
    reversible: true,
    cost: "light",
    inputs: ["projectId", "sceneId"],
  },
  {
    id: "syncSpatialToMasterSheet",
    label: "Sync Spatial → Master Sheet",
    description: "Pull spatial positions into master sheet (needs review)",
    category: "spatial",
    permission: "suggest",
    reversible: true,
    cost: "light",
    inputs: ["projectId", "sceneId"],
  },
  {
    id: "createMasterSheetFromScene",
    label: "Create Master Sheet from Scene",
    description: "Bootstrap a Whole-Scene Package from scene context",
    category: "mastersheet",
    permission: "execute",
    reversible: true,
    cost: "free",
    inputs: ["projectId", "sceneId"],
  },
  {
    id: "updateIngredient",
    label: "Update ingredient",
    description: "Patch a master sheet ingredient",
    category: "mastersheet",
    permission: "execute",
    reversible: true,
    cost: "free",
    inputs: ["projectId", "sceneId", "ingredientId", "patch"],
  },
  {
    id: "renderIngredientsSheet",
    label: "Render ingredients board",
    description: "Preview model-readable ingredients layout (not a collage prompt)",
    category: "mastersheet",
    permission: "prepare",
    reversible: true,
    cost: "light",
    inputs: ["projectId", "sceneId"],
  },
  {
    id: "validateMasterSheet",
    label: "Validate Master Sheet",
    description: "Run basic completeness checks",
    category: "mastersheet",
    permission: "read",
    reversible: true,
    cost: "free",
    inputs: ["projectId", "sceneId"],
  },
  {
    id: "setSceneAuthority",
    label: "Set Scene Authority",
    description: "Mark approved_authority on the master sheet",
    category: "mastersheet",
    permission: "execute",
    reversible: true,
    cost: "free",
    inputs: ["projectId", "sceneId", "approved"],
  },
  {
    id: "createAvatarSession",
    label: "Create Avatar Session",
    description: "Start an Avatar Studio session from a character profile",
    category: "avatar",
    permission: "execute",
    reversible: true,
    cost: "free",
    inputs: ["projectId", "name", "character_profile_id", "character_name", "mode"],
  },
  {
    id: "setAvatarLook",
    label: "Set Avatar Look",
    description: "Patch look / framing on an avatar session",
    category: "avatar",
    permission: "execute",
    reversible: true,
    cost: "free",
    inputs: ["projectId", "sessionId", "look"],
  },
  {
    id: "attachAvatarAudio",
    label: "Attach Avatar Audio",
    description: "Bind dialogue audio to the session voice",
    category: "avatar",
    permission: "execute",
    reversible: true,
    cost: "free",
    inputs: ["projectId", "sessionId", "audio_asset_id"],
  },
  {
    id: "prepareAvatarLipSync",
    label: "Prepare Avatar Lip Sync",
    description: "Open lip-sync flow; pause for mouth mask",
    category: "avatar",
    permission: "prepare",
    reversible: true,
    cost: "light",
    inputs: ["projectId", "sessionId"],
  },
  {
    id: "queueAvatarGeneration",
    label: "Queue Avatar Generation",
    description: "Queue still/video for avatar session",
    category: "avatar",
    permission: "execute",
    reversible: false,
    cost: "render",
    inputs: ["projectId", "sessionId", "prompt"],
  },
  {
    id: "approveAvatarTake",
    label: "Approve Avatar Take",
    description: "Mark a take approved",
    category: "avatar",
    permission: "execute",
    reversible: true,
    cost: "free",
    inputs: ["projectId", "sessionId", "label"],
  },
  {
    id: "sendAvatarToDirector",
    label: "Send Avatar to Timeline",
    description: "Promote approved take to a Director scene",
    category: "avatar",
    permission: "execute",
    reversible: false,
    cost: "light",
    inputs: ["projectId", "sessionId", "asset_id"],
  },
  {
    id: "createDirectorSequence",
    label: "Create Timeline Sequence",
    description: "Snapshot scene Prompt Timeline into a Timeline Sequence package",
    category: "director",
    permission: "execute",
    reversible: true,
    cost: "light",
    inputs: ["projectId", "sceneId", "name"],
  },
  {
    id: "sendDirectorToEditor",
    label: "Send Timeline to Editor",
    description: "Create Editor clip linked to an approved Timeline Sequence",
    category: "director",
    permission: "execute",
    reversible: false,
    cost: "light",
    inputs: ["projectId", "sequenceId", "include_audio"],
  },
  {
    id: "compileDirectorPrompt",
    label: "Compile Timeline Prompt",
    description: "Compile model-ready prompt package for Director generation",
    category: "director",
    permission: "prepare",
    reversible: true,
    cost: "light",
    inputs: ["intention", "modelId", "mode", "projectId", "sceneId"],
  },
  {
    id: "importDirectorSequence",
    label: "Import Timeline Sequence",
    description: "Add an approved Timeline Sequence onto Editor Video 1",
    category: "editor",
    permission: "execute",
    reversible: true,
    cost: "light",
    inputs: ["projectId", "sequenceId"],
  },
  {
    id: "assembleSceneFromApproved",
    label: "Assemble Scene from Approved",
    description: "Open Editor and stitch approved Director outputs for a scene",
    category: "editor",
    permission: "prepare",
    reversible: true,
    cost: "light",
    inputs: ["projectId", "sceneId"],
  },
  {
    id: "openSourceInDirector",
    label: "Open Source in Timeline",
    description: "Navigate from Editor clip lineage back to Timeline Prompt",
    category: "editor",
    permission: "read",
    reversible: true,
    cost: "free",
    inputs: ["sceneId", "sequenceId"],
  },
  {
    id: "applyEditorialContextToDirector",
    label: "Apply Editorial Context",
    description: "Store replacement context (duration, neighbors) for Director regenerate",
    category: "editor",
    permission: "prepare",
    reversible: true,
    cost: "free",
    inputs: ["needed_duration_sec", "prev_clip_label", "next_clip_label", "sceneId"],
  },
  {
    id: "translateToSpatial",
    label: "Translate to Spatial",
    description: "Alias for createSpatialFromMasterSheet",
    category: "spatial",
    permission: "prepare",
    reversible: true,
    cost: "light",
    inputs: ["projectId", "sceneId"],
  },
  {
    id: "compilePrompt",
    label: "Compile prompt package",
    description: "Build model-specific generation package from intention + KB",
    category: "generate",
    permission: "prepare",
    reversible: true,
    cost: "light",
    inputs: ["intention", "modelId", "mode"],
  },
  {
    id: "saveMemorySuggestion",
    label: "Save memory suggestion",
    description: "Stub — promote learning when API exists",
    category: "memory",
    permission: "suggest",
    reversible: true,
    cost: "free",
    inputs: ["projectId", "text"],
  },
  {
    id: "manualCheckpoint",
    label: "Manual checkpoint",
    description: "Pause plan for user visual/precision work",
    category: "navigate",
    permission: "read",
    reversible: true,
    cost: "free",
    inputs: ["message"],
  },
];

export function getAction(id: string): ActionDef | undefined {
  return ACTION_REGISTRY.find((a) => a.id === id);
}

/** Default policies by category */
export const DEFAULT_POLICIES: Record<ActionCategory, PermissionPolicy> = {
  navigate: "always_allow",
  search: "always_allow",
  project: "ask_once",
  scene: "ask_once",
  generate: "always_ask",
  library: "always_allow",
  spatial: "ask_once",
  mastersheet: "ask_once",
  avatar: "ask_once",
  director: "ask_once",
  timeline: "ask_once",
  editor: "ask_once",
  destructive: "always_ask",
  model_download: "always_ask",
  memory: "ask_once",
};

const POLICY_KEY = "adept_codirector_policies";
const ASKED_KEY = "adept_codirector_asked";
const AUDIT_KEY = "adept_codirector_audit";

export function loadPolicies(): Record<ActionCategory, PermissionPolicy> {
  try {
    const raw = localStorage.getItem(POLICY_KEY);
    if (!raw) return { ...DEFAULT_POLICIES };
    return { ...DEFAULT_POLICIES, ...JSON.parse(raw) };
  } catch {
    return { ...DEFAULT_POLICIES };
  }
}

export function savePolicies(p: Record<ActionCategory, PermissionPolicy>) {
  localStorage.setItem(POLICY_KEY, JSON.stringify(p));
}

export function loadAskedOnce(): Record<string, boolean> {
  try {
    return JSON.parse(localStorage.getItem(ASKED_KEY) || "{}");
  } catch {
    return {};
  }
}

export function markAskedOnce(category: ActionCategory) {
  const m = loadAskedOnce();
  m[category] = true;
  localStorage.setItem(ASKED_KEY, JSON.stringify(m));
}

export function needsConfirmation(def: ActionDef): boolean {
  const policies = loadPolicies();
  const pol = policies[def.category] || "always_ask";
  if (pol === "always_allow") return false;
  if (pol === "never") return true; // treat as block → confirm UI will refuse
  if (pol === "always_ask") return true;
  // ask_once
  return !loadAskedOnce()[def.category];
}

export function appendAudit(entry: Omit<AuditEntry, "id" | "at">) {
  const list = loadAudit();
  list.unshift({
    ...entry,
    id: `aud-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    at: new Date().toISOString(),
  });
  localStorage.setItem(AUDIT_KEY, JSON.stringify(list.slice(0, 200)));
}

export function loadAudit(): AuditEntry[] {
  try {
    return JSON.parse(localStorage.getItem(AUDIT_KEY) || "[]");
  } catch {
    return [];
  }
}

/** Capability matrix per workspace — ✓ full, △ partial/checkpoint, ✗ not yet */
export type CapLevel = "ok" | "warn" | "bad";

export function workspaceCapabilities(tab: string): { label: string; level: CapLevel; note?: string }[] {
  const base = [
    { label: "Navigate", level: "ok" as CapLevel },
    { label: "Search assets", level: "ok" as CapLevel },
    { label: "Queue generate", level: "warn" as CapLevel, note: "Asks before render" },
  ];
  switch (tab) {
    case "home":
      return [...base, { label: "Dashboard", level: "ok" }, { label: "Master Sheet", level: "ok" }];
    case "spatial":
      return [
        ...base,
        { label: "Place cameras", level: "warn", note: "Precise drag may need checkpoint" },
        { label: "Sync Master Sheet", level: "warn", note: "Needs review" },
      ];
    case "director":
    case "timeline":
      return [
        ...base,
        { label: "Prompts / generate", level: "ok" },
        { label: "Prompt Timeline", level: "ok" },
        { label: "Send to Editor", level: "ok" },
        { label: "Lip sync tracks", level: "warn", note: "Mouth mask is manual" },
      ];
    case "editor":
      return [
        ...base,
        { label: "Assemble / import", level: "ok" },
        { label: "Timeline Sources", level: "ok" },
        { label: "Open in Timeline", level: "ok" },
        { label: "Audio mix / full NLE", level: "warn", note: "Stub this pass" },
      ];
    case "audiostudio":
      return [
        ...base,
        { label: "List / upload audio", level: "ok" },
        { label: "Add to Editor tracks", level: "ok" },
        { label: "Foley / music gen", level: "bad", note: "Not yet" },
      ];
    case "one":
    case "three":
      return [...base, { label: "Frame modes", level: "ok" }];
    case "mastersheet":
      return [
        ...base,
        { label: "Ingredients", level: "ok" },
        { label: "Prompt compile", level: "ok" },
        { label: "Ingredients render", level: "warn", note: "Preview only this pass" },
      ];
    case "avatar":
      return [
        ...base,
        { label: "Create session", level: "ok" },
        { label: "Attach audio", level: "ok" },
        { label: "Generate still/video", level: "warn", note: "Asks before render" },
        { label: "Mouth mask", level: "warn", note: "Requires user confirmation" },
        { label: "Send to Timeline", level: "ok" },
// ---------------------------------------------------------------------------
      ];
    default:
      return [...base, { label: tab || "workspace", level: "warn", note: "Partial coverage" }];
  }
}

// ---------------------------------------------------------------------------
// CDX-088 (Phase 7): legacy browser-side plan builder REMOVED.
// planFromIntention / RECIPE_STUBS / RecipeStub / step() were the dormant
// bypass that could construct a non-null ActionPlan (frontend plan/execute
// engine). The live flow never uses them — backend intelligence plans
// (intelligence_plan SSE / production_plan.* tools) are authoritative and
// CoDirectorSession.plan is permanently null. tests (legacyPlanGate.test.ts)
// assert no code path can set plan != null.
// ---------------------------------------------------------------------------
