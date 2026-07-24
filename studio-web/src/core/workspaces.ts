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
  group: WorkspaceGroup;
  futureDestination: FutureWorkspace;
  compatibilityAliases: readonly string[];
}

/**
 * Phase 0 registry for every workspace the current ProjectEditor can render.
 * Current IDs remain canonical until their future destinations have parity.
 */
export const WORKSPACES = {
  home: { label: "Project Home", group: "project", futureDestination: "home", compatibilityAliases: ["project", "dashboard"] },
  setup: { label: "Setup", group: "additional", futureDestination: "setup", compatibilityAliases: [] },
  settings: { label: "Settings", group: "additional", futureDestination: "settings", compatibilityAliases: [] },
  imagegen: { label: "ImageGen", group: "create", futureDestination: "generate", compatibilityAliases: ["image", "image-gen"] },
  one: { label: "1 Frame", group: "create", futureDestination: "generate", compatibilityAliases: ["one-frame"] },
  txt2vid: { label: "Txt2Vid", group: "create", futureDestination: "generate", compatibilityAliases: ["text-to-video", "text2video"] },
  three: { label: "3 Frame", group: "create", futureDestination: "generate", compatibilityAliases: ["three-frame"] },
  director: { label: "Director", group: "create", futureDestination: "director", compatibilityAliases: [] },
  profiles: { label: "Profiles", group: "organize", futureDestination: "profiles", compatibilityAliases: [] },
  tools: { label: "Character / Angles", group: "legacy", futureDestination: "profiles", compatibilityAliases: ["image-tools"] },
  spatial: { label: "Spatial Map", group: "legacy", futureDestination: "sceneSheets", compatibilityAliases: ["blocking"] },
  script: { label: "Script / Storyboard", group: "create", futureDestination: "story", compatibilityAliases: ["story"] },
  shotlist: { label: "Shot List", group: "legacy", futureDestination: "story", compatibilityAliases: ["shot-list"] },
  generate: { label: "Generate Timeline", group: "legacy", futureDestination: "generate", compatibilityAliases: ["generate-timeline"] },
  library: { label: "Library", group: "organize", futureDestination: "library", compatibilityAliases: ["libraries"] },
  marketplace: { label: "Marketplace", group: "additional", futureDestination: "resources", compatibilityAliases: ["resources"] },
  mastersheet: { label: "Scene Master Sheet", group: "create", futureDestination: "sceneSheets", compatibilityAliases: ["scene-sheets", "sceneSheets"] },
  avatar: { label: "Avatar Studio", group: "create", futureDestination: "generate", compatibilityAliases: ["avatar-studio"] },
  editor: { label: "Editor", group: "finish", futureDestination: "editor", compatibilityAliases: [] },
  audiostudio: { label: "Audio Studio", group: "finish", futureDestination: "audio", compatibilityAliases: ["audio", "audio-studio"] },
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
