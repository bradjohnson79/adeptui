/** Structured Failed-state copy for the Timeline Preview Monitor.
 *  Render Bot B's job contract. Do not parse Python traces.
 *
 *  Prefer JobOut jobId + reasonCode when present (transport fail:
 *    status=failed, message="Local generation runtime unavailable",
 *    reasonCode="runtime_unavailable", jobId same uuid as id).
 *  Fallback when jobId/reasonCode are absent: id + status + message +
 *    history_json.videoRuntime.failure.failureClass.
 *  Timeline generation JSON (camelCase): errorCode, errorMessage,
 *    internalJobId / queueJobId. Never walk a traceback.
 */

export const LOCAL_GENERATION_FAILED_TITLE = "Local generation failed";
export const LOCAL_GENERATION_RUNTIME_UNAVAILABLE_TITLE = "Local generation runtime unavailable";
export const LOCAL_GENERATION_FAILED_FALLBACK = "The local engine did not complete this job.";
export const RUNTIME_UNAVAILABLE = "runtime_unavailable";

export type PreviewMonitorPhase = "idle" | "generating" | "preview" | "failed" | "cancelled";

export type PreviewMonitorStateName =
  | "idle"
  | "preparing"
  | "live_preview"
  | "processing"
  | "assembling"
  | "post"
  | "complete"
  | "failed"
  | "cancelled";

export function previewMonitorPhase(state: PreviewMonitorStateName): PreviewMonitorPhase {
  switch (state) {
    case "idle":
      return "idle";
    case "preparing":
    case "processing":
    case "assembling":
    case "post":
      return "generating";
    case "live_preview":
    case "complete":
      return "preview";
    case "failed":
      return "failed";
    case "cancelled":
      return "cancelled";
  }
}

export type LocalGenerationFailureCopy = {
  title: string;
  reason: string;
  details: string | null;
};

export type LocalGenerationFailureInput = {
  id?: string | null;
  jobId?: string | null;
  internalJobId?: string | null;
  message?: string | null;
  stage?: string | null;
  status?: string | null;
  reasonCode?: string | null;
  errorCode?: string | null;
  errorMessage?: string | null;
  historyJson?: string | null;
};

const DETAILS_SPLIT = /---\s*details\s*---/i;

function firstNonEmptyLine(text: string): string {
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (trimmed) return trimmed;
  }
  return "";
}

/** Surface-level blob detector. Does not walk frames or extract exception types. */
function looksLikeDiagnosticBlob(text: string): boolean {
  const value = text.trim();
  if (!value) return false;
  if (/Traceback|httpx\.|---\s*details\s*---/i.test(value)) return true;
  if (/File ["']/.test(value)) return true;
  if ((value.match(/\n/g) || []).length >= 3) return true;
  if (value.length > 220) return true;
  return false;
}

function userSafeText(value: string | null | undefined): string | null {
  const text = String(value || "").trim();
  if (!text) return null;
  if (looksLikeDiagnosticBlob(text)) return null;
  return text;
}

function asTrimmedCode(value: unknown): string {
  if (typeof value !== "string") return "";
  const text = value.trim();
  if (!text || text.length > 80 || /[\r\n]/.test(text)) return "";
  return text;
}

function contractFromJson(raw: string): {
  message?: string;
  errorMessage?: string;
  reasonCode?: string;
  errorCode?: string;
  jobId?: string;
  internalJobId?: string;
} | null {
  const value = raw.trim();
  if (!value.startsWith("{") || value.length > 2000) return null;
  try {
    const obj = JSON.parse(value) as Record<string, unknown>;
    const pick = (key: string) => (typeof obj[key] === "string" ? String(obj[key]).trim() : "");
    return {
      message: pick("message"),
      errorMessage: pick("errorMessage"),
      reasonCode: pick("reasonCode"),
      errorCode: pick("errorCode") || pick("code"),
      jobId: pick("jobId"),
      internalJobId: pick("internalJobId") || pick("queueJobId"),
    };
  } catch {
    return null;
  }
}

/** Structured videoRuntime.failure.failureClass only. Never walk traces in history_json. */
export function failureClassFromHistory(historyJson?: string | null): string {
  const raw = String(historyJson || "").trim();
  if (!raw || !raw.startsWith("{")) return "";
  try {
    const obj = JSON.parse(raw) as Record<string, unknown>;
    const videoRuntime = obj.videoRuntime;
    if (!videoRuntime || typeof videoRuntime !== "object") return "";
    const failure = (videoRuntime as Record<string, unknown>).failure;
    if (!failure || typeof failure !== "object") return "";
    return asTrimmedCode((failure as Record<string, unknown>).failureClass);
  } catch {
    return "";
  }
}

/** Prefer JobOut jobId, then Timeline internalJobId, then Studio id. */
export function resolvePreviewJobId(input: LocalGenerationFailureInput): string {
  const parsed = input.message ? contractFromJson(String(input.message)) : null;
  return String(
    input.jobId || parsed?.jobId || input.internalJobId || parsed?.internalJobId || input.id || "",
  ).trim();
}

export function localGenerationFailureCopy(input: LocalGenerationFailureInput): LocalGenerationFailureCopy {
  const raw = String(input.message || "").trim();
  const parsed = raw ? contractFromJson(raw) : null;
  const reasonCode = asTrimmedCode(input.reasonCode || parsed?.reasonCode);
  const errorCode = asTrimmedCode(input.errorCode || parsed?.errorCode);
  const failureClass = failureClassFromHistory(input.historyJson);
  // Prefer JobOut reasonCode, then Timeline errorCode, then history_json failureClass.
  const code = reasonCode || errorCode || failureClass;
  const runtimeUnavailable = code === RUNTIME_UNAVAILABLE;
  const title = runtimeUnavailable
    ? LOCAL_GENERATION_RUNTIME_UNAVAILABLE_TITLE
    : LOCAL_GENERATION_FAILED_TITLE;

  const structured =
    userSafeText(input.errorMessage) ||
    userSafeText(parsed?.errorMessage) ||
    userSafeText(parsed?.message) ||
    userSafeText(input.message) ||
    userSafeText(input.stage);

  const blob = looksLikeDiagnosticBlob(raw) ? raw : null;

  if (runtimeUnavailable) {
    return {
      title,
      reason: structured && structured !== title ? structured : LOCAL_GENERATION_RUNTIME_UNAVAILABLE_TITLE,
      details: blob && blob !== structured ? blob : null,
    };
  }

  if (structured) {
    return { title, reason: structured, details: blob && blob !== structured ? blob : null };
  }

  const cut = raw.search(DETAILS_SPLIT);
  if (cut >= 0) {
    const summary = raw.slice(0, cut).trim();
    const lead = userSafeText(firstNonEmptyLine(summary));
    if (lead) return { title, reason: lead, details: raw };
    return { title, reason: LOCAL_GENERATION_FAILED_FALLBACK, details: raw };
  }

  if (blob) {
    return { title, reason: LOCAL_GENERATION_FAILED_FALLBACK, details: blob };
  }

  return { title, reason: LOCAL_GENERATION_FAILED_FALLBACK, details: null };
}
