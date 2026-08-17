/**
 * Avatar Studio — talking digital avatars as film performances.
 * Character/Profile → Appearance → Voice → Performance → Lip Sync → Avatar Video → Director
 *
 * Voice this pass: metadata + uploaded audio (TTS providers stubbed, not executed).
 */
import type {
  CharacterCandidate,
  CharacterProfile,
  CharacterReference,
} from "../components/character/types";

export type AvatarMode =
  | "talking_portrait"
  | "cinematic_character"
  | "full_body"
  | "stylized"
  | "existing_video_lipsync";

export type PerformanceTone =
  | "calm"
  | "friendly"
  | "serious"
  | "excited"
  | "suspicious"
  | "angry"
  | "sad"
  | "confident"
  | "nervous"
  | "restrained"
  | "custom";

export type AvatarLook = {
  id: string;
  name: string;
  framing: string;
  wardrobe: string;
  expression: string;
  pose: string;
  camera_angle: string;
  lens: string;
  background: string;
  lighting: string;
  style: string;
  aspect: string;
  portrait_asset_id?: string | null;
  fullbody_asset_id?: string | null;
  environment_profile_id?: string | null;
};

export type VoiceProfileData = {
  provider: string;
  model: string;
  speaker_id: string;
  language: string;
  accent: string;
  tone: string;
  pitch: string;
  pace: string;
  emotional_range: string;
  pronunciation_notes: string;
  stability: string;
  usage_rights: string;
  /** Required for execute this pass */
  audio_asset_id?: string | null;
  fallback_audio_asset_id?: string | null;
  profile_id?: string | null;
  approved_record_id?: string | null;
  approved_take_id?: string | null;
};

export type PerformanceDirection = {
  tone: PerformanceTone;
  custom_tone?: string;
  eye_contact: string;
  head_movement: string;
  blink_frequency: string;
  shoulder_movement: string;
  gesture_intensity: string;
  breathing: string;
  facial_expressiveness: string;
  energy: string;
  stillness: string;
};

export type AvatarTake = {
  id: string;
  label: string;
  asset_id?: string | null;
  scene_id?: string | null;
  status: "draft" | "preview" | "final" | "failed";
  favorite?: boolean;
  approved?: boolean;
  performance_note?: string;
  created_at: string;
};

export type AvatarGenerationSectionStatus =
  | "pending"
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "retake_requested"
  | "approved";

export type AvatarPresentationPlanSection = {
  id: string;
  label: string;
  summary: string;
  delivery: string;
  gaze: string;
  gesture: string;
  pacing: string;
  emphasis: string;
  posture: string;
  pronunciation: string;
  transition: string;
  background: string;
  framing: string;
  retakeFocus: string;
  continuity: string;
  excerpt?: string;
  startMs?: number;
  endMs?: number;
};

export type AvatarPresentationPlan = {
  version: string;
  source?: string;
  summary: string;
  sectioningStrategy: string;
  sectionTargetSeconds: number;
  deliveryStyle: string;
  gazeStyle: string;
  gestureStyle: string;
  pacingStyle: string;
  chapterTransitionStyle: string;
  emphasisNotes: string;
  postureNotes: string;
  pronunciationNotes: string;
  backgroundRecommendation: string;
  framingRecommendation: string;
  continuityChecklist: string;
  retakeGuidance: string;
  sections: AvatarPresentationPlanSection[];
  updatedAt?: string;
};

export type AvatarJobStatus =
  | "planning"
  | "queued"
  | "generating"
  | "paused"
  | "assembling"
  | "completed"
  | "failed"
  | "cancelled";

export type AvatarGenerationSection = {
  id: string;
  order: number;
  scriptText: string;
  audioStartMs: number;
  audioEndMs: number;
  overlapBeforeMs?: number;
  overlapAfterMs?: number;
  continuationFrameAssetId?: string | null;
  outputVideoAssetId?: string | null;
  presentationPlan: Record<string, unknown>;
  status: AvatarGenerationSectionStatus;
  providerJobId?: string | null;
  errorCode?: string | null;
  errorMessage?: string | null;
  attempt?: number;
  retryCount?: number;
  updatedAt?: string;
  retakeNote?: string;
  retakeReason?: string;
  retakeActionType?: string;
  currentVersionId?: string;
  retakeRequest?: Record<string, unknown> | null;
  retakeHistory?: Array<Record<string, unknown>>;
  versionHistory?: Array<Record<string, unknown>>;
  lipsyncRepairPlan?: Record<string, unknown>;
};

export type AvatarTimelineProposal = {
  jobId: string;
  sessionId: string;
  placementMode: string;
  trackId: string;
  startMs: number;
  selectedSectionId?: string | null;
  replaceSectionId?: string | null;
  sectionIds: string[];
  readySectionIds: string[];
  clips: Array<Record<string, unknown>>;
  provenance: Record<string, unknown>;
  audioMix?: Record<string, unknown>;
  timelineWritten: boolean;
  createdAt: string;
};

export type AvatarProjectJob = {
  id: string;
  projectId: string;
  sessionId: string;
  avatarId: string;
  providerId: string;
  scriptSourceId?: string;
  audioAssetId: string;
  sections: AvatarGenerationSection[];
  assemblyState: string;
  requestedDurationMs: number;
  completedDurationMs: number;
  status: AvatarJobStatus;
  createdAt: string;
  updatedAt: string;
  sharedStyleProfileId?: string;
  identityProfileRef?: string;
  presentationPlan?: AvatarPresentationPlan;
  progress?: {
    totalSections: number;
    completedSections: number;
    failedSections: number;
    pendingSections: number;
  };
  transitionValidation?: {
    validated: boolean;
    notes?: string;
    updatedAt?: string | null;
  };
  lastError?: {
    code?: string;
    message?: string;
    sectionId?: string;
  };
  assembly?: {
    compositeVideoAssetId?: string | null;
    stub?: boolean;
    message?: string;
    validatedAt?: string | null;
    provenance?: Record<string, unknown>;
  };
  scriptSource?: Record<string, unknown>;
  voiceAsset?: Record<string, unknown>;
  audioMix?: Record<string, unknown>;
  timelineProposal?: AvatarTimelineProposal | null;
  timelinePlacements?: Array<Record<string, unknown>>;
  assemblyVersion?: number;
  retakeSummary?: Record<string, number>;
};

export type MouthMaskState = {
  placed: boolean;
  x?: number;
  y?: number;
  w?: number;
  h?: number;
  notes?: string;
};

export type AvatarSession = {
  id: string;
  project_id: string;
  name: string;
  mode: AvatarMode;
  character_profile_id?: string | null;
  character_name: string;
  continuity_lock: boolean;
  look: AvatarLook;
  voice: VoiceProfileData;
  dialogue_original: string;
  dialogue_spoken: string;
  dialogue_adaptation_accepted?: boolean | null;
  performance: PerformanceDirection;
  camera: {
    shot_size: string;
    lens: string;
    height: string;
    angle: string;
    movement: string;
    aspect: string;
  };
  background_mode: string;
  background_notes: string;
  input_mode?: "script" | "approved_voice";
  presentation_style?: string;
  framing_choice?: string;
  background_choice?: string;
  background_asset_id?: string | null;
  duration_class?: string;
  presentation_plan?: AvatarPresentationPlan;
  provider_mode?: "best_match" | "choose_provider" | "compare";
  provider_choice?: string | null;
  model_id: string;
  prompt: string;
  negative_prompt: string;
  source_video_asset_id?: string | null;
  source_still_asset_id?: string | null;
  active_job_id?: string | null;
  mouth_mask: MouthMaskState;
  lip_sync_method: "external" | "native" | "none";
  takes: AvatarTake[];
  preset_id?: string | null;
  links: {
    script_segment_id?: string | null;
    script_document_id?: string | null;
    script_scene_heading_id?: string | null;
    script_scene_id?: string | null;
    script_source_label?: string;
    script_revision_version?: number | null;
    voice_record_id?: string | null;
    voice_take_id?: string | null;
    storyboard_panel_id?: string | null;
    master_sheet_id?: string | null;
    scene_id?: string | null;
  };
  created_at: string;
  updated_at: string;
};

export const AVATAR_MODES: { id: AvatarMode; label: string; blurb: string }[] = [
  { id: "talking_portrait", label: "Talking Portrait", blurb: "Head-and-shoulders speaking clips" },
  { id: "cinematic_character", label: "Cinematic Character", blurb: "Film dialogue / close-ups with scene context" },
  { id: "full_body", label: "Full-Body Avatar", blurb: "Posture, gestures, speaking performance" },
  { id: "stylized", label: "Stylized Avatar", blurb: "Anime, illustration, 3D, cartoon" },
  { id: "existing_video_lipsync", label: "Existing Video Lip Sync", blurb: "Apply dialogue to an approved clip" },
];

export const AVATAR_PRESETS: {
  id: string;
  label: string;
  background_mode?: string;
  camera?: AvatarSession["camera"];
}[] = [
  {
    id: "studio_presenter",
    label: "Studio Presenter",
    background_mode: "solid",
    camera: { shot_size: "medium close-up", lens: "50mm", height: "eye level", angle: "direct-to-camera", movement: "static", aspect: "16:9" },
  },
  {
    id: "cinematic_closeup",
    label: "Cinematic Close-Up",
    background_mode: "environment",
    camera: { shot_size: "close-up", lens: "85mm", height: "eye level", angle: "three-quarter", movement: "slow push-in", aspect: "16:9" },
  },
  {
    id: "news_host",
    label: "News Host",
    background_mode: "solid",
    camera: { shot_size: "medium close-up", lens: "50mm", height: "eye level", angle: "direct-to-camera", movement: "static", aspect: "16:9" },
  },
  {
    id: "interview_subject",
    label: "Interview Subject",
    background_mode: "environment",
    camera: { shot_size: "medium shot", lens: "35mm", height: "eye level", angle: "slightly off-camera", movement: "static", aspect: "16:9" },
  },
  {
    id: "anime_speaker",
    label: "Anime Speaker",
    background_mode: "generated",
    camera: { shot_size: "medium close-up", lens: "35mm", height: "eye level", angle: "direct-to-camera", movement: "subtle", aspect: "16:9" },
  },
];

export function emptyLook(name = "Default Look"): AvatarLook {
  return {
    id: `look-${Date.now()}`,
    name,
    framing: "medium close-up",
    wardrobe: "",
    expression: "neutral",
    pose: "upright",
    camera_angle: "three-quarter",
    lens: "50mm",
    background: "neutral gray",
    lighting: "soft key, gentle fill",
    style: "cinematic live-action",
    aspect: "16:9",
  };
}

export function emptyVoice(): VoiceProfileData {
  return {
    provider: "upload",
    model: "",
    speaker_id: "",
    language: "en",
    accent: "",
    tone: "natural",
    pitch: "medium",
    pace: "moderate",
    emotional_range: "restrained",
    pronunciation_notes: "",
    stability: "high",
    usage_rights: "project",
    audio_asset_id: null,
    fallback_audio_asset_id: null,
    profile_id: null,
    approved_record_id: null,
    approved_take_id: null,
  };
}

export function emptyPerformance(): PerformanceDirection {
  return {
    tone: "restrained",
    eye_contact: "slightly off-camera",
    head_movement: "minimal",
    blink_frequency: "natural",
    shoulder_movement: "low",
    gesture_intensity: "low",
    breathing: "subtle",
    facial_expressiveness: "controlled",
    energy: "moderate",
    stillness: "high",
  };
}

export function emptyAvatarSession(projectId: string, name = "Avatar Session"): AvatarSession {
  const now = new Date().toISOString();
  return {
    id: `avs-${Date.now().toString(36)}`,
    project_id: projectId,
    name,
    mode: "talking_portrait",
    character_profile_id: null,
    character_name: "",
    continuity_lock: true,
    look: emptyLook(),
    voice: emptyVoice(),
    dialogue_original: "",
    dialogue_spoken: "",
    dialogue_adaptation_accepted: null,
    performance: emptyPerformance(),
    camera: {
      shot_size: "medium close-up",
      lens: "50mm",
      height: "eye level",
      angle: "direct-to-camera",
      movement: "static",
      aspect: "16:9",
    },
    background_mode: "solid",
    background_notes: "Neutral studio background",
    input_mode: "script",
    presentation_style: "direct_presenter",
    framing_choice: "medium_presenter",
    background_choice: "studio_gradient",
    background_asset_id: null,
    duration_class: "story_section",
    presentation_plan: {
      version: "m4.12",
      source: "manual",
      summary: "Plan this presenter section as clean, reviewable beats with clear continuity.",
      sectioningStrategy: "Break the script into creator-reviewable presenter beats.",
      sectionTargetSeconds: 6,
      deliveryStyle: "Clear, confident presenter delivery.",
      gazeStyle: "Hold steady eye contact on key lines.",
      gestureStyle: "Keep gestures compact and purposeful.",
      pacingStyle: "Measured pacing with short emphasis pauses.",
      chapterTransitionStyle: "Use a small breath and reset between sections.",
      emphasisNotes: "Save the strongest emphasis for pivots and the close.",
      postureNotes: "Stay upright with relaxed shoulders.",
      pronunciationNotes: "",
      backgroundRecommendation: "Soft studio gradient with clean separation.",
      framingRecommendation: "medium close-up",
      continuityChecklist: "Keep eye line, camera height, and background continuity consistent.",
      retakeGuidance: "Retake only the drifting section and preserve the handoff into the next beat.",
      sections: [],
      updatedAt: now,
    },
    provider_mode: "best_match",
    provider_choice: null,
    model_id: "ltx_2_5_distilled",
    prompt: "",
    negative_prompt:
      "identity drift, teeth distortion, frozen face, overactive facial motion, mouth drift, cropped chin, background warping, duplicate characters, blurry, low quality",
    source_video_asset_id: null,
    source_still_asset_id: null,
    active_job_id: null,
    mouth_mask: { placed: false },
    lip_sync_method: "external",
    takes: [],
    links: {},
    created_at: now,
    updated_at: now,
  };
}

export function estimateDialogueSeconds(text: string): number {
  const words = text.trim().split(/\s+/).filter(Boolean).length;
  if (!words) return 0;
  return Math.max(1.5, Math.round((words / 2.5) * 10) / 10);
}

export function buildAvatarPrompt(session: AvatarSession): { prompt: string; negative_prompt: string } {
  const parts: string[] = [];
  const name = session.character_name || "the character";
  parts.push(`${session.camera.shot_size} of ${name}`);
  if (session.presentation_style) parts.push(session.presentation_style.replace(/_/g, " "));
  if (session.look.wardrobe) parts.push(`wearing ${session.look.wardrobe}`);
  if (session.look.expression) parts.push(`${session.look.expression} expression`);
  if (session.performance.tone) parts.push(`${session.performance.tone} performance`);
  if (session.background_notes) parts.push(session.background_notes);
  if (session.duration_class) parts.push(`${session.duration_class.replace(/_/g, " ")} pacing`);
  parts.push(`${session.camera.lens} lens, ${session.camera.angle}, ${session.camera.movement}`);
  parts.push(session.look.lighting || "cinematic lighting");
  parts.push(session.look.style || "cinematic live-action realism");
  parts.push("stable identity, clean facial motion, coherent framing");

  const prompt = session.prompt?.trim() || parts.filter(Boolean).join(". ") + ".";
  const neg =
    session.negative_prompt?.trim() ||
    "identity drift, teeth distortion, frozen face, mouth drift, cropped chin, background warping, blurry";
  return { prompt, negative_prompt: neg };
}

export function resolvedAvatarAudioAssetId(session: AvatarSession): string | null {
  if ((session.input_mode || "script") === "approved_voice") {
    return session.voice?.audio_asset_id || null;
  }
  return session.voice?.fallback_audio_asset_id || session.voice?.audio_asset_id || null;
}

const HERO_STILL_ROLES = new Set([
  "hero_identity",
  "hero_portrait",
  "portrait",
  "canonical_front",
  "front",
]);
const SHEET_STILL_ROLES = new Set([
  "character_sheet",
  "sheet",
  "model_sheet",
  "master_sheet",
]);

function referenceAssetId(ref: CharacterReference & Record<string, unknown>): string | null {
  const raw = ref.asset_id ?? ref.assetId ?? (ref as { fileId?: unknown }).fileId ?? (ref as { file_id?: unknown }).file_id;
  if (typeof raw !== "string") return null;
  const trimmed = raw.trim();
  return trimmed ? trimmed : null;
}

function referenceRole(ref: CharacterReference & Record<string, unknown>): string {
  return String(ref.reference_role || (ref as { role?: unknown }).role || "");
}

export function pickApprovedCharacterStill(input: {
  profile?: (Partial<CharacterProfile> & Record<string, unknown>) | null;
  references?: Array<CharacterReference & Record<string, unknown>>;
  candidates?: Array<CharacterCandidate & Record<string, unknown>>;
}): { assetId: string; role: string } | null {
  const refs = input.references || [];
  const ranked = refs
    .map((ref) => {
      const role = referenceRole(ref);
      const approved = ref.approval_status === "approved" ? 8 : 0;
      const canonical = ref.canonical ? 4 : 0;
      const hero = HERO_STILL_ROLES.has(role) ? 16 : SHEET_STILL_ROLES.has(role) ? 12 : 0;
      return { ref, role, assetId: referenceAssetId(ref), score: approved + canonical + hero };
    })
    .filter((item) => item.assetId);
  ranked.sort((a, b) => b.score - a.score);

  const approvedIdentity = ranked.find(
    (item) =>
      item.ref.approval_status === "approved" &&
      (HERO_STILL_ROLES.has(item.role) || SHEET_STILL_ROLES.has(item.role) || item.ref.canonical),
  );
  if (approvedIdentity?.assetId) {
    return { assetId: approvedIdentity.assetId, role: approvedIdentity.role || "approved" };
  }

  const approvedOrCanonical = ranked.find(
    (item) => item.ref.approval_status === "approved" || item.ref.canonical,
  );
  if (approvedOrCanonical?.assetId) {
    return { assetId: approvedOrCanonical.assetId, role: approvedOrCanonical.role || "approved" };
  }

  for (const candidate of input.candidates || []) {
    const sheetId = candidate.sheetAssetId || candidate.assetId;
    if (typeof sheetId === "string" && sheetId.trim()) {
      return { assetId: sheetId.trim(), role: "sheet" };
    }
  }

  const profile = input.profile || {};
  for (const key of ["sheetAssetId", "sheet_asset_id", "hero_asset_id", "portrait_asset_id", "heroAssetId"]) {
    const value = profile[key];
    if (typeof value === "string" && value.trim()) {
      return { assetId: value.trim(), role: key };
    }
  }

  return ranked[0]?.assetId ? { assetId: ranked[0].assetId, role: ranked[0].role || "reference" } : null;
}

export function applyApprovedIdentityToSession(
  session: AvatarSession,
  identity: {
    characterId: string;
    characterName: string;
    stillAssetId?: string | null;
    stillRole?: string | null;
  },
): AvatarSession {
  const stillAssetId = identity.stillAssetId || session.source_still_asset_id || null;
  return {
    ...session,
    character_profile_id: identity.characterId,
    character_name: identity.characterName,
    source_still_asset_id: stillAssetId,
    look: {
      ...session.look,
      portrait_asset_id: stillAssetId || session.look.portrait_asset_id || null,
    },
    links: {
      ...session.links,
      master_sheet_id:
        identity.stillRole && SHEET_STILL_ROLES.has(identity.stillRole)
          ? stillAssetId
          : session.links.master_sheet_id || null,
    },
  };
}

export function validateAvatarSession(session: AvatarSession): { level: string; text: string }[] {
  const issues: { level: string; text: string }[] = [];
  const inputMode = session.input_mode || "script";
  const resolvedAudioAssetId = resolvedAvatarAudioAssetId(session);
  if (!session.character_profile_id && !session.character_name && !session.source_still_asset_id) {
    issues.push({ level: "warn", text: "Identity reference missing — attach Character Profile or still" });
  }
  if (
    inputMode === "approved_voice" &&
    (!session.voice.audio_asset_id || !session.voice.approved_record_id || !session.voice.approved_take_id)
  ) {
    issues.push({ level: "bad", text: "Approved Voice mode requires an approved Voice Studio take" });
  }
  if (!resolvedAudioAssetId && session.lip_sync_method === "external") {
    if (inputMode === "script") {
      issues.push({
        level: "warn",
        text: "Audio not attached — script mode can still plan without lip-sync audio",
      });
    } else {
      issues.push({ level: "bad", text: "Audio required for external lip-sync method" });
    }
  }
  if (!session.dialogue_original.trim() && !session.dialogue_spoken.trim() && !resolvedAudioAssetId) {
    if (inputMode === "script") {
      issues.push({ level: "bad", text: "Add the script for this presenter section before you generate." });
    } else {
      issues.push({ level: "warn", text: "Dialogue empty" });
    }
  }
  if (session.lip_sync_method === "external" && !session.mouth_mask.placed) {
    issues.push({ level: "warn", text: "Mouth mask requires user confirmation" });
  }
  if (session.mode === "existing_video_lipsync" && !session.source_video_asset_id) {
    issues.push({ level: "bad", text: "Source video required for Existing Video Lip Sync mode" });
  }
  if (!session.camera.shot_size) {
    issues.push({ level: "warn", text: "Camera framing incomplete" });
  }
  return issues;
}

export type AvatarRuntimeGateLabel = "Experimental" | "Not Installed" | "Needs Repair" | "Choose Runtime";

export type AvatarRuntimeGate = {
  id?: string;
  name?: string;
  label: AvatarRuntimeGateLabel;
};

export function avatarGenerateBlockers(
  session: AvatarSession,
  runtime: AvatarRuntimeGate | null,
): { level: string; text: string }[] {
  const issues = validateAvatarSession(session).filter((item) => item.level === "bad");
  const runtimeName = runtime?.name || runtime?.id || "Selected runtime";
  if (!runtime || runtime.label === "Choose Runtime") {
    issues.push({
      level: "bad",
      text: "No avatar runtime selected. Open Runtime Setup to install an avatar runtime.",
    });
    return issues;
  }
  if (runtime.label === "Not Installed") {
    issues.push({
      level: "bad",
      text:
        session.mode === "existing_video_lipsync"
          ? "MuseTalk 1.5 is not installed, so Existing Video Dubbing cannot be prepared."
          : `${runtimeName} is not installed. Open Runtime Setup to install it.`,
    });
  } else if (runtime.label === "Needs Repair") {
    issues.push({
      level: "bad",
      text: `${runtimeName} needs repair. Open Runtime Setup to repair it.`,
    });
  }
  return issues;
}

export function canGenerateAvatarSession(
  session: AvatarSession,
  runtime: AvatarRuntimeGate | null,
): boolean {
  return avatarGenerateBlockers(session, runtime).length === 0;
}

export function claimsLiveAvatarVideo(job: {
  status?: string;
  lastError?: { code?: string; message?: string } | null;
  sections?: Array<{ outputVideoAssetId?: string | null; errorCode?: string | null }>;
}): boolean {
  if (job.sections?.some((section) => section.outputVideoAssetId)) return true;
  const code = String(job.lastError?.code || "");
  if (code.includes("PROVIDER_NOT_CERTIFIED") || code.includes("PROVIDER_NOT_INSTALLED")) return false;
  return job.status === "completed" && !job.lastError;
}
