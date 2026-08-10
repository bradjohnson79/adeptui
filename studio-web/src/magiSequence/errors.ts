/** Canonical MAGI error taxonomy (m8) — mirrors the backend taxonomy in
 * ``app/magi/errors.py``.
 *
 * Every MAGI error resolves to a creator-facing message and optional recovery
 * hint. Raw stack traces and backend implementation detail are never shown to
 * creators; unknown codes fall back to a generic, safe message.
 */

export type MagiErrorKind =
  | "validation"
  | "conflict"
  | "not_found"
  | "persistence"
  | "handoff"
  | "render"
  | "unsupported"
  | "latent"
  | "unknown";

export interface MagiErrorInfo {
  code: string;
  status?: number;
  kind: MagiErrorKind;
  message: string;
  recovery?: string;
}

export const MAGI_ERROR_TAXONOMY: Record<string, MagiErrorInfo> = {
  INVALID_SEQUENCE: {
    code: "INVALID_SEQUENCE",
    status: 400,
    kind: "validation",
    message: "The MAGI sequence document is not valid.",
    recovery: "Re-apply the last edit and save again.",
  },
  INVALID_REVISION: {
    code: "INVALID_REVISION",
    status: 422,
    kind: "validation",
    message: "expectedRevision must be a positive integer.",
  },
  REVISION_CONFLICT: {
    code: "REVISION_CONFLICT",
    status: 409,
    kind: "conflict",
    message: "The MAGI sequence changed on the server since it was loaded.",
    recovery: "Reload to see the latest edits, then re-apply yours.",
  },
  INVALID_CLIP_ASSET: {
    code: "INVALID_CLIP_ASSET",
    status: 422,
    kind: "validation",
    message: "The sequence contains clips without an asset reference.",
  },
  ASSET_NOT_FOUND: {
    code: "ASSET_NOT_FOUND",
    status: 400,
    kind: "not_found",
    message: "The sequence references assets that do not exist.",
  },
  ASSET_PROJECT_MISMATCH: {
    code: "ASSET_PROJECT_MISMATCH",
    status: 400,
    kind: "validation",
    message: "The sequence references assets owned by another project.",
  },
  ASSET_OWNERSHIP: {
    code: "ASSET_OWNERSHIP",
    status: 400,
    kind: "validation",
    message: "The asset does not exist in this project.",
  },
  ASSET_ID_REQUIRED: {
    code: "ASSET_ID_REQUIRED",
    status: 400,
    kind: "validation",
    message: "An asset is required.",
  },
  CLIPS_REQUIRED: {
    code: "CLIPS_REQUIRED",
    status: 400,
    kind: "validation",
    message: "Timeline export requires at least one clip.",
  },
  CLIP_NOT_FOUND: {
    code: "CLIP_NOT_FOUND",
    status: 404,
    kind: "not_found",
    message: "The MAGI sequence does not contain the referenced clip.",
    recovery: "Refresh the sequence and export again.",
  },
  SCENE_NOT_FOUND: {
    code: "SCENE_NOT_FOUND",
    status: 404,
    kind: "not_found",
    message: "The timeline scene does not exist.",
  },
  BATCH_NOT_FOUND: {
    code: "BATCH_NOT_FOUND",
    status: 404,
    kind: "not_found",
    message: "The timeline batch block does not exist.",
  },
  SEQUENCE_NOT_FOUND: {
    code: "SEQUENCE_NOT_FOUND",
    status: 404,
    kind: "latent",
    message: "No MAGI sequence exists for this project.",
    recovery: "Save the sequence once before exporting.",
  },
  PERSISTENCE_FAILED: {
    code: "PERSISTENCE_FAILED",
    status: 500,
    kind: "persistence",
    message: "The MAGI sequence could not be saved.",
    recovery: "Try saving again in a moment.",
  },
  RENDER_FAILED: {
    code: "RENDER_FAILED",
    status: 400,
    kind: "render",
    message: "The MAGI overlay render failed.",
  },
  OVERLAY_NOT_FOUND: {
    code: "OVERLAY_NOT_FOUND",
    status: 404,
    kind: "not_found",
    message: "Composition not found.",
  },
  OVERLAY_INVALID: {
    code: "OVERLAY_INVALID",
    status: 400,
    kind: "validation",
    message: "The overlay composition failed validation.",
  },
  IMPORT_FAILED: {
    code: "IMPORT_FAILED",
    status: 400,
    kind: "handoff",
    message: "The timeline import failed.",
  },
  EXPORT_FAILED: {
    code: "EXPORT_FAILED",
    status: 400,
    kind: "handoff",
    message: "The timeline export failed.",
  },
  TIMELINE_HANDOFF_FAILED: {
    code: "TIMELINE_HANDOFF_FAILED",
    status: 502,
    kind: "handoff",
    message: "The clips could not be placed on the timeline.",
    recovery: "Check the timeline and retry the export.",
  },
  UNSUPPORTED_OPERATION: {
    code: "UNSUPPORTED_OPERATION",
    status: 400,
    kind: "unsupported",
    message: "This MAGI surface is not executable yet.",
    recovery: "Use the certified image MAGI Actions path instead.",
  },
  UNKNOWN: {
    code: "UNKNOWN",
    kind: "unknown",
    message: "The MAGI service returned an unexpected error.",
    recovery: "Try again in a moment.",
  },
};

export const MAGI_ERROR_LEGACY_ALIASES: Record<string, string> = {
  validation_failed: "INVALID_SEQUENCE",
  revision_conflict: "REVISION_CONFLICT",
  invalid_revision: "INVALID_REVISION",
  clips_required: "CLIPS_REQUIRED",
  import_failed: "IMPORT_FAILED",
  export_failed: "EXPORT_FAILED",
  render_failed: "RENDER_FAILED",
  overlay_not_found: "OVERLAY_NOT_FOUND",
  overlay_invalid: "OVERLAY_INVALID",
  asset_ownership: "ASSET_OWNERSHIP",
  asset_id_required: "ASSET_ID_REQUIRED",
};

export function magiCanonicalCode(code: string): string {
  if (code in MAGI_ERROR_TAXONOMY) return code;
  return MAGI_ERROR_LEGACY_ALIASES[code] ?? code;
}

export function magiErrorInfo(code: string): MagiErrorInfo {
  const canonical = magiCanonicalCode(code);
  const info = MAGI_ERROR_TAXONOMY[canonical];
  return info ?? { ...MAGI_ERROR_TAXONOMY.UNKNOWN, code: canonical };
}

/** Parse a MAGI ``{error: {code, message}}`` envelope from a failed fetch. */
export async function magiErrorFromResponse(res: Response): Promise<MagiErrorInfo> {
  let code = "UNKNOWN";
  let serverMessage: string | undefined;
  try {
    const body = (await res.json()) as {
      detail?: { error?: { code?: string; message?: string } };
    };
    code = body?.detail?.error?.code ?? "UNKNOWN";
    serverMessage = body?.detail?.error?.message;
  } catch {
    // Non-JSON failure body: fall through to taxonomy/UNKNOWN defaults.
  }
  const info = magiErrorInfo(code);
  return { ...info, status: res.status, message: serverMessage || info.message };
}

/** Resolve any thrown value to a short creator-facing message (never a stack). */
export function describeMagiError(err: unknown): string {
  if (err instanceof MagiApiError) {
    return err.info.recovery ? `${err.info.message} ${err.info.recovery}` : err.info.message;
  }
  if (err instanceof Error) return err.message;
  return MAGI_ERROR_TAXONOMY.UNKNOWN.message;
}

export class MagiApiError extends Error {
  readonly info: MagiErrorInfo;

  constructor(info: MagiErrorInfo) {
    super(info.recovery ? `${info.message} ${info.recovery}` : info.message);
    this.name = "MagiApiError";
    this.info = info;
  }
}
