/** Spatial Atlas Look — appearance only. Same object UI and Co-Director use. */

export type AtlasStyle =
  | "auto_match_source"
  | "realistic"
  | "cinematic"
  | "architectural"
  | "clean_concept"
  | "blueprint"
  | "stylized";

export type AtlasDetail = "low" | "balanced" | "high";
export type AtlasSourceStrength = "low" | "balanced" | "strong";
export type AtlasPresentation = "roofless" | "cutaway" | "floor_plan";
export type AtlasLighting = "match_source" | "neutral" | "bright_planning" | "cinematic";

export type SpatialAtlasLook = {
  style: AtlasStyle;
  detail: AtlasDetail;
  sourceAppearance: AtlasSourceStrength;
  presentation: AtlasPresentation;
  lighting: AtlasLighting;
  showGrid: boolean;
};

export const DEFAULT_ATLAS_LOOK: SpatialAtlasLook = {
  style: "auto_match_source",
  detail: "balanced",
  sourceAppearance: "balanced",
  presentation: "roofless",
  lighting: "match_source",
  showGrid: false,
};

export function normalizeAtlasLook(raw?: Partial<SpatialAtlasLook> | null): SpatialAtlasLook {
  return { ...DEFAULT_ATLAS_LOOK, ...(raw || {}) };
}

export function interpretAtlasLookUtterance(text: string, current?: Partial<SpatialAtlasLook> | null): SpatialAtlasLook {
  const look = normalizeAtlasLook(current);
  const blob = String(text || "").toLowerCase();
  if (/blueprint|technical drawing/.test(blob)) look.style = "blueprint";
  else if (/architect/.test(blob)) look.style = "architectural";
  else if (/concept art/.test(blob)) look.style = "clean_concept";
  else if (/styliz/.test(blob)) look.style = "stylized";
  else if (/cinematic/.test(blob) && !/bright/.test(blob)) look.style = "cinematic";
  else if (/realistic|photoreal/.test(blob)) look.style = "realistic";
  else if (/match (the )?(source|corridor|location)|metallic appearance/.test(blob)) {
    look.style = "auto_match_source";
    look.sourceAppearance = "strong";
  }
  if (/less detail|simpler|low detail/.test(blob)) look.detail = "low";
  else if (/more detail|high detail/.test(blob)) look.detail = "high";
  if (/match .{0,24}(metal|material|appearance) closely|strong(er)? source/.test(blob)) look.sourceAppearance = "strong";
  else if (/less (source|reference)|weaker source/.test(blob)) look.sourceAppearance = "low";
  if (/brighten|brighter|planning (view|light)/.test(blob)) look.lighting = "bright_planning";
  else if (/neutral light/.test(blob)) look.lighting = "neutral";
  if (/floor plan/.test(blob)) look.presentation = "floor_plan";
  else if (/cutaway/.test(blob)) look.presentation = "cutaway";
  if (/show (the )?grid|1 ?m grid/.test(blob)) look.showGrid = true;
  else if (/hide (the )?grid|no grid/.test(blob)) look.showGrid = false;
  return look;
}

export const STYLE_OPTIONS: Array<{ id: AtlasStyle; label: string }> = [
  { id: "auto_match_source", label: "Auto / Match Source" },
  { id: "realistic", label: "Realistic" },
  { id: "cinematic", label: "Cinematic" },
  { id: "architectural", label: "Architectural" },
  { id: "clean_concept", label: "Clean Concept Art" },
  { id: "blueprint", label: "Blueprint / Technical" },
  { id: "stylized", label: "Stylized" },
];

export const DETAIL_OPTIONS: Array<{ id: AtlasDetail; label: string }> = [
  { id: "low", label: "Low" },
  { id: "balanced", label: "Balanced" },
  { id: "high", label: "High" },
];

export const STRENGTH_OPTIONS: Array<{ id: AtlasSourceStrength; label: string }> = [
  { id: "low", label: "Low" },
  { id: "balanced", label: "Balanced" },
  { id: "strong", label: "Strong" },
];

export const PRESENTATION_OPTIONS: Array<{ id: AtlasPresentation; label: string }> = [
  { id: "roofless", label: "Roofless" },
  { id: "cutaway", label: "Cutaway" },
  { id: "floor_plan", label: "Clean Floor Plan" },
];

export const LIGHTING_OPTIONS: Array<{ id: AtlasLighting; label: string }> = [
  { id: "match_source", label: "Match Source" },
  { id: "neutral", label: "Neutral" },
  { id: "bright_planning", label: "Bright Planning View" },
  { id: "cinematic", label: "Cinematic" },
];
