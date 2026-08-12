/**
 * Neutral Structured Scene Spec — model-agnostic intermediate for prompt compilation.
 * Precedence (high→low): user instruction > shot overrides > master sheet > spatial >
 * script/storyboard > project rules > profiles > model KB > shared > defaults
 */
export type StructuredSceneSpec = {
  intention: string;
  mode: "creative" | "structured" | "model" | "advanced";
  model_id: string;
  task?: "text_to_video" | "image_to_video" | "ingredients_to_scene" | "storyboard_to_video" | string;
  characters: { name: string; description?: string; priority?: string }[];
  environment?: string;
  action?: string;
  camera?: string;
  lighting?: string;
  mood?: string;
  style?: string;
  motion?: string;
  duration_hint?: number;
  reference_asset_ids?: string[];
  negative_constraints?: string[];
  shot_overrides?: Record<string, string>;
  sources: { kind: string; id?: string; note?: string }[];
};

export type GenerationPackage = {
  version: string;
  model_id: string;
  mode: string;
  prompt: string;
  negative_prompt: string;
  citations: { path: string; title?: string }[];
  knowledge_version: string;
  validation: { ok: boolean; issues: string[] };
  explain: string[];
  spec: StructuredSceneSpec;
  created_at: string;
};

export function buildSpecFromContext(opts: {
  intention: string;
  mode?: StructuredSceneSpec["mode"];
  model_id?: string;
  masterSheet?: {
    ingredients?: {
      kind: string;
      label: string;
      description?: string;
      priority?: string;
      asset_id?: string | null;
    }[];
    prompt?: string;
    negative_prompt?: string;
    id?: string;
  } | null;
  sceneName?: string;
  spatialNote?: string;
}): StructuredSceneSpec {
  const ms = opts.masterSheet;
  const ings = ms?.ingredients || [];
  const by = (k: string) => ings.filter((i) => i.kind === k);
  return {
    intention: opts.intention,
    mode: opts.mode || "creative",
    model_id: opts.model_id || "ltx_2_5_distilled",
    characters: by("character").map((c) => ({
      name: c.label,
      description: c.description,
      priority: c.priority,
    })),
    environment: by("environment").map((e) => e.description || e.label).join("; ") || undefined,
    action: by("action").map((a) => a.description || a.label).join("; ") || opts.intention,
    camera: by("camera").map((c) => c.description || c.label).join("; ") || undefined,
    lighting: by("lighting").map((l) => l.description || l.label).join("; ") || undefined,
    mood: by("color_mood").map((m) => m.description || m.label).join("; ") || undefined,
    style: by("style").map((s) => s.description || s.label).join("; ") || undefined,
    reference_asset_ids: ings.map((i) => i.asset_id).filter(Boolean) as string[],
    negative_constraints: (ms?.negative_prompt || "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
    sources: [
      { kind: "user_intention", note: opts.intention },
      ...(ms ? [{ kind: "master_sheet", id: ms.id }] : []),
      ...(opts.sceneName ? [{ kind: "scene", note: opts.sceneName }] : []),
      ...(opts.spatialNote ? [{ kind: "spatial", note: opts.spatialNote }] : []),
    ],
  };
}
