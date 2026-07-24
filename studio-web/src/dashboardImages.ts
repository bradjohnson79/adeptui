/** Central cinematic image registry — drop JPEGs into public/images/dashboard later. */
export type DashboardImage = {
  src: string;
  alt: string;
  attribution?: string;
  motif: string; // CSS class motif when image missing
};

export const dashboardImages = {
  hero: {
    src: "/images/dashboard/hero-film-set.jpg",
    alt: "Cinematic film production set with camera and monitors",
    motif: "motif-set",
  },
  narrative: {
    src: "/images/dashboard/template-narrative.jpg",
    alt: "Narrative film storyboard and script desk",
    motif: "motif-narrative",
  },
  dialogue: {
    src: "/images/dashboard/template-dialogue.jpg",
    alt: "Two-character dialogue scene blocking",
    motif: "motif-dialogue",
  },
  commercial: {
    src: "/images/dashboard/template-commercial.jpg",
    alt: "Clean commercial product lighting",
    motif: "motif-commercial",
  },
  music: {
    src: "/images/dashboard/template-music.jpg",
    alt: "Music video performance and lighting",
    motif: "motif-music",
  },
  animation: {
    src: "/images/dashboard/template-animation.jpg",
    alt: "Animation character design wall",
    motif: "motif-animation",
  },
  director: {
    src: "/images/dashboard/ws-director.jpg",
    alt: "Director monitors and editing timeline",
    motif: "motif-director",
  },
  script: {
    src: "/images/dashboard/ws-script.jpg",
    alt: "Screenplay pages and storyboard sketches",
    motif: "motif-script",
  },
  spatial: {
    src: "/images/dashboard/ws-spatial.jpg",
    alt: "Top-down spatial blocking map",
    motif: "motif-spatial",
  },
  imagegen: {
    src: "/images/dashboard/ws-imagegen.jpg",
    alt: "Cinematic concept still frame",
    motif: "motif-imagegen",
  },
  video: {
    src: "/images/dashboard/ws-video.jpg",
    alt: "Film camera and moving frame",
    motif: "motif-video",
  },
  library: {
    src: "/images/dashboard/ws-library.jpg",
    alt: "Visual contact sheet of production assets",
    motif: "motif-library",
  },
  avatar: {
    src: "/images/dashboard/ws-avatar.jpg",
    alt: "Cinematic speaking portrait of a character at camera",
    motif: "motif-imagegen",
  },
} as const satisfies Record<string, DashboardImage>;

export const PRODUCTION_TYPES = [
  "Short Film",
  "Feature Film",
  "Series Episode",
  "Commercial",
  "Music Video",
  "Social Video",
  "Animation",
  "Custom",
] as const;

export type ProductionType = (typeof PRODUCTION_TYPES)[number];

export const PROJECT_TEMPLATES = [
  {
    id: "narrative",
    title: "Narrative Film",
    description: "Script, storyboard, spatial planning, coverage, and Director timeline.",
    type: "Short Film" as ProductionType,
    image: dashboardImages.narrative,
    defaults: { aspect: "2.39:1", storyboard_style: "Pencil storyboard", resolution: "1080p" },
  },
  {
    id: "dialogue",
    title: "Dialogue Scene",
    description: "Two-character blocking, standard coverage, reaction shots, and lip-sync prep.",
    type: "Series Episode" as ProductionType,
    image: dashboardImages.dialogue,
    defaults: { aspect: "16:9", storyboard_style: "Grayscale cinematic", resolution: "1080p" },
  },
  {
    id: "commercial",
    title: "Product Film",
    description: "Product consistency, controlled camera movement, clean commercial lighting.",
    type: "Commercial" as ProductionType,
    image: dashboardImages.commercial,
    defaults: { aspect: "16:9", storyboard_style: "Color concept frame", resolution: "1080p" },
  },
  {
    id: "music",
    title: "Music Video",
    description: "Rhythm-focused shot planning, visual experimentation, and performance coverage.",
    type: "Music Video" as ProductionType,
    image: dashboardImages.music,
    defaults: { aspect: "16:9", storyboard_style: "Color concept frame", resolution: "1080p", fps: 24 },
  },
  {
    id: "animation",
    title: "Animation",
    description: "Character Profiles, storyboard-first workflow, and stylized generation.",
    type: "Animation" as ProductionType,
    image: dashboardImages.animation,
    defaults: { aspect: "16:9", storyboard_style: "Anime storyboard", resolution: "1080p" },
  },
] as const;

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
