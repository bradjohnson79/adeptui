/** Typed Aurora card imagery registry — photos/SVG under public/images/ui; CSS plates as fallback. */

export type AuroraCardKey =
  | "templates.narrative"
  | "templates.dialogue"
  | "templates.commercial"
  | "templates.music"
  | "templates.animation"
  | "templates.explainer"
  | "templates.documentary"
  | "templates.social"
  | "templates.trailer"
  | "templates.talkingAvatar"
  | "workspaces.director"
  | "workspaces.script"
  | "workspaces.spatial"
  | "workspaces.imagegen"
  | "workspaces.video"
  | "workspaces.library"
  | "workspaces.avatar"
  | "workspaces.audio"
  | "workspaces.brand"
  | "workspaces.voice"
  | "workspaces.posecraft"
  | "workspaces.oneFrame"
  | "workspaces.threeFrame"
  | "workspaces.characterCreator"
  | "workspaces.scriptwriter"
  | "workspaces.bible"
  | "workspaces.characters"
  | "workspaces.editor"
  | "workspaces.codirector"
  | "surfaces.toolsHub"
  | "surfaces.sourceManager"
  | "surfaces.enhance"
  | "surfaces.createProject"
  | "empty.projects"
  | "empty.characters"
  | "empty.library"
  | "hero";

export type AuroraCardImage = {
  key: AuroraCardKey;
  /** Local path under public/ — never remote */
  src: string;
  alt: string;
  plate: string;
  motif: string;
};

export const auroraCardImagery: Record<AuroraCardKey, AuroraCardImage> = {
  hero: {
    key: "hero",
    src: "/images/ui/hero/Adept_UI_Hero_header.webp",
    alt: "Cinematic AI film production environment with aurora lighting",
    plate: "aurora-plate aurora-plate--hero",
    motif: "motif-set",
  },
  "templates.narrative": {
    key: "templates.narrative",
    src: "/images/ui/templates/template-narrative.jpg",
    alt: "Narrative film set with cinema camera and clapperboard",
    plate: "aurora-plate aurora-plate--narrative",
    motif: "motif-narrative",
  },
  "templates.dialogue": {
    key: "templates.dialogue",
    src: "/images/ui/templates/template-dialogue.jpg",
    alt: "Two-character cinematic dialogue scene",
    plate: "aurora-plate aurora-plate--dialogue",
    motif: "motif-dialogue",
  },
  "templates.commercial": {
    key: "templates.commercial",
    src: "/images/ui/templates/template-commercial.jpg",
    alt: "Premium product film lighting setup",
    plate: "aurora-plate aurora-plate--commercial",
    motif: "motif-commercial",
  },
  "templates.music": {
    key: "templates.music",
    src: "/images/ui/templates/template-music.jpg",
    alt: "Music video stage performance under dramatic lights",
    plate: "aurora-plate aurora-plate--music",
    motif: "motif-music",
  },
  "templates.animation": {
    key: "templates.animation",
    src: "/images/ui/templates/template-animation.jpg",
    alt: "Animation production desk with character concept art",
    plate: "aurora-plate aurora-plate--animation",
    motif: "motif-animation",
  },
  "templates.explainer": {
    key: "templates.explainer",
    src: "/images/ui/templates/template-explainer.jpg",
    alt: "Educational explainer workstation with clear diagram frames and captions",
    plate: "aurora-plate aurora-plate--explainer",
    motif: "motif-explainer",
  },
  "templates.documentary": {
    key: "templates.documentary",
    src: "/images/ui/templates/template-documentary.jpg",
    alt: "Documentary interview and archive research setup",
    plate: "aurora-plate aurora-plate--documentary",
    motif: "motif-documentary",
  },
  "templates.social": {
    key: "templates.social",
    src: "/images/ui/templates/template-social.jpg",
    alt: "Social short vertical video production desk",
    plate: "aurora-plate aurora-plate--social",
    motif: "motif-social",
  },
  "templates.trailer": {
    key: "templates.trailer",
    src: "/images/ui/templates/template-trailer.jpg",
    alt: "Cinematic trailer screening room with dramatic light",
    plate: "aurora-plate aurora-plate--trailer",
    motif: "motif-trailer",
  },
  "templates.talkingAvatar": {
    key: "templates.talkingAvatar",
    src: "/images/ui/templates/template-talking-avatar.jpg",
    alt: "Talking avatar presenter workstation with voice waveform",
    plate: "aurora-plate aurora-plate--avatar",
    motif: "motif-imagegen",
  },
  "workspaces.director": {
    key: "workspaces.director",
    src: "/images/ui/workspaces/ws-director.jpg",
    alt: "Director control room with timeline and camera monitors",
    plate: "aurora-plate aurora-plate--director",
    motif: "motif-director",
  },
  "workspaces.script": {
    key: "workspaces.script",
    src: "/images/ui/workspaces/ws-script.jpg",
    alt: "Screenplay pages and storyboard sketches on a production desk",
    plate: "aurora-plate aurora-plate--script",
    motif: "motif-script",
  },
  "workspaces.spatial": {
    key: "workspaces.spatial",
    src: "/images/ui/workspaces/ws-spatial.jpg",
    alt: "Top-down spatial blocking map of a film set",
    plate: "aurora-plate aurora-plate--spatial",
    motif: "motif-spatial",
  },
  "workspaces.imagegen": {
    key: "workspaces.imagegen",
    src: "/images/ui/workspaces/ws-imagegen.jpg",
    alt: "Concept still glowing on an ImageGen workstation",
    plate: "aurora-plate aurora-plate--imagegen",
    motif: "motif-imagegen",
  },
  "workspaces.video": {
    key: "workspaces.video",
    src: "/images/ui/workspaces/ws-video.jpg",
    alt: "Cinema camera with motion frames for text-to-video",
    plate: "aurora-plate aurora-plate--video",
    motif: "motif-video",
  },
  "workspaces.library": {
    key: "workspaces.library",
    src: "/images/ui/workspaces/ws-library.jpg",
    alt: "Contact sheet wall of production stills and clips",
    plate: "aurora-plate aurora-plate--library",
    motif: "motif-library",
  },
  "workspaces.avatar": {
    key: "workspaces.avatar",
    src: "/images/ui/workspaces/ws-avatar.jpg",
    alt: "Cinematic speaking portrait for Avatar Studio",
    plate: "aurora-plate aurora-plate--avatar",
    motif: "motif-imagegen",
  },
  "workspaces.audio": {
    key: "workspaces.audio",
    src: "/images/ui/workspaces/ws-audio.jpg",
    alt: "Audio studio console and waveform",
    plate: "aurora-plate aurora-plate--tools",
    motif: "motif-music",
  },
  "workspaces.brand": {
    key: "workspaces.brand",
    src: "/images/ui/workspaces/ws-brand.jpg",
    alt: "Brand identity board with campaign art and logo mark",
    plate: "aurora-plate aurora-plate--commercial",
    motif: "motif-commercial",
  },
  "workspaces.voice": {
    key: "workspaces.voice",
    src: "/images/ui/workspaces/ws-voice.jpg",
    alt: "Voice performance waveform and character dialogue booth",
    plate: "aurora-plate aurora-plate--dialogue",
    motif: "motif-dialogue",
  },
  "workspaces.posecraft": {
    key: "workspaces.posecraft",
    src: "/images/ui/workspaces/ws-posecraft.jpg",
    alt: "PoseCraft character posing stage with motion arcs and camera guides",
    plate: "aurora-plate aurora-plate--avatar",
    motif: "motif-imagegen",
  },
  "workspaces.oneFrame": {
    key: "workspaces.oneFrame",
    src: "/images/ui/workspaces/ws-one-frame.jpg",
    alt: "Single cinematic keyframe on a motion workstation with film strip accent",
    plate: "aurora-plate aurora-plate--video",
    motif: "motif-video",
  },
  "workspaces.threeFrame": {
    key: "workspaces.threeFrame",
    src: "/images/ui/workspaces/ws-three-frame.jpg",
    alt: "Start, middle, and end storyboard frames arranged for motion planning",
    plate: "aurora-plate aurora-plate--director",
    motif: "motif-director",
  },
  "workspaces.characterCreator": {
    key: "workspaces.characterCreator",
    src: "/images/ui/workspaces/ws-character-creator.jpg",
    alt: "Character design desk with portrait references, wardrobe swatches, and voice waveform",
    plate: "aurora-plate aurora-plate--avatar",
    motif: "motif-imagegen",
  },
  "workspaces.scriptwriter": {
    key: "workspaces.scriptwriter",
    src: "/images/ui/workspaces/ws-scriptwriter.jpg",
    alt: "Professional screenplay pages with scene headings and dialogue on a production desk",
    plate: "aurora-plate aurora-plate--script",
    motif: "motif-script",
  },
  "workspaces.bible": {
    key: "workspaces.bible",
    src: "/images/ui/workspaces/ws-bible.svg",
    alt: "Production notebook and continuity bible",
    plate: "aurora-plate aurora-plate--narrative",
    motif: "motif-narrative",
  },
  "workspaces.characters": {
    key: "workspaces.characters",
    src: "/images/ui/workspaces/ws-characters.svg",
    alt: "Character concept portraits",
    plate: "aurora-plate aurora-plate--avatar",
    motif: "motif-imagegen",
  },
  "workspaces.editor": {
    key: "workspaces.editor",
    src: "/images/ui/workspaces/ws-editor.jpg",
    alt: "Editing bay with timeline monitors and color scopes",
    plate: "aurora-plate aurora-plate--director",
    motif: "motif-director",
  },
  "workspaces.codirector": {
    key: "workspaces.codirector",
    src: "/images/ui/workspaces/ws-codirector.svg",
    alt: "Co-Director AI assistant workspace",
    plate: "aurora-plate aurora-plate--hero",
    motif: "motif-set",
  },
  "surfaces.toolsHub": {
    key: "surfaces.toolsHub",
    src: "/images/ui/workspaces/ws-tools.svg",
    alt: "Generation tools workbench",
    plate: "aurora-plate aurora-plate--tools",
    motif: "motif-imagegen",
  },
  "surfaces.sourceManager": {
    key: "surfaces.sourceManager",
    src: "/images/ui/workspaces/ws-sources.svg",
    alt: "Source and model management console",
    plate: "aurora-plate aurora-plate--sources",
    motif: "motif-library",
  },
  "surfaces.enhance": {
    key: "surfaces.enhance",
    src: "/images/ui/cards/enhance.svg",
    alt: "Before and after enhancement frame",
    plate: "aurora-plate aurora-plate--tools",
    motif: "motif-imagegen",
  },
  "surfaces.createProject": {
    key: "surfaces.createProject",
    src: "/images/ui/cards/create-project-screenplay.jpg",
    alt: "Screenplay title page on a dark production desk with soft cinematic lighting",
    plate: "aurora-plate aurora-plate--script",
    motif: "motif-script",
  },
  "empty.projects": {
    key: "empty.projects",
    src: "/images/ui/empty-states/empty-projects.svg",
    alt: "Empty projects illustration",
    plate: "aurora-plate aurora-plate--library",
    motif: "motif-library",
  },
  "empty.characters": {
    key: "empty.characters",
    src: "/images/ui/empty-states/empty-characters.svg",
    alt: "Empty characters illustration",
    plate: "aurora-plate aurora-plate--avatar",
    motif: "motif-imagegen",
  },
  "empty.library": {
    key: "empty.library",
    src: "/images/ui/empty-states/empty-library.svg",
    alt: "Empty library illustration",
    plate: "aurora-plate aurora-plate--library",
    motif: "motif-library",
  },
};

export function getAuroraCardImage(key: AuroraCardKey): AuroraCardImage {
  return auroraCardImagery[key];
}
