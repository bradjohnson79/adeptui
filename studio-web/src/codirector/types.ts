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
    label: "Send Avatar to Director",
    description: "Promote approved take to a Director scene",
    category: "avatar",
    permission: "execute",
    reversible: false,
    cost: "light",
    inputs: ["projectId", "sessionId", "asset_id"],
  },
  {
    id: "createDirectorSequence",
    label: "Create Director Sequence",
    description: "Snapshot scene Prompt Timeline into a Director Sequence package",
    category: "director",
    permission: "execute",
    reversible: true,
    cost: "light",
    inputs: ["projectId", "sceneId", "name"],
  },
  {
    id: "sendDirectorToEditor",
    label: "Send Director to Editor",
    description: "Create Editor clip linked to an approved Director Sequence",
    category: "director",
    permission: "execute",
    reversible: false,
    cost: "light",
    inputs: ["projectId", "sequenceId", "include_audio"],
  },
  {
    id: "compileDirectorPrompt",
    label: "Compile Director Prompt",
    description: "Compile model-ready prompt package for Director generation",
    category: "director",
    permission: "prepare",
    reversible: true,
    cost: "light",
    inputs: ["intention", "modelId", "mode", "projectId", "sceneId"],
  },
  {
    id: "importDirectorSequence",
    label: "Import Director Sequence",
    description: "Add an approved Director Sequence onto Editor Video 1",
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
    label: "Open Source in Director",
    description: "Navigate from Editor clip lineage back to Director Prompt Timeline",
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
        { label: "Director Sources", level: "ok" },
        { label: "Open in Director", level: "ok" },
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
        { label: "Send to Director", level: "ok" },
      ];
    default:
      return [...base, { label: tab || "workspace", level: "warn", note: "Partial coverage" }];
  }
}

export type RecipeStub = {
  id: string;
  title: string;
  description: string;
  expand: (ctx: { projectId?: string; sceneId?: string }) => PlannedStep[];
};

function step(actionId: string, label: string, inputs: Record<string, unknown> = {}, extra?: Partial<PlannedStep>): PlannedStep {
  return {
    id: `step-${actionId}-${Math.random().toString(36).slice(2, 6)}`,
    actionId,
    label,
    inputs,
    status: "pending",
    ...extra,
  };
}

export const RECIPE_STUBS: RecipeStub[] = [
  {
    id: "build_dialogue_scene",
    title: "Build Dialogue Scene",
    description: "Create scene, master sheet, spatial stub, then ImageGen.",
    expand: ({ projectId, sceneId }) => [
      step("searchLibrary", "Search library for character refs", { projectId, q: "character" }),
      step("createScene", "Ensure dialogue scene", { projectId, name: "Dialogue" }),
      step("createMasterSheetFromScene", "Create Master Sheet", { projectId, sceneId }),
      step("createSpatialFromMasterSheet", "Draft Spatial Map", { projectId, sceneId }),
      step("queueImageGeneration", "Generate establishing still", { projectId, prompt: "two characters in conversation, cinematic lighting" }),
    ],
  },
  {
    id: "storyboard_current_scene",
    title: "Storyboard Current Scene",
    description: "Open script workspace and prepare boards.",
    expand: ({ projectId, sceneId }) => [
      step("goToWorkspace", "Open Script / Storyboard", { tab: "script" }),
      step("validateMasterSheet", "Validate Master Sheet if present", { projectId, sceneId }),
      step("compilePrompt", "Compile storyboard-friendly prompt", { intention: "storyboard panels for current scene", mode: "structured" }),
    ],
  },
  {
    id: "prepare_lip_sync",
    title: "Prepare Lip Sync",
    description: "Navigate Director; pause for mouth mask placement.",
    expand: ({ projectId }) => [
      step("goToWorkspace", "Open Director", { tab: "director" }),
      step("searchLibrary", "Find dialogue audio", { projectId, q: "audio" }),
      step(
        "manualCheckpoint",
        "Manual: place mouth mask",
        { message: "Please place the black rectangle mouth mask on the speaker, then Continue." },
        { status: "checkpoint", checkpointMessage: "Please place the black rectangle mouth mask on the speaker, then Continue." }
      ),
    ],
  },
  {
    id: "create_master_sheet_from_scene",
    title: "Create Master Sheet from Scene",
    description: "Bootstrap Whole-Scene Package.",
    expand: ({ projectId, sceneId }) => [
      step("createMasterSheetFromScene", "Create / refresh Master Sheet", { projectId, sceneId }),
      step("goToWorkspace", "Open Scene Master Sheet", { tab: "mastersheet" }),
      step("validateMasterSheet", "Validate", { projectId, sceneId }),
    ],
  },
  {
    id: "build_coverage_from_master_sheet",
    title: "Build coverage from Master Sheet",
    description: "Spatial + storyboard + Director stubs from authority sheet.",
    expand: ({ projectId, sceneId }) => [
      step("validateMasterSheet", "Validate Master Sheet", { projectId, sceneId }),
      step("createSpatialFromMasterSheet", "Translate to Spatial", { projectId, sceneId }),
      step("goToWorkspace", "Open Storyboard", { tab: "script" }),
      step("goToWorkspace", "Open Director", { tab: "director" }),
    ],
  },
  {
    id: "create_talking_avatar",
    title: "Create Talking Avatar",
    description: "Profile → look → audio checkpoint → generate → lip sync → Director.",
    expand: ({ projectId }) => [
      step("searchLibrary", "Search library for character refs", { projectId, q: "character" }),
      step("createAvatarSession", "Create Avatar Session", { projectId, name: "Talking Avatar", mode: "talking_portrait" }),
      step("goToWorkspace", "Open Avatar Studio", { tab: "avatar" }),
      step(
        "manualCheckpoint",
        "Attach dialogue audio",
        { message: "Attach or upload dialogue audio for this avatar, then Continue." },
        { status: "checkpoint", checkpointMessage: "Attach or upload dialogue audio for this avatar, then Continue." }
      ),
      step("queueAvatarGeneration", "Queue avatar generation", { projectId, prompt: "talking portrait cinematic close-up" }),
      step(
        "prepareAvatarLipSync",
        "Prepare lip sync",
        { projectId },
        {
          status: "checkpoint",
          checkpointMessage: "Place the black rectangle over the character’s mouth, then select Continue.",
        }
      ),
      step("goToWorkspace", "Review in Director", { tab: "director" }),
    ],
  },
  {
    id: "three_performance_takes",
    title: "Three Performance Takes",
    description: "Create three takes with varied performance tones.",
    expand: ({ projectId }) => [
      step("goToWorkspace", "Open Avatar Studio", { tab: "avatar" }),
      step("createAvatarSession", "Session — restrained", { projectId, name: "Take set — restrained", mode: "talking_portrait" }),
      step("createAvatarSession", "Session — skeptical", { projectId, name: "Take set — skeptical", mode: "talking_portrait" }),
      step("createAvatarSession", "Session — warmer", { projectId, name: "Take set — warmer", mode: "talking_portrait" }),
      step(
        "manualCheckpoint",
        "Review takes",
        { message: "Generate each take with different performance tones, then Continue." },
        { status: "checkpoint", checkpointMessage: "Generate each take with different performance tones, then Continue." }
      ),
    ],
  },
  {
    id: "build_director_sequence_from_scene",
    title: "Build Director sequence from Scene",
    description: "Open Director Prompt Timeline and snapshot a Director Sequence package.",
    expand: ({ projectId, sceneId }) => [
      step("goToWorkspace", "Open Director", { tab: "director" }),
      step("createDirectorSequence", "Snapshot Director Sequence", { projectId, sceneId, name: "Scene sequence" }),
      step("compileDirectorPrompt", "Compile Director prompt", {
        intention: "model-ready shot from Prompt Timeline",
        mode: "structured",
        projectId,
        sceneId,
      }),
    ],
  },
  {
    id: "send_approved_to_editor",
    title: "Send approved to Editor",
    description: "Approve current Director Sequence and create a linked Editor clip.",
    expand: ({ projectId, sceneId }) => [
      step("createDirectorSequence", "Ensure Director Sequence", { projectId, sceneId }),
      step("sendDirectorToEditor", "Send to Editor", { projectId, include_audio: true }),
      step("goToWorkspace", "Open Editor", { tab: "editor" }),
    ],
  },
  {
    id: "assemble_scene_from_approved",
    title: "Assemble Scene 12 from approved Director outputs",
    description: "Open Editor and assemble approved Director Sequences for a scene.",
    expand: ({ projectId, sceneId }) => [
      step("assembleSceneFromApproved", "Plan assembly from approved", { projectId, sceneId }),
      step("goToWorkspace", "Open Editor", { tab: "editor" }),
      step(
        "manualCheckpoint",
        "Review stitch order",
        { message: "Drag approved Director Sequences onto Video 1, trim, then Continue." },
        {
          status: "checkpoint",
          checkpointMessage: "Drag approved Director Sequences onto Video 1, trim, then Continue.",
        }
      ),
    ],
  },
];

/** Heuristic plan builder from free text */
export function planFromIntention(
  intention: string,
  ctx: { projectId?: string; sceneId?: string }
): ActionPlan {
  const lower = intention.toLowerCase();
  const recipe = RECIPE_STUBS.find(
    (r) =>
      lower.includes(r.id.replace(/_/g, " ")) ||
      lower.includes(r.title.toLowerCase()) ||
      (lower.includes("dialogue") && r.id === "build_dialogue_scene") ||
      (lower.includes("storyboard") && r.id === "storyboard_current_scene") ||
      (lower.includes("lip") && r.id === "prepare_lip_sync") ||
      (lower.includes("master sheet") && r.id === "create_master_sheet_from_scene") ||
      (lower.includes("coverage") && r.id === "build_coverage_from_master_sheet") ||
      ((lower.includes("avatar") || lower.includes("talking")) && r.id === "create_talking_avatar") ||
      (lower.includes("takes") && r.id === "three_performance_takes") ||
      ((lower.includes("director sequence") || lower.includes("build director")) &&
        r.id === "build_director_sequence_from_scene") ||
      ((lower.includes("send") && lower.includes("editor")) && r.id === "send_approved_to_editor") ||
      ((lower.includes("assemble") || lower.includes("editor")) && r.id === "assemble_scene_from_approved")
  );
  const steps = recipe
    ? recipe.expand(ctx)
    : [
        step("searchLibrary", "Search library first (asset-first)", { projectId: ctx.projectId, q: intention.slice(0, 40) }),
        step("compilePrompt", "Compile generation package", { intention, mode: "creative", projectId: ctx.projectId, sceneId: ctx.sceneId }),
        ...(lower.includes("image") || lower.includes("generate")
          ? [step("queueImageGeneration", "Queue image generation", { projectId: ctx.projectId, prompt: intention })]
          : []),
        ...(lower.includes("video") || lower.includes("txt2vid")
          ? [step("queueVideoGeneration", "Queue video generation", { projectId: ctx.projectId, prompt: intention })]
          : []),
        step("goToWorkspace", "Open relevant workspace", {
          tab: lower.includes("avatar") || lower.includes("talking")
            ? "avatar"
            : lower.includes("assemble") || lower.includes("editor")
              ? "editor"
            : lower.includes("spatial")
              ? "spatial"
              : lower.includes("script") || lower.includes("storyboard")
                ? "script"
                : lower.includes("master")
                  ? "mastersheet"
                  : "director",
        }),
      ];

  return {
    id: `plan-${Date.now()}`,
    title: recipe?.title || "Planned Actions",
    intention,
    steps,
    createdAt: new Date().toISOString(),
  };
}
