import type { MagiSequenceDocument } from "./types";
import { MagiApiError, magiErrorFromResponse } from "./errors";

export class MagiSaveConflictError extends Error {
  currentRevision: number;
  expectedRevision: number;
  constructor(currentRevision: number, expectedRevision: number) {
    super(
      `MAGI sequence changed on the server (rev ${expectedRevision} → ${currentRevision}). Reload to see the latest edits.`,
    );
    this.name = "MagiSaveConflictError";
    this.currentRevision = currentRevision;
    this.expectedRevision = expectedRevision;
  }
}

export async function fetchMagiSequence(projectId: string): Promise<MagiSequenceDocument> {
  const res = await fetch(`/api/magi/projects/${encodeURIComponent(projectId)}/sequence`);
  if (!res.ok) throw new MagiApiError(await magiErrorFromResponse(res));
  const data = (await res.json()) as { sequence: MagiSequenceDocument };
  return data.sequence;
}

export async function saveMagiSequence(
  projectId: string,
  sequence: MagiSequenceDocument,
  expectedRevision?: number,
): Promise<MagiSequenceDocument> {
  const res = await fetch(`/api/magi/projects/${encodeURIComponent(projectId)}/sequence`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sequence, expectedRevision }),
  });
  if (!res.ok) {
    if (res.status === 409) {
      let current = 0;
      let expected = expectedRevision ?? 0;
      try {
        const detail = (await res.json()) as {
          detail?: { error?: { fields?: { currentRevision?: number; expectedRevision?: number } } };
        };
        current = detail?.detail?.error?.fields?.currentRevision ?? 0;
        expected = detail?.detail?.error?.fields?.expectedRevision ?? expectedRevision ?? 0;
      } catch {
        // Keep the defaults above.
      }
      throw new MagiSaveConflictError(current, expected);
    }
    throw new MagiApiError(await magiErrorFromResponse(res));
  }
  const data = (await res.json()) as { sequence: MagiSequenceDocument };
  return data.sequence;
}
