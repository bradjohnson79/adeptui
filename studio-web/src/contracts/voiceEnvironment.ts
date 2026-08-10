/**
 * M5.2 frozen contracts — Voice Environment.
 * Do not change field names without primary approval (Law 16).
 */

export type VoiceEnvironmentSource =
  | "manual"
  | "codirector"
  | "scene"
  | "location"
  | "spatial_map";

export type VoiceEnvironmentRenderStatus =
  | "queued"
  | "processing"
  | "preview_ready"
  | "completed"
  | "failed";

export type VoiceEnvironmentWallaLevel = "subtle" | "moderate" | "present";
export type VoiceEnvironmentWallaDistance = "near" | "mid" | "far";
export type VoiceEnvironmentWallaBehavior = "steady" | "reactive" | "intermittent";

/** Processing latency contract — required on every preview/render. */
export type VoiceEnvironmentTiming = {
  speechStartOffsetMs: number;
  processingLatencyMs: number;
  tailDurationMs: number;
  dryDurationMs: number;
  processedDurationMs: number;
};

export type VoiceEnvironmentProfile = {
  id: string;
  projectId: string;
  characterId?: string | null;
  sceneId?: string | null;
  locationId?: string | null;
  name: string;
  spacePreset: string;
  customSpacePrompt?: string | null;
  distancePreset: string;
  customDistancePrompt?: string | null;
  directionPreset: string;
  customDirectionPrompt?: string | null;
  tonePreset: string;
  customTonePrompt?: string | null;
  devicePreset: string;
  customDevicePrompt?: string | null;
  wallaPreset: string;
  wallaLevel?: VoiceEnvironmentWallaLevel | null;
  wallaDistance?: VoiceEnvironmentWallaDistance | null;
  wallaBehavior?: VoiceEnvironmentWallaBehavior | null;
  customWallaPrompt?: string | null;
  source: VoiceEnvironmentSource;
  createdAt: string;
  updatedAt: string;
};

export type VoiceEnvironmentRender = {
  id: string;
  projectId: string;
  characterId: string;
  performanceRecordId: string;
  performanceTakeId: string;
  environmentProfileId: string;
  dryAudioAssetId: string;
  processedAudioAssetId?: string | null;
  roomToneAssetId?: string | null;
  wallaAssetId?: string | null;
  timing: VoiceEnvironmentTiming;
  status: VoiceEnvironmentRenderStatus;
  approved: boolean;
  errorCode?: string | null;
  errorMessage?: string | null;
  createdAt: string;
  updatedAt: string;
};

export type VoiceEnvironmentRecommendation = {
  profileDraft: Partial<VoiceEnvironmentProfile>;
  spaceLabel: string;
  distanceLabel: string;
  directionLabel: string;
  toneLabel: string;
  deviceLabel: string;
  wallaLabel: string;
  reason: string;
  evidence: {
    sceneId?: string | null;
    locationId?: string | null;
    spatialMapId?: string | null;
    environmentPrompt?: string | null;
  };
};

export type VoiceEnvironmentTimelineHandoff = {
  projectId: string;
  sceneId?: string | null;
  characterId: string;
  dialogueId?: string | null;
  voiceIdentityId?: string | null;
  performanceRecordId: string;
  performanceTakeId: string;
  environmentProfileId: string;
  environmentRenderId: string;
  dryAudioAssetId: string;
  processedAudioAssetId?: string | null;
  roomToneAssetId?: string | null;
  wallaAssetId?: string | null;
  timing: VoiceEnvironmentTiming;
  distancePreset: string;
  directionPreset: string;
  devicePreset: string;
  provenance: Record<string, unknown>;
};

export type VoiceEnvironmentLipSyncHandoff = {
  projectId: string;
  sceneId?: string | null;
  characterId: string;
  performanceRecordId: string;
  performanceTakeId: string;
  dryAudioAssetId: string;
  timing: VoiceEnvironmentTiming;
  /** Always dry-aligned; ignores reverb/ambience tails. */
  useDryTiming: true;
};

export type VoiceEnvironmentAudioStudioHandoff = {
  projectId: string;
  characterId: string;
  sceneId?: string | null;
  environmentProfileId: string;
  environmentRenderId: string;
  dryAudioAssetId: string;
  processedAudioAssetId?: string | null;
  roomToneAssetId?: string | null;
  wallaAssetId?: string | null;
  timing: VoiceEnvironmentTiming;
  approved: boolean;
  provenance: Record<string, unknown>;
};

export type VoiceEnvironmentErrorCode =
  | "VOICE_STUDIO_CHARACTER_REQUIRED"
  | "VOICE_IDENTITY_REQUIRED"
  | "VOICE_PERFORMANCE_REQUIRED"
  | "VOICE_ENVIRONMENT_RUNTIME_NOT_READY"
  | "VOICE_ENVIRONMENT_PREVIEW_FAILED"
  | "VOICE_ENVIRONMENT_RENDER_FAILED"
  | "VOICE_ENVIRONMENT_PROFILE_INVALID"
  | "VOICE_ENVIRONMENT_SCENE_NOT_FOUND"
  | "VOICE_ENVIRONMENT_SPATIAL_CONTEXT_MISSING"
  | "VOICE_ENVIRONMENT_TIMELINE_HANDOFF_FAILED"
  | "VOICE_ENVIRONMENT_LIPSYNC_HANDOFF_FAILED"
  | "VOICE_ENVIRONMENT_AUDIO_STUDIO_HANDOFF_FAILED";

/** Outer Voice Studio stage order (M5.2). */
export type VoiceStudioWorkspaceTab =
  | "identity"
  | "performance"
  | "environment"
  | "sceneDialogue"
  | "takes";

export const VOICE_STUDIO_STAGE_ORDER: readonly {
  id: VoiceStudioWorkspaceTab;
  label: string;
  tip: string;
}[] = [
  {
    id: "identity",
    label: "Voice Identity",
    tip: "Who the character sounds like.",
  },
  {
    id: "performance",
    label: "Voice Performance",
    tip: "How the character performs the line.",
  },
  {
    id: "environment",
    label: "Voice Environment",
    tip: "Where and how the voice is heard in the scene.",
  },
  {
    id: "sceneDialogue",
    label: "Scene Dialogue",
    tip: "What the character says.",
  },
  {
    id: "takes",
    label: "Takes",
    tip: "Generated and approved results.",
  },
] as const;

/** Frozen Co-Director tool IDs (read). */
export const VOICE_ENVIRONMENT_READ_TOOLS = [
  "voice.inspect_studio",
  "voice.inspect_character",
  "voice.inspect_identity",
  "voice.inspect_performance",
  "voice.inspect_dialogue",
  "voice.inspect_takes",
  "voice_environment.inspect_scene",
  "voice_environment.inspect_location",
  "voice_environment.inspect_spatial_map",
  "voice_environment.inspect_performance",
  "voice_environment.inspect_profile",
  "voice_environment.list_profiles",
  "voice_environment.list_renders",
  "voice_environment.inspect_runtime",
  "voice_environment.inspect_timeline_link",
  "voice_environment.inspect_lipsync_link",
  "voice_environment.preview_plan",
] as const;

/** Frozen Co-Director tool IDs (proposal-gated). */
export const VOICE_ENVIRONMENT_MUTATION_TOOLS = [
  "voice.select_character",
  "voice.create_character_handoff",
  "voice.create_identity_plan",
  "voice.create_performance_plan",
  "voice_environment.create_profile",
  "voice_environment.update_profile",
  "voice_environment.apply_codirector_recommendation",
  "voice_environment.create_preview",
  "voice_environment.render",
  "voice_environment.approve",
  "voice_environment.create_alternate",
  "voice_environment.apply_to_scene",
  "voice_environment.prepare_timeline",
  "voice_environment.prepare_lipsync",
  "voice_environment.open_audio_studio",
  "voice_environment.request_repair",
] as const;
