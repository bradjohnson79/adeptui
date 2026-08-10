/** M4.9 Storyboard Studio contracts */

export type StoryboardPageSize = 6 | 9 | 12;
export type ScriptLinkStatus =
  | "linked"
  | "script_updated"
  | "override"
  | "conflict"
  | "unlinked";

export type StoryboardPanelLink = {
  panelId: string;
  pageIndex: number;
  slotIndex: number;
  assetId?: string | null;
  label: string;
  prompt: string;
  lens: string;
  shotSize: string;
  approval: string;
  status: string;
  scriptLinkStatus: ScriptLinkStatus;
  segmentId?: string | null;
  scriptwriterSceneId?: string | null;
  scriptwriterActionId?: string | null;
  scriptwriterDialogueId?: string | null;
  continuitySessionId?: string | null;
  spatialMapId?: string | null;
  spatialMapVersion?: string | null;
  durationEst: number;
  meta?: Record<string, unknown>;
};

export type StoryboardPage = {
  pageIndex: number;
  pageSize: StoryboardPageSize;
  panelIds: string[];
  title: string;
};

export type StoryboardDocument = {
  id: string;
  projectId: string;
  title: string;
  pageSize: StoryboardPageSize;
  pages: StoryboardPage[];
  panelOrder: string[];
  legacyDocId?: string | null;
  continuitySessionId?: string | null;
  createdAt: string;
  updatedAt: string;
};

export type TimelinePrepShotProposal = {
  panelId: string;
  assetId?: string | null;
  label: string;
  prompt: string;
  dialogue: string;
  cameraNote: string;
  durationEst: number;
  sceneId?: string | null;
  continuitySessionId?: string | null;
  spatialMapId?: string | null;
  spatialMapVersion?: string | null;
};

export type TimelinePrepProposal = {
  id: string;
  projectId: string;
  documentId: string;
  shots: TimelinePrepShotProposal[];
  status: "draft" | "approved" | "applied" | "rejected";
  createdAt: string;
  note: string;
};

export type StoryboardWorkspacePayload = {
  document: StoryboardDocument;
  panels: StoryboardPanelLink[];
};
