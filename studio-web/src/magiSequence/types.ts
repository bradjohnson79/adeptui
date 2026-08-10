/** Frozen Magi sequence contracts — M4.12 NLE rebuild. */

export type MagiTrackKind =
  | "video"
  | "image"
  | "audio"
  | "text"
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
  solo?: boolean;
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
  /** m2 lineage: provenance of how this clip entered MAGI (W46 Timeline handoff). */
  batchBlockId?: string;
  generationId?: string;
  takeId?: string;
  sourceClipId?: string;
  sceneId?: string;
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

export const DEFAULT_TRACK_BLUEPRINT: Array<{ kind: MagiTrackKind; label: string }> = [
  { kind: "video", label: "V1" },
  { kind: "video", label: "V2" },
  { kind: "video", label: "V3" },
  { kind: "image", label: "I1" },
  { kind: "image", label: "I2" },
  { kind: "audio", label: "A1" },
  { kind: "audio", label: "A2" },
  { kind: "audio", label: "A3" },
  { kind: "text", label: "T1" },
  { kind: "fx", label: "FX" },
  { kind: "mask", label: "M" },
  { kind: "adjustment", label: "ADJ" },
];
