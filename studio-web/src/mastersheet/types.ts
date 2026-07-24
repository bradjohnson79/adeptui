/**
 * Scene Master Sheet / Whole-Scene Package
 *
 * Master Sheet = what exists in the scene (structured production data).
 * Spatial = where things are.
 * Storyboard = how framed.
 * Director = assembled timeline.
 * Ingredients Render is one OUTPUT of this structured source — never prompt as a collage/mood board.
 */

export type IngredientPriority = "Required" | "Preferred" | "Optional" | "Background" | "Exclude";

export type IngredientKind =
  | "character"
  | "wardrobe"
  | "prop"
  | "environment"
  | "camera"
  | "lighting"
  | "color_mood"
  | "action"
  | "style"
  | "other";

export type MasterSheetIngredient = {
  id: string;
  kind: IngredientKind;
  label: string;
  description?: string;
  priority: IngredientPriority;
  profile_id?: string | null;
  asset_id?: string | null;
  notes?: string;
  spatial_ref?: string | null;
  uncertain?: boolean;
};

export type MasterSheetState = {
  id: string; // A, B, C…
  label: string;
  notes?: string;
};

export type MasterSheetVersion = {
  version: string; // v1, v2…
  created_at: string;
  note?: string;
  snapshot: Omit<SceneMasterSheet, "versions" | "history">;
};

export type SceneMasterSheet = {
  id: string;
  project_id: string;
  scene_id: string;
  title: string;
  /** Scene Authority — approved as source of truth */
  approved_authority: boolean;
  state_id: string;
  states: MasterSheetState[];
  version: string;
  versions: MasterSheetVersion[];
  ingredients: MasterSheetIngredient[];
  prompt: string;
  negative_prompt: string;
  links: {
    script_scene_id?: string | null;
    spatial_map_id?: string | null;
    storyboard_panel_ids?: string[];
    director_usage?: string | null;
  };
  created_at: string;
  updated_at: string;
};

export function emptyMasterSheet(projectId: string, sceneId: string, title = "Scene Master Sheet"): SceneMasterSheet {
  const now = new Date().toISOString();
  return {
    id: `ms-${sceneId}`,
    project_id: projectId,
    scene_id: sceneId,
    title,
    approved_authority: false,
    state_id: "A",
    states: [{ id: "A", label: "Primary" }],
    version: "v1",
    versions: [],
    ingredients: [],
    prompt: "",
    negative_prompt: "",
    links: {},
    created_at: now,
    updated_at: now,
  };
}

/** Build final-scene prompts — NEVER mention collage / mood board / grid / reference sheet / panels / white background */
export function buildPromptsFromSheet(sheet: SceneMasterSheet): { prompt: string; negative_prompt: string } {
  const chars = sheet.ingredients.filter((i) => i.kind === "character" && i.priority !== "Exclude");
  const wardrobe = sheet.ingredients.filter((i) => i.kind === "wardrobe" && i.priority !== "Exclude");
  const props = sheet.ingredients.filter((i) => i.kind === "prop" && i.priority !== "Exclude");
  const env = sheet.ingredients.filter((i) => i.kind === "environment" && i.priority !== "Exclude");
  const cam = sheet.ingredients.filter((i) => i.kind === "camera" && i.priority !== "Exclude");
  const light = sheet.ingredients.filter((i) => i.kind === "lighting" && i.priority !== "Exclude");
  const mood = sheet.ingredients.filter((i) => i.kind === "color_mood" && i.priority !== "Exclude");
  const action = sheet.ingredients.filter((i) => i.kind === "action" && i.priority !== "Exclude");
  const style = sheet.ingredients.filter((i) => i.kind === "style" && i.priority !== "Exclude");

  const parts: string[] = [];
  if (action.length) parts.push(action.map((a) => a.description || a.label).join("; "));
  if (chars.length) {
    parts.push(
      chars
        .map((c) => {
          const w = wardrobe.filter((w) => w.label.toLowerCase().includes(c.label.toLowerCase()) || !w.label);
          const wtxt = w.length ? ` wearing ${w.map((x) => x.label).join(", ")}` : "";
          return `${c.description || c.label}${wtxt}`;
        })
        .join("; ")
    );
  } else if (wardrobe.length) {
    parts.push(wardrobe.map((w) => w.description || w.label).join(", "));
  }
  if (env.length) parts.push(`in ${env.map((e) => e.description || e.label).join(", ")}`);
  if (props.length) parts.push(`with ${props.map((p) => p.description || p.label).join(", ")}`);
  if (light.length) parts.push(light.map((l) => l.description || l.label).join(", "));
  if (cam.length) parts.push(cam.map((c) => c.description || c.label).join(", "));
  if (mood.length) parts.push(mood.map((m) => m.description || m.label).join(", "));
  if (style.length) parts.push(style.map((s) => s.description || s.label).join(", "));

  const prompt =
    sheet.prompt?.trim() ||
    parts.filter(Boolean).join(". ") ||
    "A complete cinematic scene with coherent characters, environment, and lighting.";

  const negBits = [
    "collage",
    "mood board",
    "reference sheet",
    "character sheet",
    "grid layout",
    "multi-panel",
    "storyboard panels",
    "white background",
    "identity drift",
    "inconsistent faces",
    "split screen",
    "contact sheet",
  ];
  const exclude = sheet.ingredients.filter((i) => i.priority === "Exclude").map((i) => i.label);
  const negative_prompt =
    sheet.negative_prompt?.trim() ||
    [...negBits, ...exclude, "blurry", "low quality", "watermark"].join(", ");

  return { prompt, negative_prompt };
}

export function validateSheet(sheet: SceneMasterSheet): { level: string; text: string }[] {
  const issues: { level: string; text: string }[] = [];
  if (!sheet.ingredients.some((i) => i.kind === "character" && i.priority === "Required")) {
    issues.push({ level: "warn", text: "No Required character ingredient" });
  }
  if (!sheet.ingredients.some((i) => i.kind === "environment")) {
    issues.push({ level: "warn", text: "No environment ingredient" });
  }
  if (!sheet.prompt && !sheet.ingredients.length) {
    issues.push({ level: "bad", text: "Empty master sheet — add ingredients or a prompt" });
  }
  const { prompt } = buildPromptsFromSheet(sheet);
  if (/collage|mood board|reference sheet|white background/i.test(prompt)) {
    issues.push({ level: "bad", text: "Prompt mentions collage/mood-board language — remove it" });
  }
  return issues;
}
