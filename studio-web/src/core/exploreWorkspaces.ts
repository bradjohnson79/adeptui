import type { DashboardImage } from "../dashboardImages";
import { dashboardImages } from "../dashboardImages";
import { WORKSPACES, type EditorTab } from "./workspaces";

/**
 * Canonical Home "Explore Adept UI" roster.
 * Timeline and MAGI stay on Home feature cards / nav / Production, not here.
 * Library stays in Production and the project workspace, not on this grid.
 * Text to Video, 1 Frame, and 3 Frame are LTX modes on Timeline, not Explore cards.
 * Ordered list of workspace ids from the WORKSPACES registry — do not hardcode
 * parallel route maps in Home or Production menu.
 */
export const EXPLORE_WORKSPACE_IDS = [
  "imagegen",
  "characters",
  "propcreator",
  "environmentcreator",
  "script",
  "scriptwriter",
  "voicestudio",
  "audiostudio",
] as const satisfies readonly EditorTab[];

export type ExploreWorkspaceId = (typeof EXPLORE_WORKSPACE_IDS)[number];

export type ExploreWorkspaceCard = {
  id: ExploreWorkspaceId;
  label: string;
  description: string;
  workspace: ExploreWorkspaceId;
  image: DashboardImage;
  requiresProject: boolean;
  enabled: boolean;
  category: "production" | "studio";
};

/**
 * Creator-facing Explore card labels/copy.
 * Prefer short Home labels (e.g. Storyboard) while WORKSPACES keeps product/menu names
 * (e.g. Storyboard Studio) for chrome and Production menu.
 */
const EXPLORE_CARD_COPY: Record<
  ExploreWorkspaceId,
  { label: string; description: string; category: ExploreWorkspaceCard["category"]; image: DashboardImage }
> = {
  imagegen: {
    label: "Image Generation",
    description: "Create stills, keyframes, and references.",
    category: "studio",
    image: dashboardImages.imagegen,
  },
  characters: {
    label: "Character Creator",
    description: "Design character identity, appearance, wardrobe, and voice.",
    category: "studio",
    image: dashboardImages.characterCreator,
  },
  propcreator: {
    label: "Prop Creator",
    description: "Design reusable props, objects, and production assets.",
    category: "studio",
    image: dashboardImages.propCreator,
  },
  environmentcreator: {
    label: "Environment Creator",
    description: "Build locations, sets, and reusable scene environments.",
    category: "studio",
    image: dashboardImages.environmentCreator,
  },
  script: {
    label: "Storyboard",
    description: "Plan shots, beats, and visual sequences before production.",
    category: "production",
    image: dashboardImages.storyboard,
  },
  scriptwriter: {
    label: "Scriptwriter",
    description: "Write and organize professional scripts, scenes, and dialogue.",
    category: "production",
    image: dashboardImages.scriptwriter,
  },
  voicestudio: {
    label: "Voice Studio",
    description: "Design character voices, direct performances, and prepare dialogue.",
    category: "studio",
    image: dashboardImages.voice,
  },
  audiostudio: {
    label: "Audio Studio",
    description: "Create music, ambience, Foley, and production-ready audio.",
    category: "studio",
    image: dashboardImages.audio,
  },
};

export function getExploreWorkspaceCards(): ExploreWorkspaceCard[] {
  return EXPLORE_WORKSPACE_IDS.map((id) => {
    const copy = EXPLORE_CARD_COPY[id];
    // Guard: registry entry must exist so Explore never drifts from WORKSPACES ids.
    if (!WORKSPACES[id]) {
      throw new Error(`Explore workspace missing from WORKSPACES registry: ${id}`);
    }
    return {
      id,
      label: copy.label,
      description: copy.description,
      workspace: id,
      image: copy.image,
      requiresProject: true,
      enabled: true,
      category: copy.category,
    };
  });
}

export function buildProjectWorkspacePath(projectId: string, workspace: EditorTab): string {
  return `/project/${encodeURIComponent(projectId)}?workspace=${encodeURIComponent(workspace)}`;
}
