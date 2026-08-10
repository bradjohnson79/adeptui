export type ScriptElementType =
  | "scene_heading"
  | "action"
  | "character"
  | "parenthetical"
  | "dialogue"
  | "transition"
  | "shot"
  | "general"
  | "act_break"
  | "section"
  | "note"
  | "lyric";

export type ScriptElement = {
  id: string;
  type: ScriptElementType;
  text: string;
  order: number;
  sceneId?: string | null;
  characterId?: string | null;
  sceneNumber?: string | null;
  revisionColor?: string | null;
  locked?: boolean;
  omitted?: boolean;
  metadata?: Record<string, unknown>;
};

export type ScriptDocument = {
  id: string;
  projectId: string;
  title: string;
  format: string;
  draftStatus: string;
  elements: ScriptElement[];
  revision: number;
  productionNumbersLocked?: boolean;
  sceneSync?: Record<string, string>;
};

export type SaveState =
  | "saved"
  | "saving"
  | "unsaved"
  | "offline"
  | "conflict"
  | "recovery_available"
  | "save_failed";

export type StudioView =
  | "script"
  | "outline"
  | "cards"
  | "beats"
  | "compare"
  | "production"
  | "storyboard";

export type WritingMode =
  | "standard"
  | "focus"
  | "distraction-free"
  | "dialogue"
  | "scene"
  | "revision"
  | "production";
