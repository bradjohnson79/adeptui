/** ORDER 14 SFX Director Intent — bind reports/ORDER14_SFX_INTENT_CONTRACT.md v1.2 */
export type SfxTemporalIntent = {
  durationSec: number;
  pace: "slow" | "normal" | "fast" | "frantic" | null;
  eventCount: number | null;
  continuous: boolean | null;
};

export type SfxDirectorIntent = {
  physicalEvent: string;
  material: string;
  context: string;
  temporal: SfxTemporalIntent;
  negatives: string[];
  refinementOps: string[];
  intensity?: string;
  distance?: "close" | "medium" | "far" | "";
  environment?: string;
  reverb?: "none" | "dry" | "small" | "medium" | "large" | "more" | "less" | "";
  perspective?: "close" | "intimate" | "wide" | "otS" | "pov" | "";
  adherence?: "strict" | "balanced" | "loose" | "";
};

/** @deprecated alias */
export type SfxStructuredIntent = SfxDirectorIntent;

export type SfxFieldHonor = "native" | "prompt" | "partial" | "soft" | "no";

export type SfxAdvancedFieldMeta = {
  key: string;
  label: string;
  honor: SfxFieldHonor;
  hint: string;
};

/** Honest Advanced labels per MMAudio matrix in contract §2. */
export const SFX_ADVANCED_FIELD_META: SfxAdvancedFieldMeta[] = [
  { key: "physicalEvent", label: "Physical event", honor: "prompt", hint: "Prompt-influenced (not a native MMAudio control)" },
  { key: "material", label: "Material", honor: "prompt", hint: "Prompt-influenced (not a native MMAudio control)" },
  { key: "context", label: "Context", honor: "prompt", hint: "Prompt-influenced (not a native MMAudio control)" },
  { key: "environment", label: "Environment", honor: "prompt", hint: "Prompt-influenced (not a native MMAudio control)" },
  { key: "eventCount", label: "Event count", honor: "prompt", hint: "Prompt-influenced (not a native MMAudio control)" },
  { key: "pace", label: "Pace", honor: "prompt", hint: "Prompt-influenced (not a native MMAudio control)" },
  { key: "continuous", label: "Continuous", honor: "prompt", hint: "Prompt-influenced (not a native MMAudio control)" },
  { key: "distance", label: "Distance", honor: "prompt", hint: "Prompt-influenced (not a native MMAudio control)" },
  { key: "perspective", label: "Perspective", honor: "prompt", hint: "Prompt-influenced (not a native MMAudio control)" },
  { key: "reverb", label: "Reverb", honor: "partial", hint: "Prompt-only on MMAudio — no true IR/reverb send" },
  { key: "adherence", label: "Adherence", honor: "soft", hint: "Compiler strictness only; model may still drift" },
  { key: "negatives", label: "Negatives", honor: "partial", hint: "Folded into avoid / negative prompt text when supported" },
];

export function honorBadge(honor: SfxFieldHonor): string {
  switch (honor) {
    case "native":
      return "Native";
    case "prompt":
      return "Prompt-influenced";
    case "partial":
      return "Partial";
    case "soft":
      return "Soft";
    default:
      return "Unsupported";
  }
}

/** Full Owner refine ops (contract §9). */
export const SFX_OWNER_REFINE_OPS = [
  "too_soft",
  "too_loud",
  "too_short",
  "too_long",
  "wrong_material",
  "wrong_sound",
  "more_impacts",
  "fewer_impacts",
  "more_reverb",
  "less_reverb",
  "more_aggressive",
  "more_subtle",
  "regenerate_similar",
  "more_material",
  "less_ambience",
] as const;

export type SfxRefineOp = (typeof SFX_OWNER_REFINE_OPS)[number];

export type SfxRefineButton = {
  op: SfxRefineOp;
  label: string;
};

export const SFX_REFINE_BUTTONS: SfxRefineButton[] = [
  { op: "too_soft", label: "Too Soft" },
  { op: "too_loud", label: "Too Loud" },
  { op: "too_short", label: "Too Short" },
  { op: "too_long", label: "Too Long" },
  { op: "wrong_material", label: "Wrong Material" },
  { op: "wrong_sound", label: "Wrong Sound" },
  { op: "more_impacts", label: "More Impacts" },
  { op: "fewer_impacts", label: "Fewer Impacts" },
  { op: "more_reverb", label: "More Reverb" },
  { op: "less_reverb", label: "Less Reverb" },
  { op: "more_aggressive", label: "More Aggressive" },
  { op: "more_subtle", label: "More Subtle" },
  { op: "regenerate_similar", label: "Regenerate Similar" },
  { op: "more_material", label: "More Material" },
  { op: "less_ambience", label: "Less Ambience" },
];

/** @deprecated — all Owner ops are live in UI; routes may still 404 until Systems ping */
export const SFX_PUBLISHED_REFINE_OPS = SFX_OWNER_REFINE_OPS;
export const SFX_PENDING_REFINE_OPS = [] as const;

export const SFX_PHYSICAL_EVENTS = [
  "door_slam",
  "door_close_soft",
  "door_knock",
  "footsteps_walk",
  "footsteps_run",
  "footsteps_stomp",
  "footsteps",
  "glass_place",
  "glass_break",
  "electrical_spark",
  "car_door",
  "chair_scrape",
  "thunder",
  "rain_window",
  "cloth_rustle",
  "keyboard_type",
  "explosion",
  "generic",
] as const;

export const SFX_MATERIALS = [
  "",
  "wood",
  "metal",
  "heavy steel",
  "glass",
  "concrete",
  "hardwood",
  "leather",
  "cloth",
  "gravel",
  "rigid steel industrial grating",
] as const;

export const SFX_PACES = ["slow", "normal", "fast", "frantic"] as const;
export const SFX_DISTANCES = ["close", "medium", "far"] as const;
export const SFX_REVERBS = ["none", "dry", "small", "medium", "large", "more", "less"] as const;
export const SFX_PERSPECTIVES = ["close", "intimate", "wide", "otS", "pov"] as const;
export const SFX_ADHERENCE = ["strict", "balanced", "loose"] as const;

export function defaultSfxIntent(args: {
  physicalEvent?: string;
  durationSec: number;
  intensity?: string;
}): SfxDirectorIntent {
  return {
    physicalEvent: args.physicalEvent || "",
    material: "",
    context: "",
    temporal: {
      durationSec: args.durationSec,
      pace: null,
      eventCount: null,
      continuous: null,
    },
    negatives: [],
    refinementOps: [...SFX_OWNER_REFINE_OPS],
    intensity: args.intensity ? String(args.intensity).toLowerCase() : undefined,
    distance: "",
    environment: "",
    reverb: "",
    perspective: "",
    adherence: "",
  };
}

export function mergeSfxIntent(
  current: SfxDirectorIntent,
  patch: Partial<SfxDirectorIntent> & { temporal?: Partial<SfxTemporalIntent> },
): SfxDirectorIntent {
  return {
    ...current,
    ...patch,
    temporal: {
      ...current.temporal,
      ...(patch.temporal || {}),
    },
    negatives: patch.negatives ?? current.negatives,
    refinementOps: patch.refinementOps ?? current.refinementOps,
  };
}

export function isPublishedRefineOp(op: string): boolean {
  return (SFX_OWNER_REFINE_OPS as readonly string[]).includes(op);
}

export function toGenerateIntentPayload(intent: SfxDirectorIntent, args: {
  prompt: string;
  eventType?: string;
  durationSec: number;
  intensity: string;
  candidateCount: number;
}) {
  const physicalEvent = args.eventType || intent.physicalEvent || "";
  return {
    physicalEvent,
    material: intent.material || undefined,
    context: intent.context || undefined,
    temporal: {
      durationSec: args.durationSec,
      pace: intent.temporal.pace || undefined,
      eventCount: intent.temporal.eventCount ?? undefined,
      continuous: intent.temporal.continuous ?? undefined,
    },
    negatives: intent.negatives.length ? intent.negatives : undefined,
    refinementOps: intent.refinementOps,
    intensity: (intent.intensity || args.intensity || "").toLowerCase() || undefined,
    distance: intent.distance || undefined,
    environment: intent.environment || undefined,
    reverb: intent.reverb || undefined,
    perspective: intent.perspective || undefined,
    adherence: intent.adherence || undefined,
    prompt: args.prompt,
    candidateCount: args.candidateCount,
  };
}
