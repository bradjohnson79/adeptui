/** M42 W45 frozen TypeScript mirrors — see docs/release-gate/m42/M42_W45_SHARED_CONTRACTS.md */

export type AudioCategory =
  | "music"
  | "ambience"
  | "foley"
  | "reaction"
  | "impact"
  | "environment"
  | "technology"
  | "creature"
  | "mechanical"
  | "transition"
  | "room_tone"
  | "custom";

export type CandidateStatus = "ready" | "failed" | "selected" | "approved" | "archived";

export type StemRole =
  | "Drums"
  | "Bass"
  | "Vocals"
  | "Pads"
  | "FX"
  | "Lead"
  | "Strings"
  | "Percussion"
  | "Custom";

export interface AudioCreativeBrief {
  projectId: string;
  sceneId?: string | null;
  shotId?: string | null;
  category: AudioCategory | string;
  prompt: string;
  durationSeconds?: number | null;
  mood?: string[];
  intensity?: string | null;
  tempo?: number | null;
  instrumentation?: string[];
  loopRequired?: boolean;
  startBehavior?: string | null;
  endBehavior?: string | null;
  referenceAssetIds?: string[];
  notes?: string | null;
  genre?: string | null;
  energy?: string | null;
}

export interface AudioCandidate {
  id: string;
  batchId: string;
  name: string;
  assetId?: string | null;
  status: CandidateStatus;
  summary?: string;
  provider?: string;
  runtime?: string;
  parentCandidateId?: string | null;
  error?: string | null;
}

export interface AudioCandidateBatch {
  id: string;
  projectId: string;
  method: "music" | "sfx" | "ambience" | "similar";
  briefSnapshot: Record<string, unknown>;
  candidateIds: string[];
  parentCandidateId?: string | null;
  createdAt: string;
  candidates?: AudioCandidate[];
}

export interface AudioMixClipState {
  clipId: string;
  gain: number;
  pan: number;
  mute: boolean;
  solo: boolean;
  normalize?: boolean;
  fadeInMs?: number;
  fadeOutMs?: number;
  crossfadeToClipId?: string | null;
  trackRoute?: string;
  loop?: boolean;
  peak?: number | null;
  lufs?: number | null;
}

export interface AudioMasterOutput {
  gain: number;
  peak?: number | null;
  lufsIntegrated?: number | null;
  lufsShortTerm?: number | null;
}

export interface MusicStem {
  role: StemRole;
  assetId: string;
  muted?: boolean;
}

export interface MusicStemSet {
  parentVersionId: string;
  stems: MusicStem[];
  stemsSupported: boolean;
}
