/** Frozen Magi sequence contracts — M4.12 NLE rebuild. */

export type MagiObjectsSlot = 1 | 2;

export type MagiTrackKind =
  | "video"
  | "image"
  | "audio"
  | "music"
  | "sfx"
  | "text"
  | "objects"
  | "graphics"
  | "fx"
  | "mask"
  | "adjustment";

export type MagiFocusRegion =
  | "timeline"
  | "viewer"
  | "media_bin"
  | "inspector"
  | "text_input"
  | "modal"
  | "none";

export type MagiTrack = {
  id: string;
  kind: MagiTrackKind;
  label: string;
  order: number;
  locked?: boolean;
  muted?: boolean;
  /** Picture and Objects tracks. Hidden tracks stay in the timeline and drop out of the preview. */
  hidden?: boolean;
  solo?: boolean;
  /** 1 = OBJECTS 1, 2 = OBJECTS 2. Required when kind is objects; graphics aliases slot 1. */
  objectsSlot?: MagiObjectsSlot;
};

export type MagiClip = {
  id: string;
  trackId: string;
  assetId: string;
  name?: string;
  startFrame: number;
  durationFrames: number;
  inPoint: number;
  outPoint: number;
  speed?: number;
  reverse?: boolean;
  freeze?: boolean;
  transitionInId?: string | null;
  transitionOutId?: string | null;
  /** Boundary blend length. Used when transitionOutId is dissolve, fade, or wipe. */
  transitionDurationFrames?: number | null;
  /** Fade-in length for the first picture clip. Independent of the outgoing cut. */
  transitionInDurationFrames?: number | null;
  /** m2 lineage: provenance of how this clip entered MAGI (W46 Timeline handoff). */
  batchBlockId?: string;
  generationId?: string;
  takeId?: string;
  sourceClipId?: string;
  sceneId?: string;
    ingestRole?:
    | "published_master"
    | "published_master_audio"
    | "music"
    | "sfx"
    | "finishing_output"
    | "graphic";
  /** Canonical MAGI overlay id when this clip is an Objects projection (`gfx_*`). */
  overlayId?: string;
};

export type MagiMarker = {
  id: string;
  frame: number;
  label: string;
  color?: string;
};

export type MagiSequenceDocument = {
  id: string;
  projectId: string;
  frameRate: number;
  durationFrames: number;
  playheadFrame: number;
  tracks: MagiTrack[];
  clips: MagiClip[];
  markers: MagiMarker[];
  snapEnabled: boolean;
  revision: number;
  updatedAt: string;
  recipeId?: string | null;
  /** m5: MAGI-side export lineage ledger keyed by W46 batchBlockId. Server
   * bookkeeping; survives reload through normal sequence persistence. */
  exportLedger?: Record<string, unknown>;
  finishing?: MagiFinishingState;
};

export type MagiClipGrade = {
  presetId?: string;
  lightingPresetId?: string;
  params?: Record<string, number>;
};

export type MagiFinishingState = {
  clipGrades?: Record<string, MagiClipGrade>;
  upscale?: {
    enabled?: boolean;
    engine?: string;
    model?: string;
    target?: string;
    preview?: boolean;
    soundProfile?: string;
    soundSourceAssetId?: string;
  };
  audio?: {
    range?: "entire" | "clip";
    musicAssetId?: string;
    sfxAssetId?: string;
    lastJobIds?: string[];
    prompt?: string;
  };
  render?: {
    lastJobId?: string;
    profile?: "preview" | "final";
    assetId?: string;
  };
  /** Latest applied MAGI visual derivative (color / upscale / final render). */
  visualResultAssetId?: string | null;
  /** Viewer Compare / Split View source. Original is the published picture, not a copy. */
  compareAssetId?: string | null;
  viewerMode?: "viewer" | "compare" | "split";
};

export type MagiTimelineExportClip = {
  clipId: string;
  assetId: string;
  name?: string;
  startFrame?: number;
  durationFrames?: number;
};

export type MagiTimelineImportResult = {
  ok: boolean;
  clip?: MagiClip;
  message?: string;
};

export type MagiTimelineExportResult = {
  ok: boolean;
  batchBlockId: string;
  clips: Array<{ ok: boolean; clip?: { id?: string } }>;
  mock: boolean;
};

export type MagiEditCommandKind =
  | "Insert"
  | "Overwrite"
  | "Lift"
  | "Extract"
  | "RippleDelete"
  | "Trim"
  | "Split"
  | "Join"
  | "Slip"
  | "Slide"
  | "Move"
  | "Duplicate"
  | "Paste"
  | "AddTrack"
  | "ReorderTrack"
  | "SetPlayhead"
  | "AddMarker"
  | "ApplyTransition"
  | "Select"
  | "Deselect";

export type MagiEditCommand = {
  kind: MagiEditCommandKind;
  payload?: Record<string, unknown>;
};

export const PRIMARY_MAGI_TRACK_KINDS = ["objects", "video", "audio", "music", "sfx"] as const;

export const DEFAULT_TRACK_BLUEPRINT: Array<{
  kind: MagiTrackKind;
  label: string;
  objectsSlot?: MagiObjectsSlot;
}> = [
  { kind: "objects", label: "OBJECTS 1", objectsSlot: 1 },
  { kind: "video", label: "VIDEO" },
  { kind: "audio", label: "AUDIO" },
  { kind: "music", label: "MUSIC" },
  { kind: "sfx", label: "SFX" },
];
