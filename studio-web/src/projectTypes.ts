/**
 * M3.1a Project Types — frontend catalog for the new-project selector.
 * Backend `/api/templates-presets/project-types` is the source of truth when the
 * feature flag is on; these constants keep the UI usable offline / flag-off.
 */

/** @deprecated Soft UI labels only — not the M3.1a source of truth. Prefer PRIMARY_PROJECT_TYPES. */
export const LEGACY_PRODUCTION_TYPES = [
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

export type LegacyProductionType = (typeof LEGACY_PRODUCTION_TYPES)[number];

export const LEGACY_TO_SLUG: Record<string, string> = {
  "Short Film": "short_film",
  "Feature Film": "feature_film",
  "Series Episode": "television_episodic",
  Commercial: "commercial",
  "Music Video": "music_video",
  "Social Video": "social_media",
  Animation: "animation",
  "Educational / Explainer": "educational_explainer",
  Documentary: "documentary",
  Trailer: "video_cinematic_trailer",
  "Talking Avatar": "talking_avatar",
  Custom: "custom",
};

export type PrimaryProjectType = {
  slug: string;
  displayName: string;
  subtypes?: { slug: string; displayName: string }[];
  traitOptions?: string[];
  prominent?: boolean;
};

export const PRIMARY_PROJECT_TYPES: PrimaryProjectType[] = [
  { slug: "feature_film", displayName: "Feature Film" },
  { slug: "short_film", displayName: "Short Film", prominent: true },
  {
    slug: "series",
    displayName: "Series",
    subtypes: [
      { slug: "web_series", displayName: "Web Series" },
      { slug: "television_episodic", displayName: "Television Series" },
      { slug: "animated_series", displayName: "Animated Series" },
      { slug: "docuseries", displayName: "Docuseries" },
      { slug: "limited_series", displayName: "Limited Series" },
    ],
    traitOptions: ["animation", "educational", "vertical_derivatives"],
  },
  { slug: "documentary", displayName: "Documentary" },
  {
    slug: "animation",
    displayName: "Animation",
    subtypes: [{ slug: "anime", displayName: "Anime" }],
    traitOptions: ["anime", "educational"],
  },
  { slug: "talking_avatar", displayName: "Talking Avatar" },
  {
    slug: "commercial",
    displayName: "Commercial",
    prominent: true,
    subtypes: [{ slug: "brand_ad", displayName: "Brand Ad" }],
  },
  { slug: "music_video", displayName: "Music Video", prominent: true },
  {
    slug: "social_media",
    displayName: "Social Media",
    prominent: true,
    subtypes: [
      { slug: "youtube_short", displayName: "YouTube Short" },
      { slug: "tiktok", displayName: "TikTok" },
      { slug: "instagram_reel", displayName: "Instagram Reel" },
      { slug: "facebook_video", displayName: "Facebook Video" },
      { slug: "vertical_advertisement", displayName: "Vertical Advertisement" },
      { slug: "multi_platform_campaign", displayName: "Multi-Platform Campaign" },
    ],
  },
  { slug: "youtube_creator", displayName: "YouTube / Creator Video" },
  { slug: "educational_explainer", displayName: "Educational / Explainer" },
  { slug: "storyboard_previs", displayName: "Storyboard / Previsualization" },
  { slug: "game_cinematic", displayName: "Game Cinematic" },
  {
    slug: "video_cinematic_trailer",
    displayName: "Video / Cinematic Trailer",
    prominent: true,
    subtypes: [
      { slug: "film_trailer", displayName: "Film Trailer" },
      { slug: "series_trailer", displayName: "Series Trailer" },
      { slug: "cinematic_game_trailer", displayName: "Cinematic Game Trailer" },
      { slug: "teaser_trailer", displayName: "Teaser Trailer" },
      { slug: "social_trailer_cut", displayName: "Social Trailer Cut" },
      { slug: "concept_trailer", displayName: "Concept Trailer" },
    ],
    traitOptions: ["social_media", "vertical_derivatives", "animation"],
  },
  { slug: "custom", displayName: "Custom" },
];

export function resolveCreateType(primarySlug: string, subtypeSlug?: string | null): string {
  return (subtypeSlug && subtypeSlug.trim()) || primarySlug || "custom";
}
