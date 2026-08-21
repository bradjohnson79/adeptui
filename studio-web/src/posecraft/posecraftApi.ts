/**
 * PoseCraft API client — Master Program Phase 15–20 persistence.
 *
 * The project API is the single source of truth for PoseCraft scenes,
 * revisions, and custom poses. localStorage is no longer the SoT (it is
 * only used for ephemeral client conveniences like favorites and undo).
 */
import type { PoseCraftDocument, PoseCraftScene, PoseCraftSnapshot, PosePreset } from "./types";
import { apiUrl } from "../runtime/apiBase";

export class PoseCraftApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "PoseCraftApiError";
    this.status = status;
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(apiUrl(path), {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const payload = (await res.json()) as { detail?: string };
      if (payload.detail) detail = payload.detail;
    } catch {
      /* keep statusText */
    }
    throw new PoseCraftApiError(detail, res.status);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export async function loadSceneDocument(projectId: string): Promise<PoseCraftDocument> {
  return req<PoseCraftDocument>(`/api/posecraft/projects/${projectId}/scene`);
}

export async function saveSceneDocument(projectId: string, document: PoseCraftDocument): Promise<PoseCraftDocument> {
  return req<PoseCraftDocument>(`/api/posecraft/projects/${projectId}/scene`, {
    method: "PUT",
    body: JSON.stringify(document),
  });
}

// Immediate, navigation-safe flush used by explicit Save actions. `keepalive`
// lets the PUT complete on the server even if the creator reloads or navigates
// away in the same tick as the click (the debounced auto-save would otherwise
// be cancelled by the navigation, losing the scene).
export async function flushSceneDocument(projectId: string, document: PoseCraftDocument): Promise<PoseCraftDocument> {
  const res = await fetch(apiUrl(`/api/posecraft/projects/${projectId}/scene`), {
    method: "PUT",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(document),
    keepalive: true,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const payload = (await res.json()) as { detail?: string };
      if (payload.detail) detail = payload.detail;
    } catch {
      /* keep statusText */
    }
    throw new PoseCraftApiError(detail, res.status);
  }
  if (res.status === 204) return undefined as unknown as PoseCraftDocument;
  return (await res.json()) as PoseCraftDocument;
}

export type CustomPoseRecord = {
  id: string;
  projectId: string;
  poseId: string;
  label: string;
  description: string;
  category: string;
  archetypes: string[];
  joints: PosePreset["joints"];
  thumbnail: string;
  creatorModified: boolean;
  savedBy: string;
  createdAt?: string;
  updatedAt?: string;
};

export async function listCustomPoses(projectId: string): Promise<CustomPoseRecord[]> {
  return req<CustomPoseRecord[]>(`/api/posecraft/projects/${projectId}/poses`);
}

export async function createCustomPose(projectId: string, pose: CustomPoseRecord): Promise<CustomPoseRecord> {
  return req<CustomPoseRecord>(`/api/posecraft/projects/${projectId}/poses`, {
    method: "POST",
    body: JSON.stringify(pose),
  });
}

export async function updateCustomPose(projectId: string, poseId: string, pose: CustomPoseRecord): Promise<CustomPoseRecord> {
  return req<CustomPoseRecord>(`/api/posecraft/projects/${projectId}/poses/${poseId}`, {
    method: "PUT",
    body: JSON.stringify(pose),
  });
}

export async function deleteCustomPose(projectId: string, poseId: string): Promise<void> {
  await req<void>(`/api/posecraft/projects/${projectId}/poses/${poseId}`, { method: "DELETE" });
}

export async function listRevisions(projectId: string): Promise<{ id: string; label: string; savedAt: string; revision: number; scene: PoseCraftScene }[]> {
  return req(`/api/posecraft/projects/${projectId}/revisions`);
}

export async function saveRevision(projectId: string, label: string, scene: PoseCraftScene) {
  return req(`/api/posecraft/projects/${projectId}/revisions`, {
    method: "POST",
    body: JSON.stringify({ id: "pending", label, savedAt: "", revision: scene.revision, scene }),
  });
}

export async function restoreRevision(projectId: string, revisionId: string): Promise<PoseCraftDocument> {
  return req<PoseCraftDocument>(`/api/posecraft/projects/${projectId}/revisions/${revisionId}/restore`, { method: "POST" });
}

// ---------------------------------------------------------------------------
// Snapshot API — frozen camera-composition handoff artifacts. Snapshots are
// persisted on the PoseCraftDocument via the existing scene PUT (the client
// appends the frozen snapshot and flushes). These helpers expose rename /
// duplicate / delete / select and a snapshot-aware export preview so the
// gallery and Co-Director / Image Gen / Storyboard handoffs can read a frozen
// composition by id.
// ---------------------------------------------------------------------------

export async function listSnapshots(projectId: string): Promise<PoseCraftSnapshot[]> {
  return req<PoseCraftSnapshot[]>(`/api/posecraft/projects/${projectId}/snapshots`);
}

export async function getSnapshot(projectId: string, snapshotId: string): Promise<PoseCraftSnapshot> {
  return req<PoseCraftSnapshot>(`/api/posecraft/projects/${projectId}/snapshots/${snapshotId}`);
}

export async function renameSnapshotApi(projectId: string, snapshotId: string, name: string): Promise<PoseCraftDocument> {
  return req<PoseCraftDocument>(`/api/posecraft/projects/${projectId}/snapshots/${snapshotId}/rename`, {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export async function duplicateSnapshotApi(projectId: string, snapshotId: string): Promise<PoseCraftDocument> {
  return req<PoseCraftDocument>(`/api/posecraft/projects/${projectId}/snapshots/${snapshotId}/duplicate`, {
    method: "POST",
  });
}

export async function deleteSnapshotApi(projectId: string, snapshotId: string): Promise<PoseCraftDocument> {
  return req<PoseCraftDocument>(`/api/posecraft/projects/${projectId}/snapshots/${snapshotId}`, {
    method: "DELETE",
  });
}

export async function selectSnapshotApi(projectId: string, snapshotId: string | null): Promise<PoseCraftDocument> {
  return req<PoseCraftDocument>(`/api/posecraft/projects/${projectId}/snapshots/select`, {
    method: "POST",
    body: JSON.stringify({ snapshotId }),
  });
}

export async function getExportPreview(projectId: string, snapshotId?: string): Promise<unknown> {
  const url = snapshotId
    ? `/api/posecraft/projects/${projectId}/export-preview?snapshot_id=${encodeURIComponent(snapshotId)}`
    : `/api/posecraft/projects/${projectId}/export-preview`;
  return req(url);
}

export type PoseIntelligencePacket = {
  packetId?: string;
  availability?: string;
  reason?: string;
  creatorFacingSummary?: string;
  creatorFacingDetails?: string;
  warnings?: string[];
  character?: {
    primarySupport?: string;
    balance?: string;
    stance?: string;
    figureName?: string;
  };
  interaction?: {
    handContact?: string[];
    footContact?: string[];
  };
  motion?: {
    rotationDirection?: string;
    outgoingMovement?: string;
    likelyContinuation?: string;
    transitionState?: string;
  };
  constraints?: {
    preserveSupportFoot?: string;
    creatorIntentHonored?: boolean;
  };
  world?: { availability?: string };
};

export async function analyzePoseIntelligence(
  projectId: string,
  body?: { snapshotId?: string; figureId?: string },
): Promise<{ packet: PoseIntelligencePacket; worldAvailable: boolean }> {
  return req(`/api/posecraft/projects/${projectId}/intelligence/analyze`, {
    method: "POST",
    body: JSON.stringify(body || {}),
  });
}

export async function comparePoseIntelligence(
  projectId: string,
  fromSnapshotId: string,
  toSnapshotId: string,
): Promise<{ transition?: { plausibilityWarnings?: string[]; actionProgression?: string }; sequence?: unknown; to?: PoseIntelligencePacket }> {
  return req(`/api/posecraft/projects/${projectId}/intelligence/compare`, {
    method: "POST",
    body: JSON.stringify({ fromSnapshotId, toSnapshotId }),
  });
}

export async function loadPoseIntelligence(projectId: string, snapshotId?: string): Promise<{
  available: boolean;
  worldAvailable: boolean;
  packet: PoseIntelligencePacket | null;
}> {
  const q = snapshotId ? `?snapshotId=${encodeURIComponent(snapshotId)}` : "";
  return req(`/api/posecraft/projects/${projectId}/intelligence${q}`);
}

export async function handoffPoseToSceneCreator(projectId: string, snapshotId?: string) {
  return req(`/api/posecraft/projects/${projectId}/intelligence/handoff/scene-creator`, {
    method: "POST",
    body: JSON.stringify({ snapshotId: snapshotId || "" }),
  });
}

export async function handoffPoseToTimeline(projectId: string, snapshotId?: string) {
  return req(`/api/posecraft/projects/${projectId}/intelligence/handoff/timeline`, {
    method: "POST",
    body: JSON.stringify({ snapshotId: snapshotId || "" }),
  });
}
