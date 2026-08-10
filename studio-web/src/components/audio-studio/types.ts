import type { Project } from "../../types";
import type { EditorTab } from "../../workspacePrefs";

export type AudioStudioTab = "music" | "sfx" | "ambience" | "library";
export type AudioStudioTrack = "music" | "sfx" | "ambience";
export type AudioStudioGenerationKind = AudioStudioTrack;

export type AudioGenerationProgress = {
  visible: boolean;
  active: boolean;
  percent: number;
  label: string;
  completed?: number;
  total?: number;
  batchId?: string;
};

export type AudioStudioActionHandlers = {
  onGenerate: () => Promise<void> | void;
  onOpenAdvanced: () => void;
};

export type AudioStudioWorkspaceProps = {
  project: Project;
  onChange?: () => Promise<void>;
  onGo: (tab: EditorTab) => void;
};

export type AudioCandidate = {
  id: string;
  batchId?: string;
  assetId?: string;
  title: string;
  subtitle?: string;
  description?: string;
  prompt?: string;
  durationSec?: number;
  loop?: boolean;
  audioUrl?: string;
  typeLabel?: string;
  status?: string;
  stemsSupported?: boolean;
  seed?: number;
  variationIndex?: number;
  variationHint?: string;
  raw?: any;
};

export type AudioLibraryAsset = {
  id: string;
  kind?: string;
  tag?: string;
  filename?: string;
  title?: string;
  url?: string;
  thumb_url?: string;
  createdAt?: string;
  created_at?: string;
  approved?: boolean;
  durationSec?: number;
  duration_sec?: number;
  [key: string]: any;
};
