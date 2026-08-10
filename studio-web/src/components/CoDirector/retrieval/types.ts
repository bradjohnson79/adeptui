export type RetrievalStatus = "success" | "partial" | "empty" | "failed";

export interface RetrievalEvidence {
  sourceType: string;
  sourceId: string;
  sourceName?: string | null;
  repository: string;
  version?: string | null;
  updatedAt?: string | null;
}

export interface RetrievalWarning {
  code: string;
  message: string;
  section?: string | null;
}

export interface RetrievalEnvelope {
  requestId?: string | null;
  toolId: string;
  toolVersion?: string | number;
  projectId?: string | null;
  status: RetrievalStatus;
  summary: string;
  data?: unknown;
  evidence?: RetrievalEvidence[];
  pagination?: {
    cursor?: string | null;
    nextCursor?: string | null;
    total?: number | null;
    limit?: number;
    hasMore?: boolean;
    returnedCount?: number;
    appliedFilters?: Record<string, unknown>;
  } | null;
  warnings?: RetrievalWarning[];
  retrievedAt?: string;
  availableSections?: string[];
  unavailableSections?: string[];
}

export function asRetrievalEnvelope(result: Record<string, unknown> | null | undefined): RetrievalEnvelope | null {
  if (!result || typeof result !== "object") return null;
  if (typeof result.status === "string" && "data" in result && typeof result.toolId === "string") {
    return result as unknown as RetrievalEnvelope;
  }
  return null;
}
