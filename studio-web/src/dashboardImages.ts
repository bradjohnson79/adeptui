/** Central cinematic image registry — prefers Aurora registry; drop JPEGs into public/images/dashboard later. */
import { auroraCardImagery } from "./theme/auroraCardImagery";

export type DashboardImage = {
  src: string;
  alt: string;
  attribution?: string;
  motif: string; // CSS class motif when image missing
  plate?: string;
};

function fromAurora(key: keyof typeof auroraCardImagery): DashboardImage {
  const img = auroraCardImagery[key];
  return { src: img.src, alt: img.alt, motif: img.motif, plate: img.plate };
}

export const dashboardImages = {
  hero: fromAurora("hero"),
  narrative: fromAurora("templates.narrative"),
  dialogue: fromAurora("templates.dialogue"),
  commercial: fromAurora("templates.commercial"),
  music: fromAurora("templates.music"),
  animation: fromAurora("templates.animation"),
  explainer: fromAurora("templates.explainer"),
  documentary: fromAurora("templates.documentary"),
  social: fromAurora("templates.social"),
  trailer: fromAurora("templates.trailer"),
  talkingAvatar: fromAurora("templates.talkingAvatar"),
  director: fromAurora("workspaces.director"),
  timeline: {
    src: "/images/hero/Timeline_Anadriya_4-3.png",
    alt: "Adept UI Timeline Generator — Anadriya",
    motif: "motif-timeline",
    plate: "plate-aurora",
  },
  editor: fromAurora("workspaces.editor"),
  magi: {
    src: "/images/hero/MAGI_Editor_Hero_Korri.png",
    alt: "Adept UI MAGI Editor — Korri",
    motif: "motif-edit",
    plate: "plate-aurora",
  },
  script: fromAurora("workspaces.script"),
  spatial: fromAurora("workspaces.spatial"),
  imagegen: fromAurora("workspaces.imagegen"),
  video: fromAurora("workspaces.video"),
  library: fromAurora("workspaces.library"),
  avatar: fromAurora("workspaces.avatar"),
  audio: fromAurora("workspaces.audio"),
  brand: fromAurora("workspaces.brand"),
  voice: fromAurora("workspaces.voice"),
  posecraft: fromAurora("workspaces.posecraft"),
  oneFrame: fromAurora("workspaces.oneFrame"),
  threeFrame: fromAurora("workspaces.threeFrame"),
  characterCreator: fromAurora("workspaces.characterCreator"),
  scriptwriter: fromAurora("workspaces.scriptwriter"),
  createProject: fromAurora("surfaces.createProject"),
} as const satisfies Record<string, DashboardImage>;

/**
 * @deprecated Soft UI labels only. M3.1a source of truth is project type slugs
 * in `projectTypes.ts` / backend project type catalog.
 */
export const PRODUCTION_TYPES = [
  "Short Film",
  "Feature Film",
  "Series Episode",
  "Commercial",
  "Music Video",
  "Social Video",
  "Animation",
  "Educational / Explainer",
  "Documentary",
  "Trailer",
  "Talking Avatar",
  "Custom",
] as const;

/** @deprecated Prefer PrimaryProjectType slugs from projectTypes.ts */
export type ProductionType = (typeof PRODUCTION_TYPES)[number];

export type ProjectTemplateDef = {
  id: string;
  title: string;
  description: string;
  type: ProductionType;
  primaryProjectType: string;
  image: DashboardImage;
  defaults: {
    aspect?: string;
    storyboard_style?: string;
    resolution?: string;
    fps?: number;
    /** Subtype traits forwarded to createProject (e.g. web_series, brand_ad). */
    projectTraits?: string[];
  };
};

export const PROJECT_TEMPLATES: readonly ProjectTemplateDef[] = [
  {
    id: "narrative",
    title: "Narrative Film",
    description: "Script, storyboard, spatial planning, coverage, and Director timeline.",
    type: "Short Film",
    primaryProjectType: "short_film",
    image: dashboardImages.narrative,
    defaults: { aspect: "2.39:1", storyboard_style: "Pencil storyboard", resolution: "1080p" },
  },
  {
    id: "dialogue",
    title: "Dialogue Scene",
    description: "Two-character blocking, standard coverage, reaction shots, and lip-sync prep.",
    type: "Series Episode",
    primaryProjectType: "television_episodic",
    image: dashboardImages.dialogue,
    defaults: { aspect: "16:9", storyboard_style: "Grayscale cinematic", resolution: "1080p" },
  },
  {
    id: "commercial",
    title: "Product Film",
    description: "Product consistency, controlled camera movement, clean commercial lighting.",
    type: "Commercial",
    primaryProjectType: "commercial",
    image: dashboardImages.commercial,
    defaults: { aspect: "16:9", storyboard_style: "Color concept frame", resolution: "1080p" },
  },
  {
    id: "music",
    title: "Music Video",
    description: "Rhythm-focused shot planning, visual experimentation, and performance coverage.",
    type: "Music Video",
    primaryProjectType: "music_video",
    image: dashboardImages.music,
    defaults: { aspect: "16:9", storyboard_style: "Color concept frame", resolution: "1080p", fps: 24 },
  },
  {
    id: "animation",
    title: "Animation",
    description: "Character Profiles, storyboard-first workflow, and stylized generation.",
    type: "Animation",
    primaryProjectType: "animation",
    image: dashboardImages.animation,
    defaults: { aspect: "16:9", storyboard_style: "Anime storyboard", resolution: "1080p" },
  },
  {
    id: "explainer",
    title: "Explainer",
    description:
      "Clear script beats, on-screen captions, diagram frames, and Co-Director educational planning.",
    type: "Educational / Explainer",
    primaryProjectType: "educational_explainer",
    image: dashboardImages.explainer,
    defaults: { aspect: "16:9", storyboard_style: "Color concept frame", resolution: "1080p", fps: 24 },
  },
  {
    id: "documentary",
    title: "Documentary",
    description: "Interview structure, B-roll planning, archive honesty, and observational coverage.",
    type: "Documentary",
    primaryProjectType: "documentary",
    image: dashboardImages.documentary,
    defaults: { aspect: "16:9", storyboard_style: "Grayscale cinematic", resolution: "1080p", fps: 24 },
  },
  {
    id: "social",
    title: "Social Short",
    description: "Hook-first short-form cuts, captions, CTA pacing, and vertical-ready delivery.",
    type: "Social Video",
    primaryProjectType: "social_media",
    image: dashboardImages.social,
    defaults: { aspect: "9:16", storyboard_style: "Color concept frame", resolution: "1080p", fps: 30 },
  },
  {
    id: "trailer",
    title: "Cinematic Trailer",
    description: "Cold open, escalation beats, title reveal, and release-card trailer structure.",
    type: "Trailer",
    primaryProjectType: "video_cinematic_trailer",
    image: dashboardImages.trailer,
    defaults: { aspect: "16:9", storyboard_style: "Color concept frame", resolution: "1080p", fps: 24 },
  },
  {
    id: "talking-avatar",
    title: "Talking Avatar",
    description: "Character Profile, voice, lip-sync presenter workflow, and caption-ready delivery.",
    type: "Talking Avatar",
    primaryProjectType: "talking_avatar",
    image: dashboardImages.talkingAvatar,
    defaults: { aspect: "16:9", storyboard_style: "Color concept frame", resolution: "1080p", fps: 24 },
  },
  {
    id: "web-series",
    title: "Web Series",
    description: "Episode-based series with recurring characters, serialized story beats, and season planning.",
    type: "Series Episode",
    primaryProjectType: "series",
    image: dashboardImages.dialogue,
    defaults: { aspect: "16:9", storyboard_style: "Grayscale cinematic", resolution: "1080p", fps: 24, projectTraits: ["web_series"] },
  },
  {
    id: "brand-ad",
    title: "Brand Ad",
    description: "Brand-led commercial with identity, logo reveal, CTA, and multi-format delivery.",
    type: "Commercial",
    primaryProjectType: "commercial",
    image: dashboardImages.commercial,
    defaults: { aspect: "16:9", storyboard_style: "Color concept frame", resolution: "1080p", fps: 24, projectTraits: ["brand_ad"] },
  },
];

export function relativeTime(iso?: string | null): string {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "—";
  const sec = Math.round((Date.now() - t) / 1000);
  if (sec < 60) return "Just now";
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
  if (sec < 604800) return `${Math.floor(sec / 86400)}d ago`;
  return new Date(iso).toLocaleDateString();
}
