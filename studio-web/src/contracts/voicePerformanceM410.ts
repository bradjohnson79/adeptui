export type VoicePerformanceDirectionMode = "codirector" | "manual";

export type VoicePerformanceTakeStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled"
  | "approved"
  | "rejected";

export type VoicePerformanceEmotionVectorKey =
  | "joy"
  | "sadness"
  | "anger"
  | "fear"
  | "surprise"
  | "disgust"
  | "contempt";

export type VoicePerformanceEmotionVector = Partial<Record<VoicePerformanceEmotionVectorKey, number>>;

export type VoicePerformanceEmotionSource =
  | "codirector"
  | "preset"
  | "emotional_reference_audio"
  | "voice_reference_emotion"
  | "advanced_mix";

export type VoicePerformancePlan = {
  source?: string;
  summary?: string;
  emotionLabel?: string;
  intensity?: string;
  delivery?: string;
  pacing?: string;
  breath?: string;
  emphasis?: string;
  subtext?: string;
  performanceReference?: string;
  notes?: string;
  editable?: boolean;
  presetId?: string;
  emotionVector?: VoicePerformanceEmotionVector;
  [key: string]: unknown;
};

export type VoicePerformanceEmotionPreset = {
  id: string;
  name: string;
  emotionVector: VoicePerformanceEmotionVector;
  intensity: string;
  delivery: string;
  pacing: string;
  breath: string;
  notes: string;
  summary: string;
};

export type VoicePerformanceTake = {
  id: string;
  recordId: string;
  takeNumber: number;
  label: string;
  jobId?: string | null;
  audioAssetId?: string | null;
  durationMs?: number | null;
  status: VoicePerformanceTakeStatus;
  directionSnapshot: Record<string, unknown>;
  generatedAt?: string | null;
  errorCode?: string | null;
  errorMessage?: string | null;
  createdAt: string;
  updatedAt: string;
};

export type VoicePerformanceRecord = {
  id: string;
  projectId: string;
  sceneId?: string | null;
  scriptDocumentId?: string | null;
  scriptElementId?: string | null;
  characterId: string;
  voiceIdentityId: string;
  voiceIdentityVersion?: string | null;
  dialogueText: string;
  language: string;
  directionMode: VoicePerformanceDirectionMode;
  performancePlan: VoicePerformancePlan;
  emotionSource?: string | null;
  emotionVector: VoicePerformanceEmotionVector;
  emotionalReferenceAssetId?: string | null;
  emotionalReferenceStrength?: number | null;
  providerId: string;
  providerVersion?: string | null;
  modelRevision?: string | null;
  approvedTakeId?: string | null;
  manualPlan: VoicePerformancePlan;
  codirectorPlan: VoicePerformancePlan;
  sceneArcId?: string | null;
  timelineLinkage: Record<string, unknown>;
  lipsyncLinkage: Record<string, unknown>;
  consentAck: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
  takes: VoicePerformanceTake[];
};

export type VoicePerformanceRecordList = {
  projectId: string;
  records: VoicePerformanceRecord[];
  mock?: boolean;
};

export type VoicePerformanceTakeList = {
  recordId: string;
  approvedTakeId?: string | null;
  takes: VoicePerformanceTake[];
  mock?: boolean;
};

export type VoicePerformanceRuntimeStatus = {
  ok: boolean;
  providerId: string;
  providerVersion: string;
  installed: boolean;
  ready: boolean;
  availableOnDisk: boolean;
  modelRevision?: string | null;
  runtimeRoot: string;
  manifestPath: string;
  message: string;
  mock?: boolean;
};

export type VoicePerformanceCapabilities = {
  ok: boolean;
  providerId: string;
  providerVersion: string;
  status: "available" | "requires_setup" | string;
  installed: boolean;
  ready: boolean;
  supportsLiveGeneration: boolean;
  supportsEmotionVectors: boolean;
  supportedEmotionVectors: VoicePerformanceEmotionVectorKey[];
  directionModes: VoicePerformanceDirectionMode[];
  presetsAvailable: number;
  message: string;
  mock?: boolean;
};

export type VoicePerformanceComparisonTake = {
  id: string;
  takeNumber: number;
  label: string;
  status: VoicePerformanceTakeStatus;
  durationMs?: number | null;
  audioAssetId?: string | null;
  isApproved: boolean;
};

export type VoicePerformanceComparison = {
  ok: boolean;
  recordId: string;
  approvedTakeId?: string | null;
  comparison: {
    dialogueText: string;
    takeCount: number;
    takes: VoicePerformanceComparisonTake[];
  };
  mock?: boolean;
};

export type VoicePerformanceTimelinePlacement = {
  ok: boolean;
  recordId: string;
  approvedTakeId: string;
  trackId: string;
  wouldReplace: boolean;
  existingClipIds: string[];
  clip: Record<string, unknown>;
  persisted?: boolean;
  timelineLinkage?: Record<string, unknown>;
  mock?: boolean;
};

export type VoicePerformanceLipsyncResult = {
  ok: boolean;
  recordId: string;
  lipsyncLinkage: {
    sceneId?: string | null;
    recordId: string;
    takeId: string;
    audioAssetId?: string | null;
    setSceneAudioAsset: boolean;
    updatedScene: boolean;
    wouldReplace: boolean;
  };
  mock?: boolean;
};
