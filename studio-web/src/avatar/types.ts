/**
 * Avatar Studio — talking digital avatars as film performances.
 * Character/Profile → Appearance → Voice → Performance → Lip Sync → Avatar Video → Director
 *
 * Voice this pass: metadata + uploaded audio (TTS providers stubbed, not executed).
 */

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
  profile_id?: string | null;
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
  model_id: string;
  prompt: string;
  negative_prompt: string;
  source_video_asset_id?: string | null;
  source_still_asset_id?: string | null;
  mouth_mask: MouthMaskState;
  lip_sync_method: "external" | "native" | "none";
  takes: AvatarTake[];
  preset_id?: string | null;
  links: {
    script_segment_id?: string | null;
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
    profile_id: null,
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
    model_id: "ltx_2_3",
    prompt: "",
    negative_prompt:
      "identity drift, teeth distortion, frozen face, overactive facial motion, mouth drift, cropped chin, background warping, duplicate characters, blurry, low quality",
    source_video_asset_id: null,
    source_still_asset_id: null,
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
  if (session.look.wardrobe) parts.push(`wearing ${session.look.wardrobe}`);
  if (session.look.expression) parts.push(`${session.look.expression} expression`);
  if (session.performance.tone) parts.push(`${session.performance.tone} performance`);
  if (session.background_notes) parts.push(session.background_notes);
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

export function validateAvatarSession(session: AvatarSession): { level: string; text: string }[] {
  const issues: { level: string; text: string }[] = [];
  if (!session.character_profile_id && !session.character_name && !session.source_still_asset_id) {
    issues.push({ level: "warn", text: "Identity reference missing — attach Character Profile or still" });
  }
  if (!session.voice.audio_asset_id && session.mode !== "talking_portrait") {
    issues.push({ level: "warn", text: "Voice audio not attached (required before lip sync)" });
  }
  if (!session.voice.audio_asset_id && session.lip_sync_method === "external") {
    issues.push({ level: "bad", text: "Audio required for external lip-sync method" });
  }
  if (!session.dialogue_original.trim() && !session.dialogue_spoken.trim() && !session.voice.audio_asset_id) {
    issues.push({ level: "warn", text: "Dialogue empty" });
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
