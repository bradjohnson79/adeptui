export type WorkspaceGroup =
  | "project"
  | "create"
  | "finish"
  | "organize"
  | "additional"
  | "legacy";

export type FutureWorkspace =
  | "home"
  | "setup"
  | "settings"
  | "story"
  | "sceneSheets"
  | "generate"
  | "director"
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
}

/**
 * Phase 0 registry for every workspace the current ProjectEditor can render.
 * Current IDs remain canonical until their future destinations have parity.
 */
export const WORKSPACES = {
  home: { label: "Project Home", labelKey: "projectHome", group: "project", futureDestination: "home", compatibilityAliases: ["project", "dashboard"] },
  setup: { label: "Setup", labelKey: "setup", group: "additional", futureDestination: "setup", compatibilityAliases: [] },
  settings: { label: "Settings", labelKey: "settings", group: "additional", futureDestination: "settings", compatibilityAliases: [] },
  imagegen: { label: "ImageGen", labelKey: "imagegen", group: "create", futureDestination: "generate", compatibilityAliases: ["image", "image-gen"] },
  one: { label: "1 Frame", labelKey: "generate", group: "create", futureDestination: "generate", compatibilityAliases: ["one-frame"] },
  txt2vid: { label: "Txt2Vid", labelKey: "txt2vid", group: "create", futureDestination: "generate", compatibilityAliases: ["text-to-video", "text2video"] },
  three: { label: "3 Frame", labelKey: "generate", group: "create", futureDestination: "generate", compatibilityAliases: ["three-frame"] },
  director: { label: "Director", labelKey: "director", group: "create", futureDestination: "director", compatibilityAliases: [] },
  profiles: { label: "Profiles", labelKey: "profiles", group: "organize", futureDestination: "profiles", compatibilityAliases: [] },
  tools: { label: "Character / Angles", labelKey: "profiles", group: "legacy", futureDestination: "profiles", compatibilityAliases: ["image-tools"] },
  spatial: { label: "Spatial Map", labelKey: "generate", group: "legacy", futureDestination: "sceneSheets", compatibilityAliases: ["blocking"] },
  script: { label: "Script / Storyboard", labelKey: "script", group: "create", futureDestination: "story", compatibilityAliases: ["story"] },
  shotlist: { label: "Shot List", labelKey: "shotlist", group: "legacy", futureDestination: "story", compatibilityAliases: ["shot-list"] },
  generate: { label: "Generate Timeline", labelKey: "generate", group: "legacy", futureDestination: "generate", compatibilityAliases: ["generate-timeline"] },
  library: { label: "Library", labelKey: "library", group: "organize", futureDestination: "library", compatibilityAliases: ["libraries"] },
  marketplace: { label: "Marketplace", labelKey: "marketplace", group: "additional", futureDestination: "resources", compatibilityAliases: ["resources"] },
  mastersheet: { label: "Scene Master Sheet", labelKey: "mastersheet", group: "create", futureDestination: "sceneSheets", compatibilityAliases: ["scene-sheets", "sceneSheets"] },
  avatar: { label: "Avatar Studio", labelKey: "avatar", group: "create", futureDestination: "generate", compatibilityAliases: ["avatar-studio"] },
  bible: { label: "Production Bible", labelKey: "bible", group: "organize", futureDestination: "story", compatibilityAliases: ["production-bible", "productionbible"] },
  editor: { label: "Editor", labelKey: "editor", group: "finish", futureDestination: "editor", compatibilityAliases: [] },
  audiostudio: { label: "Audio Studio", labelKey: "audioStudio", group: "finish", futureDestination: "audio", compatibilityAliases: ["audio", "audio-studio"] },
} as const satisfies Record<string, WorkspaceDefinition>;

export type EditorTab = keyof typeof WORKSPACES;

export const ALL_TABS = Object.freeze(Object.keys(WORKSPACES) as EditorTab[]);

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
  return normalized ? WORKSPACE_ALIASES.get(normalized) ?? null : null;
}

export function workspaceLabel(tab: EditorTab): string {
  return WORKSPACES[tab].label;
}
