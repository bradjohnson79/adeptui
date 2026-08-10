export type WorkspaceGroup =
  | "project"
  | "create"
  | "finish"
  | "organize"
  | "additional"
  | "legacy";

/** Desktop menu groups — registry-driven menus filter on this. */
export type WorkspaceMenuGroup =
  | "project"
  | "generate"
  | "characters"
  | "production"
  | "tools"
  | "window"
  | "none";

export type FutureWorkspace =
  | "home"
  | "setup"
  | "settings"
  | "story"
  | "sceneSheets"
  | "generate"
  | "director"
  | "timeline"
  | "audio"
  | "editor"
  | "profiles"
  | "library"
  | "jobs"
  | "resources";

export interface WorkspaceDefinition {
  label: string;
  /** i18n key under navigation namespace (M3.0F) */
  labelKey: string;
  group: WorkspaceGroup;
  futureDestination: FutureWorkspace;
  compatibilityAliases: readonly string[];
  /** Desktop menu column; `none` = not listed in workspace menus */
  menuGroup: WorkspaceMenuGroup;
  /** Sort order within menuGroup (ascending) */
  order: number;
  description: string;
  capabilityBadges: readonly string[];
  toolbarEligible?: boolean;
  commandPalette?: boolean;
  /** Hide from menus when true (legacy/internal) */
  menuHidden?: boolean;
}

/**
 * Canonical workspace registry.
 * Menus, Quick Search, and cards are generated from this — do not hardcode lists.
 */
export const WORKSPACES = {
  home: {
    label: "Project Home",
    labelKey: "projectHome",
    group: "project",
    futureDestination: "home",
    compatibilityAliases: ["project", "dashboard"],
    menuGroup: "project",
    order: 10,
    description: "Project dashboard and workspace launchpad.",
    capabilityBadges: ["Overview"],
    toolbarEligible: true,
    commandPalette: true,
  },
  setup: {
    label: "Setup",
    labelKey: "setup",
    group: "additional",
    futureDestination: "setup",
    compatibilityAliases: [],
    menuGroup: "tools",
    order: 10,
    description: "Install and verify local runtime components.",
    capabilityBadges: ["Setup"],
    commandPalette: true,
  },
  settings: {
    label: "Settings",
    labelKey: "settings",
    group: "additional",
    futureDestination: "settings",
    compatibilityAliases: [],
    menuGroup: "project",
    order: 40,
    description: "Project and studio preferences.",
    capabilityBadges: ["Settings"],
    commandPalette: true,
  },
  imagegen: {
    label: "Cinematic Image Generator",
    labelKey: "imagegen",
    group: "create",
    futureDestination: "generate",
    compatibilityAliases: ["image", "image-gen", "imagegen", "cinematic-image"],
    menuGroup: "generate",
    order: 10,
    description: "Cinematic production frames for storyboard sequences.",
    capabilityBadges: ["Image", "ComfyUI", "Storyboard"],
    toolbarEligible: true,
    commandPalette: true,
  },
  one: {
    label: "1 Frame",
    labelKey: "generate",
    group: "create",
    futureDestination: "generate",
    compatibilityAliases: ["one-frame"],
    menuGroup: "generate",
    order: 40,
    description: "Animate a single keyframe.",
    capabilityBadges: ["Video", "Director"],
    commandPalette: true,
  },
  txt2vid: {
    label: "Text to Video",
    labelKey: "txt2vid",
    group: "create",
    futureDestination: "generate",
    compatibilityAliases: ["text-to-video", "text2video", "txt2vid"],
    menuGroup: "generate",
    order: 20,
    description: "Create video directly from a written scene.",
    capabilityBadges: ["Video"],
    commandPalette: true,
  },
  three: {
    label: "3 Frame",
    labelKey: "generate",
    group: "create",
    futureDestination: "generate",
    compatibilityAliases: ["three-frame"],
    menuGroup: "generate",
    order: 50,
    description: "Build motion from start, middle, and end frames.",
    capabilityBadges: ["Video", "Timeline"],
    commandPalette: true,
  },
  timeline: {
    label: "Timeline Generator",
    labelKey: "timeline",
    group: "create",
    futureDestination: "timeline",
    compatibilityAliases: ["director", "director-generator", "director_workspace"],
    menuGroup: "generate",
    order: 30,
    description: "Plan and assemble scenes, shots, and sequences.",
    capabilityBadges: ["Timeline"],
    toolbarEligible: true,
    commandPalette: true,
  },
  /** @deprecated Wave 4C — hidden alias shell; resolveWorkspace maps to timeline */
  director: {
    label: "Timeline Generator",
    labelKey: "timeline",
    group: "legacy",
    futureDestination: "timeline",
    compatibilityAliases: [],
    menuGroup: "none",
    order: 999,
    description: "Legacy Director product id — use Timeline Generator.",
    capabilityBadges: ["Timeline"],
    toolbarEligible: false,
    commandPalette: false,
    menuHidden: true,
  },
  profiles: {
    label: "Project Profile",
    labelKey: "profiles",
    group: "organize",
    futureDestination: "profiles",
    compatibilityAliases: [],
    menuGroup: "characters",
    order: 30,
    description: "Shared visual, tonal, technical, and production identity.",
    capabilityBadges: ["Profiles"],
    commandPalette: true,
  },
  tools: {
    label: "Character / Angles",
    labelKey: "profiles",
    group: "legacy",
    futureDestination: "profiles",
    compatibilityAliases: ["image-tools"],
    menuGroup: "characters",
    order: 40,
    description: "Character angle and reference tools.",
    capabilityBadges: ["Legacy"],
    commandPalette: true,
    menuHidden: true,
  },
  spatial: {
    label: "Spatial Map",
    labelKey: "spatialMap",
    group: "create",
    futureDestination: "sceneSheets",
    compatibilityAliases: ["blocking", "spatial-map", "spatialmap"],
    menuGroup: "production",
    order: 40,
    description: "Artist-facing blocking canvas, 360 collage planning, and camera staging.",
    capabilityBadges: ["Spatial", "360"],
    commandPalette: true,
  },
  posecraft: {
    label: "PoseCraft",
    labelKey: "posecraft",
    group: "create",
    futureDestination: "generate",
    compatibilityAliases: ["pose-craft", "pose", "posing"],
    menuGroup: "production",
    order: 45,
    description:
      "Pose characters on a 3D stage with camera, lenses, and guides — pre-production staging for shots and storyboards.",
    capabilityBadges: ["Pose", "Staging", "3D"],
    commandPalette: true,
  },
  script: {
    label: "Storyboard Studio",
    labelKey: "script",
    group: "create",
    futureDestination: "story",
    compatibilityAliases: ["story", "storyboard", "script-storyboard"],
    menuGroup: "production",
    order: 20,
    description: "Professional page sheets and shot sequences linked to script.",
    capabilityBadges: ["Script", "Storyboard", "Timeline Prep"],
    commandPalette: true,
  },
  shotlist: {
    label: "Shot List",
    labelKey: "shotlist",
    group: "legacy",
    futureDestination: "story",
    compatibilityAliases: ["shot-list"],
    menuGroup: "production",
    order: 25,
    description: "Structured shot list.",
    capabilityBadges: ["Legacy"],
    commandPalette: true,
    menuHidden: true,
  },
  generate: {
    label: "Generate Timeline",
    labelKey: "generate",
    group: "legacy",
    futureDestination: "generate",
    compatibilityAliases: ["generate-timeline"],
    menuGroup: "generate",
    order: 60,
    description: "Legacy generate timeline.",
    capabilityBadges: ["Legacy"],
    commandPalette: true,
    menuHidden: true,
  },
  library: {
    label: "Library",
    labelKey: "library",
    group: "organize",
    futureDestination: "library",
    compatibilityAliases: ["libraries"],
    menuGroup: "project",
    order: 20,
    description: "Project media shelf and asset taxonomy.",
    capabilityBadges: ["Library"],
    toolbarEligible: true,
    commandPalette: true,
  },
  marketplace: {
    label: "Marketplace",
    labelKey: "marketplace",
    group: "additional",
    futureDestination: "resources",
    compatibilityAliases: ["resources"],
    menuGroup: "tools",
    order: 40,
    description: "Creative packs and resources.",
    capabilityBadges: ["Resources"],
    commandPalette: true,
  },
  mastersheet: {
    label: "Scene Master Sheet",
    labelKey: "mastersheet",
    group: "create",
    futureDestination: "sceneSheets",
    compatibilityAliases: ["scene-sheets", "sceneSheets"],
    menuGroup: "production",
    order: 30,
    description: "Scene continuity master sheet.",
    capabilityBadges: ["Scenes"],
    commandPalette: true,
  },
  avatar: {
    label: "Avatar Studio",
    labelKey: "avatar",
    group: "create",
    futureDestination: "generate",
    compatibilityAliases: ["avatar-studio"],
    menuGroup: "characters",
    order: 20,
    description: "Speaking portraits and avatar generation.",
    capabilityBadges: ["Avatar", "Lip Sync"],
    commandPalette: true,
  },
  voicestudio: {
    label: "Voice Studio",
    labelKey: "voiceStudio",
    group: "finish",
    futureDestination: "audio",
    compatibilityAliases: ["voice-studio", "voiceStudio"],
    menuGroup: "production",
    order: 55,
    description: "Design character voices, direct performances, and prepare dialogue for production.",
    capabilityBadges: ["Voice", "Performance"],
    commandPalette: true,
  },
  characters: {
    label: "Character Creator",
    labelKey: "characters",
    group: "organize",
    futureDestination: "profiles",
    compatibilityAliases: ["character", "character-profile", "character-identity", "identity", "characters"],
    menuGroup: "characters",
    order: 10,
    description: "Build characters — sheets, voice, wardrobe, expressions, performance, and approved look.",
    capabilityBadges: ["Identity", "Voice"],
    toolbarEligible: true,
    commandPalette: true,
  },
  bible: {
    label: "Production Bible",
    labelKey: "bible",
    group: "organize",
    futureDestination: "story",
    compatibilityAliases: ["production-bible", "productionbible"],
    menuGroup: "production",
    order: 10,
    description: "Canon production bible and continuity.",
    capabilityBadges: ["Bible", "Continuity"],
    toolbarEligible: true,
    commandPalette: true,
  },
  identityregistry: {
    label: "Approved Look",
    labelKey: "identityRegistry",
    group: "organize",
    futureDestination: "profiles",
    compatibilityAliases: ["identity-registry", "visual-identity", "identities"],
    menuGroup: "characters",
    order: 15,
    description: "Compatibility route — opens Character Profiles → Approved Look.",
    capabilityBadges: ["Identity", "References"],
    toolbarEligible: false,
    commandPalette: false,
    menuHidden: true,
  },
  continuity: {
    label: "Continuity Workspace",
    labelKey: "continuity",
    group: "organize",
    futureDestination: "story",
    compatibilityAliases: ["continuity-workspace", "continuity-review"],
    menuGroup: "production",
    order: 15,
    description: "Continuity evaluation, sequence review, and human decisions.",
    capabilityBadges: ["Continuity", "Review"],
    toolbarEligible: true,
    commandPalette: true,
  },
  magi: {
    label: "MAGI Editor",
    labelKey: "magi",
    group: "finish",
    futureDestination: "editor",
    compatibilityAliases: ["magi-editor", "magieditor", "finishing-editor"],
    menuGroup: "production",
    order: 45,
    description: "Adept UI MAGI Editor — Cut. Change. Create. The production editor for all types and takes.",
    capabilityBadges: ["MAGI", "Edit", "AI"],
    toolbarEligible: true,
    commandPalette: true,
  },
  editor: {
    label: "Editor",
    labelKey: "editor",
    group: "legacy",
    futureDestination: "editor",
    compatibilityAliases: [],
    menuGroup: "production",
    order: 50,
    description: "Superseded by MAGI Editor — compatibility alias only.",
    capabilityBadges: ["Legacy"],
    toolbarEligible: false,
    commandPalette: false,
    menuHidden: true,
  },
  audiostudio: {
    label: "Audio Studio",
    labelKey: "audioStudio",
    group: "finish",
    futureDestination: "audio",
    compatibilityAliases: ["audio", "audio-studio"],
    menuGroup: "production",
    order: 60,
    description: "Create music, ambience, Foley, sound effects, and production-ready audio layers.",
    capabilityBadges: ["Audio", "TTS"],
    commandPalette: true,
  },
  generationtools: {
    label: "Generation Tools",
    labelKey: "generationTools",
    group: "create",
    futureDestination: "generate",
    compatibilityAliases: ["tools-hub", "generation-tools", "enhance", "gen-tools"],
    menuGroup: "generate",
    order: 15,
    description: "Enhance, upscale, and generation utilities.",
    capabilityBadges: ["Enhance", "Tools"],
    toolbarEligible: true,
    commandPalette: true,
    menuHidden: true,
  },
  scriptwriter: {
    label: "Scriptwriter",
    labelKey: "scriptwriter",
    group: "create",
    futureDestination: "story",
    compatibilityAliases: ["script-writer", "writer"],
    menuGroup: "production",
    order: 15,
    description: "Professional screenplay studio with Co-Director integration.",
    capabilityBadges: ["Writing", "Screenplay"],
    commandPalette: true,
  },
  brandstudio: {
    label: "Brand Studio",
    labelKey: "brandStudio",
    group: "create",
    futureDestination: "generate",
    compatibilityAliases: ["brand", "branding", "promo"],
    menuGroup: "generate",
    order: 70,
    description: "Create brand identities, visual systems, campaign assets, and reusable production styling.",
    capabilityBadges: ["Brand"],
    commandPalette: true,
  },
} as const satisfies Record<string, WorkspaceDefinition>;

export type EditorTab = keyof typeof WORKSPACES;

export const ALL_TABS = Object.freeze(Object.keys(WORKSPACES) as EditorTab[]);

export const MENU_GROUP_LABELS: Record<Exclude<WorkspaceMenuGroup, "none">, string> = {
  project: "Project",
  generate: "Generate",
  characters: "Characters",
  production: "Production",
  tools: "Tools",
  window: "Window",
};

const WORKSPACE_ALIASES: ReadonlyMap<string, EditorTab> = (() => {
  const aliases = new Map<string, EditorTab>(
    ALL_TABS.map((tab) => [tab.toLowerCase(), tab] as const)
  );
  for (const tab of ALL_TABS) {
    for (const alias of WORKSPACES[tab].compatibilityAliases) {
      const normalized = alias.trim().toLowerCase();
      if (normalized && !aliases.has(normalized)) aliases.set(normalized, tab);
    }
  }
  return aliases;
})();

export function resolveWorkspace(value: unknown): EditorTab | null {
  if (typeof value !== "string") return null;
  const normalized = value.trim().toLowerCase();
  const resolved = normalized ? WORKSPACE_ALIASES.get(normalized) ?? null : null;
  // Legacy finishing Editor is retired — MAGI Editor is the sole production editor.
  if (resolved === "editor") return "magi";
  // Wave 4C: Director product renamed Timeline — never surface two products.
  if (resolved === "director") return "timeline";
  // M4.7: writing entry points resolve to Scriptwriter Studio.
  // Storyboard remains available via workspace=storyboard / script-storyboard.
  if (normalized === "script-writer" || normalized === "writer") return "scriptwriter";
  return resolved;
}

export function workspaceLabel(tab: EditorTab): string {
  return WORKSPACES[tab].label;
}

function isMenuHidden(tab: EditorTab): boolean {
  return Boolean((WORKSPACES[tab] as WorkspaceDefinition).menuHidden);
}

export function workspacesForMenu(menuGroup: Exclude<WorkspaceMenuGroup, "none">): EditorTab[] {
  return ALL_TABS.filter((tab) => {
    const def = WORKSPACES[tab] as WorkspaceDefinition;
    return def.menuGroup === menuGroup && !isMenuHidden(tab);
  }).sort((a, b) => WORKSPACES[a].order - WORKSPACES[b].order);
}

export function commandPaletteWorkspaces(): EditorTab[] {
  return ALL_TABS.filter((tab) => {
    const def = WORKSPACES[tab] as WorkspaceDefinition;
    return def.commandPalette !== false && !isMenuHidden(tab);
  }).sort((a, b) => WORKSPACES[a].label.localeCompare(WORKSPACES[b].label));
}
