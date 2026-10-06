/**
 * Environment Creator planning model (Express + Standard shared surface).
 * Pure helpers: gating, serialize, draft persistence, Co-Director snapshot store.
 * Does not drive Spatial Map / Scene Creator Standard production flows.
 */
export const ENV_CREATOR_ASPECTS = ["1:1", "4:3", "3:4", "16:9", "9:16", "21:9"] as const;
export type EnvCreatorAspect = (typeof ENV_CREATOR_ASPECTS)[number];
export const ENV_CREATOR_ASPECT_DEFAULT: EnvCreatorAspect = "16:9";

export type EnvCreatorGeneratorId = "gpt-image-2";

export const ENV_CREATOR_GENERATORS: ReadonlyArray<{
  id: EnvCreatorGeneratorId;
  label: string;
  /** When false, option is listed disabled until the catalog/provider is ready. */
  catalogAvailable: boolean;
  unavailableReason: string | null;
}> = [
  {
    id: "gpt-image-2",
    label: "GPT Image 2",
    catalogAvailable: true,
    unavailableReason: null,
  },
];

export const ENV_CREATOR_GENERATOR_DEFAULT: EnvCreatorGeneratorId = "gpt-image-2";

export type EnvCreatorPropAssignment =
  | { kind: "environment_object" }
  | { kind: "used_by"; characterId: string };

export type EnvCreatorCharacterPlan = {
  characterId: string;
  name: string;
  thumbAssetId: string | null;
  crsAssetId: string | null;
  crsApproved: boolean;
};

export type EnvCreatorPropPlan = {
  propId: string;
  name: string;
  prsAssetId: string | null;
  thumbAssetId: string | null;
  assignment: EnvCreatorPropAssignment;
};

export type EnvCreatorStoryTheme = {
  label: string;
  source: "story" | "override" | "none";
  override: string;
};

export type EnvironmentCreatorPlanningState = {
  name: string;
  isGlobal: boolean;
  referenceImageAssetId: string | null;
  environmentPrompt: string;
  characters: EnvCreatorCharacterPlan[];
  props: EnvCreatorPropPlan[];
  storyTheme: EnvCreatorStoryTheme;
  aspectRatio: EnvCreatorAspect;
  generator: EnvCreatorGeneratorId;
  apiProvider: string;
  apiModelId: string;
  apiOfficialModelId: string;
  apiModelLabel: string;
};

export type EnvironmentCreatorSerializedPlan = {
  name?: string;
  isGlobal?: boolean;
  environmentPrompt: string;
  referenceImageAssetId?: string;
  storyTheme: string;
  aspectRatio: EnvCreatorAspect;
  generator: EnvCreatorGeneratorId;
  apiProvider?: string;
  apiModelId?: string;
  apiOfficialModelId?: string;
  apiModelLabel?: string;
  characters: Array<{ characterId: string; crsAssetId?: string }>;
  props: Array<{
    propId: string;
    prsAssetId?: string;
    assignment: "environment_object" | "used_by";
    characterId?: string;
  }>;
};

export const ENV_CREATOR_MAX_CHARACTERS = 4;
export const ENV_CREATOR_MAX_PROPS = 4;

export function emptyEnvironmentCreatorPlanning(): EnvironmentCreatorPlanningState {
  return {
    name: "",
    isGlobal: false,
    referenceImageAssetId: null,
    environmentPrompt: "",
    characters: [],
    props: [],
    storyTheme: { label: "", source: "none", override: "" },
    aspectRatio: ENV_CREATOR_ASPECT_DEFAULT,
    generator: ENV_CREATOR_GENERATOR_DEFAULT,
    apiProvider: "",
    apiModelId: "",
    apiOfficialModelId: "",
    apiModelLabel: "",
  };
}

export function resolveStoryThemeLabel(theme: EnvCreatorStoryTheme): string {
  const override = theme.override.trim();
  if (override) return override;
  return theme.label.trim();
}

export function serializeEnvironmentCreatorPlan(
  state: EnvironmentCreatorPlanningState,
): EnvironmentCreatorSerializedPlan {
  const ref = String(state.referenceImageAssetId || "").trim();
  return {
    ...(state.name.trim() ? { name: state.name.trim() } : {}),
    isGlobal: Boolean(state.isGlobal),
    environmentPrompt: state.environmentPrompt.trim(),
    ...(ref ? { referenceImageAssetId: ref } : {}),
    storyTheme: resolveStoryThemeLabel(state.storyTheme),
    aspectRatio: state.aspectRatio,
    generator: state.generator,
    ...(state.apiProvider ? { apiProvider: state.apiProvider } : {}),
    ...(state.apiModelId ? { apiModelId: state.apiModelId } : {}),
    ...(state.apiOfficialModelId ? { apiOfficialModelId: state.apiOfficialModelId } : {}),
    ...(state.apiModelLabel ? { apiModelLabel: state.apiModelLabel } : {}),
    characters: state.characters.map((c) => ({
      characterId: c.characterId,
      ...(c.crsAssetId ? { crsAssetId: c.crsAssetId } : {}),
    })),
    props: state.props.map((p) => ({
      propId: p.propId,
      ...(p.prsAssetId ? { prsAssetId: p.prsAssetId } : {}),
      assignment: p.assignment.kind === "used_by" ? "used_by" : "environment_object",
      ...(p.assignment.kind === "used_by" ? { characterId: p.assignment.characterId } : {}),
    })),
  };
}

export type EnvCreatorGateInput = {
  planning: EnvironmentCreatorPlanningState;
  /** Provider ready for selected generator (T2I / general). */
  providerReady: boolean | null;
  /** Provider ready for I2I when a reference image is present. */
  providerI2IReady?: boolean | null;
  /** Catalog availability for selected generator option. */
  generatorCatalogAvailable: boolean;
  generatorUnavailableReason?: string | null;
  /** False when the saved API provider is no longer configured. */
  selectedProviderAvailable?: boolean;
};

/**
 * Generate is active when: valid provider + aspect + (prompt non-empty OR reference image).
 * Characters / props / image are NOT required. Prompt required only when no reference.
 */
export function environmentCreatorGenerateBlockReason(input: EnvCreatorGateInput): string | null {
  const { planning } = input;
  const hasRef = Boolean(String(planning.referenceImageAssetId || "").trim());
  const hasPrompt = Boolean(planning.environmentPrompt.trim());
  if (!hasRef && !hasPrompt) {
    return "Add an environment description, or choose an optional reference image.";
  }
  if (!ENV_CREATOR_ASPECTS.includes(planning.aspectRatio)) {
    return "Choose a valid image aspect.";
  }
  if (input.selectedProviderAvailable === false) {
    return "This provider is currently unavailable. Choose another configured provider.";
  }
  if (!input.generatorCatalogAvailable) {
    return input.generatorUnavailableReason || "Selected image generator is not available.";
  }
  const hostedSelected = Boolean(planning.apiProvider && planning.apiModelId);
  if (!hostedSelected) {
    if (hasRef) {
      if (input.providerI2IReady === false || (input.providerI2IReady == null && input.providerReady === false)) {
        return "GPT Image 2 — Requires Setup. Add a Kie API key in Settings for image-to-image.";
      }
    } else if (input.providerReady === false) {
      return "GPT Image 2 — Requires Setup. Add a Kie API key in Settings.";
    }
  }
  return null;
}

export function canAddCharacter(count: number): boolean {
  return count < ENV_CREATOR_MAX_CHARACTERS;
}

export function canAddProp(count: number): boolean {
  return count < ENV_CREATOR_MAX_PROPS;
}

export function formatPropAssignmentLabel(
  assignment: EnvCreatorPropAssignment,
  characters: Array<{ characterId: string; name: string }>,
): string {
  if (assignment.kind === "environment_object") return "Environment Object";
  const hit = characters.find((c) => c.characterId === assignment.characterId);
  return hit ? `Used by ${hit.name}` : "Used by character";
}

export function buildEnvironmentPlanSummary(state: EnvironmentCreatorPlanningState): string[] {
  const lines: string[] = [];
  const ref = String(state.referenceImageAssetId || "").trim();
  if (state.name.trim()) lines.push(`Name: ${state.name.trim()}${state.isGlobal ? " (Global)" : ""}`);
  lines.push(ref ? `Reference image: ${ref.slice(0, 8)}…` : "Reference image: none (prompt-only)");
  const prompt = state.environmentPrompt.trim();
  lines.push(prompt ? `Description: ${prompt.slice(0, 120)}${prompt.length > 120 ? "…" : ""}` : "Description: (empty)");
  lines.push(
    state.characters.length
      ? `Characters (${state.characters.length}): ${state.characters.map((c) => c.name).join(", ")}`
      : "Characters: none",
  );
  lines.push(
    state.props.length
      ? `Props (${state.props.length}): ${state.props
          .map((p) => `${p.name} [${formatPropAssignmentLabel(p.assignment, state.characters)}]`)
          .join("; ")}`
      : "Props: none",
  );
  const theme = resolveStoryThemeLabel(state.storyTheme);
  const themeSource =
    state.storyTheme.override.trim()
      ? "override"
      : state.storyTheme.source === "story"
        ? "inherited from Story"
        : "none";
  lines.push(theme ? `Story theme: ${theme} (${themeSource})` : `Story theme: none (${themeSource})`);
  lines.push(`Aspect: ${state.aspectRatio}`);
  if (state.apiProvider) {
    const providerLabel =
      state.apiProvider === "kie" ? "kie.ai" : state.apiProvider === "fal" ? "fal.ai" : state.apiProvider === "wavespeed" ? "wavespeed.ai" : state.apiProvider;
    lines.push(`API Provider: ${providerLabel}`);
  }
  lines.push(`Generator: ${state.apiModelLabel || "GPT Image 2"}`);
  return lines;
}

const DRAFT_KEY_PREFIX = "adept_environment_creator_plan_";

export function environmentCreatorDraftKey(projectId: string): string {
  return `${DRAFT_KEY_PREFIX}${projectId}`;
}

export type EnvironmentCreatorDraftExtras = {
  boundSheetId?: string | null;
  savedSnapshot?: string | null;
};

export type EnvironmentCreatorDraftRecord = Partial<EnvironmentCreatorPlanningState> & EnvironmentCreatorDraftExtras;

export function loadEnvironmentCreatorDraft(projectId: string): EnvironmentCreatorDraftRecord | null {
  if (!projectId || typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(environmentCreatorDraftKey(projectId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as EnvironmentCreatorDraftRecord;
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
}

export function saveEnvironmentCreatorDraft(
  projectId: string,
  state: EnvironmentCreatorPlanningState,
  extras?: EnvironmentCreatorDraftExtras,
): void {
  if (!projectId || typeof window === "undefined") return;
  try {
    const payload: EnvironmentCreatorDraftRecord = {
      ...state,
      boundSheetId: extras?.boundSheetId ?? null,
      savedSnapshot: extras?.savedSnapshot ?? null,
    };
    window.localStorage.setItem(environmentCreatorDraftKey(projectId), JSON.stringify(payload));
  } catch {
    // storage unavailable
  }
}

export function environmentCreatorPersistSnapshot(state: EnvironmentCreatorPlanningState): string {
  return JSON.stringify({
    name: state.name.trim(),
    isGlobal: Boolean(state.isGlobal),
    referenceImageAssetId: String(state.referenceImageAssetId || "").trim() || null,
    environmentPrompt: state.environmentPrompt.trim(),
    characters: state.characters.map((c) => ({
      characterId: c.characterId,
      name: c.name,
      thumbAssetId: c.thumbAssetId,
      crsAssetId: c.crsAssetId,
      crsApproved: c.crsApproved,
    })),
    props: state.props.map((p) => ({
      propId: p.propId,
      name: p.name,
      prsAssetId: p.prsAssetId,
      thumbAssetId: p.thumbAssetId,
      assignment: p.assignment,
    })),
    storyThemeOverride: state.storyTheme.override.trim(),
    aspectRatio: state.aspectRatio,
    generator: state.generator,
  });
}

export function validateEnvironmentCreatorSave(
  state: EnvironmentCreatorPlanningState,
): { ok: true } | { ok: false; error: string; field: "name" } {
  if (!state.name.trim()) {
    return { ok: false, error: "Give the environment a name, then Save Environment.", field: "name" };
  }
  return { ok: true };
}

function asCharacterPlan(row: unknown): EnvCreatorCharacterPlan | null {
  if (!row || typeof row !== "object") return null;
  const rec = row as Record<string, unknown>;
  const characterId = String(rec.characterId || rec.character_id || "").trim();
  if (!characterId) return null;
  return {
    characterId,
    name: String(rec.name || "Character").trim() || "Character",
    thumbAssetId: String(rec.thumbAssetId || rec.thumb_asset_id || "").trim() || null,
    crsAssetId: String(rec.crsAssetId || rec.crs_asset_id || "").trim() || null,
    crsApproved: Boolean(rec.crsApproved || rec.crs_approved),
  };
}

function asPropPlan(row: unknown): EnvCreatorPropPlan | null {
  if (!row || typeof row !== "object") return null;
  const rec = row as Record<string, unknown>;
  const propId = String(rec.propId || rec.prop_id || "").trim();
  if (!propId) return null;
  const assignmentRaw = rec.assignment;
  let assignment: EnvCreatorPropAssignment = { kind: "environment_object" };
  if (assignmentRaw && typeof assignmentRaw === "object") {
    const kind = String((assignmentRaw as { kind?: string }).kind || "");
    const characterId = String((assignmentRaw as { characterId?: string }).characterId || "").trim();
    assignment =
      kind === "used_by" && characterId ? { kind: "used_by", characterId } : { kind: "environment_object" };
  } else if (String(assignmentRaw || "") === "used_by") {
    const characterId = String(rec.characterId || "").trim();
    assignment = characterId ? { kind: "used_by", characterId } : { kind: "environment_object" };
  }
  return {
    propId,
    name: String(rec.name || "Prop").trim() || "Prop",
    prsAssetId: String(rec.prsAssetId || rec.prs_asset_id || "").trim() || null,
    thumbAssetId: String(rec.thumbAssetId || rec.thumb_asset_id || "").trim() || null,
    assignment,
  };
}

export function planningFromSavedSheet(
  sheet: {
    name?: string;
    description?: string;
    isGlobal?: boolean;
    is_global?: boolean;
    profile?: { description?: string; storyPurpose?: string } | null;
    provenance?: { details?: Record<string, unknown> | null } | null;
  },
  fallback: EnvironmentCreatorPlanningState,
): EnvironmentCreatorPlanningState {
  const details = (sheet.provenance?.details || {}) as Record<string, unknown>;
  const plan = (details.environmentCreatorPlan || {}) as Record<string, unknown>;
  const storyRaw = plan.storyTheme;
  let storyTheme = fallback.storyTheme;
  if (storyRaw && typeof storyRaw === "object") {
    const rec = storyRaw as Record<string, unknown>;
    const source = rec.source === "story" || rec.source === "override" ? rec.source : fallback.storyTheme.source;
    storyTheme = {
      label: String(rec.label || fallback.storyTheme.label || ""),
      source,
      override: String(rec.override || ""),
    };
  } else if (typeof storyRaw === "string" && storyRaw.trim()) {
    storyTheme = { ...fallback.storyTheme, label: storyRaw.trim() };
  } else if (sheet.profile?.storyPurpose && sheet.profile.storyPurpose !== "Environment reference sheet") {
    storyTheme = { ...fallback.storyTheme, label: String(sheet.profile.storyPurpose) };
  }
  const aspect = String(plan.aspectRatio || fallback.aspectRatio || ENV_CREATOR_ASPECT_DEFAULT);
  const generator = fallback.generator || ENV_CREATOR_GENERATOR_DEFAULT;
  const characters = Array.isArray(plan.characters)
    ? plan.characters.map(asCharacterPlan).filter((row): row is EnvCreatorCharacterPlan => Boolean(row))
    : [];
  const props = Array.isArray(plan.props)
    ? plan.props.map(asPropPlan).filter((row): row is EnvCreatorPropPlan => Boolean(row))
    : [];
  const ref = String(plan.referenceImageAssetId || "").trim();
  return {
    ...fallback,
    name: String(plan.name || sheet.name || fallback.name || "").trim(),
    isGlobal: Boolean(plan.isGlobal ?? plan.is_global ?? sheet.isGlobal ?? sheet.is_global ?? fallback.isGlobal),
    environmentPrompt: String(
      plan.environmentPrompt || sheet.description || sheet.profile?.description || fallback.environmentPrompt || "",
    ),
    referenceImageAssetId: ref || fallback.referenceImageAssetId,
    characters,
    props,
    storyTheme,
    aspectRatio: ENV_CREATOR_ASPECTS.includes(aspect as EnvCreatorAspect)
      ? (aspect as EnvCreatorAspect)
      : fallback.aspectRatio,
    generator,
  };
}

export function buildEnvironmentCreatorSaveBody(
  state: EnvironmentCreatorPlanningState,
  sheetId: string | null,
): {
  sheetId?: string;
  name: string;
  description: string;
  environmentPrompt: string;
  isGlobal: boolean;
  is_global: boolean;
  referenceImageAssetId?: string;
  storyTheme: EnvCreatorStoryTheme;
  aspectRatio: EnvCreatorAspect;
  generator: EnvCreatorGeneratorId;
  characters: EnvCreatorCharacterPlan[];
  props: EnvCreatorPropPlan[];
  plan: Record<string, unknown>;
} {
  const serialized = serializeEnvironmentCreatorPlan(state);
  const name = state.name.trim();
  const prompt = state.environmentPrompt.trim();
  return {
    ...(sheetId ? { sheetId } : {}),
    name,
    description: prompt,
    environmentPrompt: prompt,
    isGlobal: Boolean(state.isGlobal),
    is_global: Boolean(state.isGlobal),
    ...(serialized.referenceImageAssetId ? { referenceImageAssetId: serialized.referenceImageAssetId } : {}),
    storyTheme: state.storyTheme,
    aspectRatio: state.aspectRatio,
    generator: state.generator,
    characters: state.characters,
    props: state.props,
    plan: {
      ...serialized,
      name,
      characters: state.characters,
      props: state.props,
      storyTheme: state.storyTheme,
    },
  };
}

/** In-memory Co-Director awareness store (same process as CD session). */
type PlanningListener = (snapshot: EnvironmentCreatorSerializedPlan | null) => void;
const planningByProject = new Map<string, EnvironmentCreatorSerializedPlan>();
const listeners = new Set<PlanningListener>();

export function publishEnvironmentCreatorPlanning(
  projectId: string,
  state: EnvironmentCreatorPlanningState | null,
): void {
  if (!projectId) return;
  if (!state) {
    planningByProject.delete(projectId);
    listeners.forEach((fn) => fn(null));
    return;
  }
  const snap = serializeEnvironmentCreatorPlan(state);
  planningByProject.set(projectId, snap);
  listeners.forEach((fn) => fn(snap));
}

export function getEnvironmentCreatorPlanningSnapshot(
  projectId: string,
): EnvironmentCreatorSerializedPlan | null {
  if (!projectId) return null;
  return planningByProject.get(projectId) || null;
}

export function subscribeEnvironmentCreatorPlanning(listener: PlanningListener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function extractCharacterThumbAndCrs(row: Record<string, unknown>): {
  thumbAssetId: string | null;
  crsAssetId: string | null;
  crsApproved: boolean;
  name: string;
  characterId: string;
} {
  const characterId = String(row.id || row.character_id || "").trim();
  const name = String(row.name || "Character").trim() || "Character";
  const status = String(row.approval_status || row.status || "").trim().toLowerCase();
  const crsAssetId = String(
    row.approved_asset_id ||
      row.approvedAssetId ||
      row.crs_asset_id ||
      row.crsAssetId ||
      row.hero_asset_id ||
      row.heroAssetId ||
      "",
  ).trim() || null;
  const thumbAssetId = String(
    row.thumbnail_asset_id ||
      row.thumbnailAssetId ||
      row.portrait_asset_id ||
      row.portraitAssetId ||
      row.reference_asset_id ||
      row.referenceAssetId ||
      crsAssetId ||
      "",
  ).trim() || null;
  const crsApproved = status === "approved" || Boolean(crsAssetId && (row.approved === true || status === "approved"));
  return { characterId, name, thumbAssetId, crsAssetId, crsApproved };
}

export function extractApprovedProp(row: Record<string, unknown>): {
  propId: string;
  name: string;
  prsAssetId: string | null;
  thumbAssetId: string | null;
} | null {
  const propId = String(row.id || row.prop_id || "").trim();
  if (!propId) return null;
  const name = String(row.name || row.display_label || row.tag || "Prop").trim() || "Prop";
  // Official PRS authority: Advanced sheet when complete, else structured ids,
  // else leftover notes marker on unsanitized rows, else primary/library still.
  const advancedSheetId = String(
    row.advanced_sheet_asset_id || row.advancedSheetAssetId || "",
  ).trim();
  const sheetStatus = String(
    row.advanced_sheet_status || row.advancedSheetStatus || "",
  )
    .trim()
    .toLowerCase();
  const notes = String(row.notes || "").trim();
  const notesPrsMatch = notes.match(/prsAssetId=(\S+)/);
  const notesPrsId = (notesPrsMatch?.[1] || "").trim();
  const primaryOrLibrary = String(
    row.approved_asset_id || row.approvedAssetId || row.library_asset_id || row.libraryAssetId || "",
  ).trim();
  const officialPrs =
    (sheetStatus === "complete" && advancedSheetId ? advancedSheetId : "") ||
    notesPrsId ||
    primaryOrLibrary ||
    "";
  const prsAssetId = officialPrs || null;
  const thumbAssetId = String(
    row.thumbnail_asset_id ||
      row.thumbnailAssetId ||
      row.reference_asset_id ||
      row.referenceAssetId ||
      primaryOrLibrary ||
      (sheetStatus === "complete" ? advancedSheetId : "") ||
      "",
  ).trim() || null;
  return { propId, name, prsAssetId, thumbAssetId };
}
