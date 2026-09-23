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
  contentHtml?: string | null;
  contentType?: "html" | "elements";
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

/**
 * Script Writer Standard: Script (screenplay) and Story (project story
 * document). Story uses the same canonical story_entries row as Co-Director
 * Story Express — never a second story store. Revisions stay script-only.
 */
export type StudioView =
  | "script"
  | "story"
  | "revisions";

export type WritingMode =
  | "standard"
  | "focus";
