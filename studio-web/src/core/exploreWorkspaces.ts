import type { DashboardImage } from "../dashboardImages";
import { dashboardImages } from "../dashboardImages";
import { WORKSPACES, type EditorTab } from "./workspaces";

/**
 * Canonical Home "Explore Adept UI" roster.
 * Ordered list of workspace ids from the WORKSPACES registry — do not hardcode
 * parallel route maps in Home or Production menu.
 */
export const EXPLORE_WORKSPACE_IDS = [
  "timeline",
  "magi",
  "brandstudio",
  "spatial",
  "posecraft",
  "imagegen",
  "txt2vid",
  "one",
  "three",
  "characters",
  "scriptwriter",
  "avatar",
  "voicestudio",
  "audiostudio",
  "library",
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
  category: "production" | "studio" | "library";
};

/**
 * Creator-facing Explore card labels/copy.
 * Prefer short Home labels (e.g. Timeline) while WORKSPACES keeps product/menu names
 * (e.g. Timeline Generator) for chrome and Production menu.
 */
const EXPLORE_CARD_COPY: Record<
  ExploreWorkspaceId,
  { label: string; description: string; category: ExploreWorkspaceCard["category"]; image: DashboardImage }
> = {
  timeline: {
    label: "Timeline",
    description: "Build and organize production timelines, scenes, shots, and sequences.",
    category: "production",
    image: dashboardImages.timeline,
  },
  magi: {
    label: "MAGI Editor",
    description: "Cut. Change. Create. — AI-native editing for all types and takes.",
    category: "production",
    image: dashboardImages.magi,
  },
  brandstudio: {
    label: "Brand Studio",
    description: "Create brand identities, visual systems, campaign assets, and reusable production styling.",
    category: "studio",
    image: dashboardImages.brand,
  },
  spatial: {
    label: "Spatial Map",
    description: "Block cameras, characters, and continuity.",
    category: "production",
    image: dashboardImages.spatial,
  },
  posecraft: {
    label: "PoseCraft",
    description: "Pose characters on a 3D stage with cameras, lenses, and guides to stage shots before generation.",
    category: "production",
    image: dashboardImages.posecraft,
  },
  imagegen: {
    label: "Image Generation",
    description: "Create stills, keyframes, and references.",
    category: "studio",
    image: dashboardImages.imagegen,
  },
  txt2vid: {
    label: "Text to Video",
    description: "Generate motion clips from prompts.",
    category: "studio",
    image: dashboardImages.video,
  },
  one: {
    label: "1 Frame",
    description: "Animate a single keyframe into a cinematic shot.",
    category: "studio",
    image: dashboardImages.oneFrame,
  },
  three: {
    label: "3 Frame",
    description: "Build motion from start, middle, and end frames.",
    category: "studio",
    image: dashboardImages.threeFrame,
  },
  characters: {
    label: "Character Creator",
    description: "Design character identity, appearance, wardrobe, voice, and continuity.",
    category: "studio",
    image: dashboardImages.characterCreator,
  },
  scriptwriter: {
    label: "Scriptwriter",
    description: "Write and organize professional scripts, scenes, and dialogue.",
    category: "production",
    image: dashboardImages.scriptwriter,
  },
  avatar: {
    label: "Avatar Studio",
    description: "Talking characters, presenters, and guided lip sync from Character Profiles.",
    category: "studio",
    image: dashboardImages.avatar,
  },
  voicestudio: {
    label: "Voice Studio",
    description: "Design character voices, direct performances, and prepare dialogue for production.",
    category: "studio",
    image: dashboardImages.voice,
  },
  audiostudio: {
    label: "Audio Studio",
    description: "Create music, ambience, Foley, sound effects, and production-ready audio layers.",
    category: "studio",
    image: dashboardImages.audio,
  },
  library: {
    label: "Library",
    description: "Browse assets, tags, and approved frames.",
    category: "library",
    image: dashboardImages.library,
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
