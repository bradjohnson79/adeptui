/**
 * Declarative Production menu catalog.
 * Labels, routes, descriptions, help, and availability keys only — no health fetches.
 */
import type { EditorTab } from "./workspaces";
import type { ProductionAvailabilityKey, ProductAvailability } from "./productionAvailability";

export type ProductionCategoryId =
  | "create"
  | "pre-production"
  | "creative-studios"
  | "post-production"
  | "recent-projects";

export const PRODUCTION_CATEGORY_ORDER: readonly ProductionCategoryId[] = [
  "create",
  "pre-production",
  "creative-studios",
  "post-production",
  "recent-projects",
] as const;

export const PRODUCTION_CATEGORY_LABELS: Record<ProductionCategoryId, string> = {
  create: "Create",
  "pre-production": "Pre-Production",
  "creative-studios": "Creative Studios",
  "post-production": "Post",
  "recent-projects": "Recent Projects",
};

/** @deprecated Old IDs — kept for docs/migration notes only */
export const LEGACY_PRODUCTION_CATEGORY_IDS = [
  "scene-generation",
  "production-profiles",
  "pre-production-tools",
  "studios",
  "post-production",
] as const;

export type ProductionMenuAction = "coDirector" | "workspace" | "coDirectorAction";

export type CoDirectorQuickActionId =
  | "continueProject"
  | "reviewTimeline"
  | "generateAssets"
  | "openChat";

export type ProductionMenuEntryDef = {
  id: string;
  label: string;
  description: string;
  helpLabel: string;
  helpContent: string;
  action: ProductionMenuAction;
  workspace?: EditorTab;
  coDirectorAction?: CoDirectorQuickActionId;
  availabilityKey?: ProductionAvailabilityKey;
  /** When true, Production menu routes through a character picker instead of the workspace. */
  requiresCharacter?: boolean;
};

export type ProductionCategoryDef = {
  id: ProductionCategoryId;
  label: string;
  entries: readonly ProductionMenuEntryDef[];
};

export const CO_DIRECTOR_QUICK_ACTIONS: readonly ProductionMenuEntryDef[] = [
  {
    id: "cd-continue",
    label: "Continue Project",
    description: "Return to the project home overview",
    helpLabel: "Continue Project",
    helpContent: "Open the project home so you can resume where you left off.",
    action: "coDirectorAction",
    coDirectorAction: "continueProject",
    workspace: "home",
  },
  {
    id: "cd-timeline",
    label: "Review Timeline",
    description: "Open the Timeline Generator",
    helpLabel: "Review Timeline",
    helpContent: "Jump to Timeline Generator to review scenes, shots, and sequences.",
    action: "coDirectorAction",
    coDirectorAction: "reviewTimeline",
    workspace: "timeline",
  },
  {
    id: "cd-generate",
    label: "Generate Assets",
    description: "Open Image Generation",
    helpLabel: "Generate Assets",
    helpContent: "Create concepts, stills, and production frames.",
    action: "coDirectorAction",
    coDirectorAction: "generateAssets",
    workspace: "imagegen",
  },
  {
    id: "cd-chat",
    label: "Open Chat",
    description: "Talk with Co-Director",
    helpLabel: "Open Chat",
    helpContent: "Open Co-Director chat for planning, reviews, and production decisions.",
    action: "coDirectorAction",
    coDirectorAction: "openChat",
  },
] as const;

export const PRODUCTION_MENU_CATALOG: readonly ProductionCategoryDef[] = [
  {
    id: "create",
    label: PRODUCTION_CATEGORY_LABELS.create,
    entries: [
      {
        id: "txt2vid",
        label: "Text to Video",
        description: "Create video directly from a written scene",
        helpLabel: "What is Text to Video?",
        helpContent: "Create video directly from a written scene description.",
        action: "workspace",
        workspace: "txt2vid",
        availabilityKey: "textToVideo",
      },
      {
        id: "imagegen",
        label: "Image Generation",
        description: "Create images, concepts, and production frames",
        helpLabel: "What is Image Generation?",
        helpContent: "Create images, concepts, props, environments, and reference frames.",
        action: "workspace",
        workspace: "imagegen",
        availabilityKey: "imageGeneration",
      },
      {
        id: "one",
        label: "1 Frame",
        description: "Animate a single keyframe",
        helpLabel: "What is 1 Frame?",
        helpContent: "Animate a single keyframe into a short motion clip.",
        action: "workspace",
        workspace: "one",
        availabilityKey: "oneFrame",
      },
      {
        id: "three",
        label: "3 Frame",
        description: "Build motion from start, middle, and end frames",
        helpLabel: "What is 3 Frame?",
        helpContent: "Build motion from start, middle, and end frames for continuity.",
        action: "workspace",
        workspace: "three",
        availabilityKey: "threeFrame",
      },
      {
        id: "script",
        label: "Storyboard",
        description: "Design visual panels and shot sequences",
        helpLabel: "What is Storyboard?",
        helpContent: "Design visual panels and shot sequences before you assemble the timeline.",
        action: "workspace",
        workspace: "script",
      },
      {
        id: "timeline",
        label: "Timeline Generator",
        description: "Plan and assemble scenes, shots, and sequences",
        helpLabel: "What is Timeline Generator?",
        helpContent: "Plan and assemble scenes, shots, and sequences after storyboard.",
        action: "workspace",
        workspace: "timeline",
        availabilityKey: "timeline",
      },
    ],
  },
  {
    id: "pre-production",
    label: PRODUCTION_CATEGORY_LABELS["pre-production"],
    entries: [
      {
        id: "scriptwriter",
        label: "Scriptwriter",
        description: "Write and organize scripts and dialogue",
        helpLabel: "What is Scriptwriter?",
        helpContent: "Write and organize scripts and dialogue for your production.",
        action: "workspace",
        workspace: "scriptwriter",
      },
      {
        id: "environmentcreator",
        label: "Environment Creator",
        description: "Plan and create Environment Reference Sheets (ERS) for locations and sets",
        helpLabel: "What is Environment Creator?",
        helpContent: "Plan and create the Environment Reference Sheet (ERS) for a location or set — the environment identity your production builds from, like a CRS for characters or a PRS for props. Not shot creation or storyboard.",
        action: "workspace",
        workspace: "environmentcreator",
      },
      {
        id: "propcreator",
        label: "Prop Creator",
        description: "Create project Prop identities and approve a production look",
        helpLabel: "What is Prop Creator?",
        helpContent: "Create and refine project Props — description, reference, generated looks, and an approved identity used by the Image Generator.",
        action: "workspace",
        workspace: "propcreator",
      },
    ],
  },
  {
    id: "creative-studios",
    label: PRODUCTION_CATEGORY_LABELS["creative-studios"],
    entries: [
      {
        id: "characters",
        label: "Character Creator",
        description: "Build characters, voices, wardrobe, and performance",
        helpLabel: "What is Character Creator?",
        helpContent:
          "Create and refine characters — sheets, voice, wardrobe, expressions, performance, relationships, and approved look.",
        action: "workspace",
        workspace: "characters",
      },
      {
        id: "voicestudio",
        label: "Voice Studio",
        description: "Character voices, performances, and dialogue prep",
        helpLabel: "What is Voice Studio?",
        helpContent: "Design character voices, direct performances, and prepare dialogue for production.",
        action: "workspace",
        workspace: "voicestudio",
        requiresCharacter: false,
      },
      {
        id: "audiostudio",
        label: "Audio Studio",
        description: "Music, ambience, Foley, and production audio",
        helpLabel: "What is Audio Studio?",
        helpContent: "Create music, ambience, Foley, sound effects, and production-ready audio layers.",
        action: "workspace",
        workspace: "audiostudio",
        availabilityKey: "audioStudio",
      },
      {
        id: "library",
        label: "Library",
        description: "Browse and manage project media, references, images, video, and audio",
        helpLabel: "What is Library?",
        helpContent: "Browse and manage project media, references, images, video, and audio.",
        action: "workspace",
        workspace: "library",
      },
    ],
  },
  {
    id: "post-production",
    label: PRODUCTION_CATEGORY_LABELS["post-production"],
    entries: [
      {
        id: "magi",
        label: "MAGI Editor",
        description: "Edit, enhance, compare, finish, and prepare production assets",
        helpLabel: "What is MAGI Editor?",
        helpContent: "Edit, enhance, compare, finish, and prepare production assets.",
        action: "workspace",
        workspace: "magi",
      },
    ],
  },
] as const;

export type BuiltProductionMenuEntry = ProductionMenuEntryDef & {
  availability?: ProductAvailability;
  characterMissing?: boolean;
};

export type BuiltProductionCategory = {
  id: ProductionCategoryId;
  label: string;
  entries: BuiltProductionMenuEntry[];
};

export type BuiltProductionMenu = {
  coDirector: {
    id: "coDirector";
    label: "Co-Director";
    description: "Your AI Production Assistant";
    helpLabel: "What is Co-Director?";
    helpContent: "Your AI production assistant for planning, reviews, and production decisions.";
    quickActions: BuiltProductionMenuEntry[];
  };
  categories: BuiltProductionCategory[];
  projectId?: string;
  selectedCharacterId?: string;
};

export function buildProductionMenu(input: {
  availability: Record<ProductionAvailabilityKey, ProductAvailability>;
  projectId?: string;
  selectedCharacterId?: string;
}): BuiltProductionMenu {
  const selected = (input.selectedCharacterId || "").trim();
  const decorate = (entry: ProductionMenuEntryDef): BuiltProductionMenuEntry => {
    const availability = entry.availabilityKey
      ? input.availability[entry.availabilityKey]
      : undefined;
    const characterMissing = Boolean(entry.requiresCharacter && !selected);
    return { ...entry, availability, characterMissing };
  };
  return {
    coDirector: {
      id: "coDirector",
      label: "Co-Director",
      description: "Your AI Production Assistant",
      helpLabel: "What is Co-Director?",
      helpContent: "Your AI production assistant for planning, reviews, and production decisions.",
      quickActions: CO_DIRECTOR_QUICK_ACTIONS.map(decorate),
    },
    projectId: input.projectId,
    selectedCharacterId: selected || undefined,
    categories: PRODUCTION_MENU_CATALOG.map((cat) => ({
      id: cat.id,
      label: cat.label,
      entries: cat.entries.map(decorate),
    })),
  };
}
