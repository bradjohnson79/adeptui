/**
 * timelineErrors — creator-facing error extraction for Timeline actions.
 *
 * Timeline endpoints return structured { ok, error, message, errors } bodies
 * with HTTP 200 even on domain failures (GENERATOR_REQUIRED,
 * BATCH_ALREADY_IN_FLIGHT, CAPABILITY_VALIDATION_FAILED, ...). Every generate
 * call site must surface these — a silent ok:false is a creator-facing
 * failure with no feedback (Timeline UX blocker 1).
 */

function formatErrorItem(item: unknown): string {
  if (typeof item === "string") return item.trim();
  if (!item || typeof item !== "object") return "";
  const o = item as Record<string, unknown>;
  if (o.error === "DURATION_EXCEEDS_GENERATOR") {
    const planned = Number(o.plannedDuration);
    const max = Number(o.maxDurationSec);
    if (Number.isFinite(planned) && Number.isFinite(max)) {
      return `This shot is ${planned}s. The selected engine can run up to ${max}s. Shorten it or split it into batches.`;
    }
  }
  if (typeof o.message === "string" && o.message.trim()) return o.message.trim();
  if (typeof o.error === "string" && o.error.trim()) return o.error;
  return "";
}

function collectParts(result: Record<string, unknown>): string[] {
  const parts: string[] = [];
  if (Array.isArray(result.errors)) {
    for (const item of result.errors) {
      const text = formatErrorItem(item);
      if (text) parts.push(text);
    }
  }
  if (Array.isArray(result.findings) && result.error === "PREFLIGHT_STRICT") {
    for (const item of result.findings) {
      const text = formatErrorItem(item);
      if (text) parts.push(text);
    }
  }
  return parts;
}

export function timelineActionError(result: unknown): string | null {
  if (!result || typeof result !== "object") return null;
  const r = result as Record<string, unknown>;
  if (r.ok !== false) return null;
  const parts = collectParts(r);
  if (parts.length) return parts.join("; ");
  const message = typeof r.message === "string" ? r.message.trim() : "";
  if (message && message !== "Scene generation submitted.") return message;
  const code = typeof r.error === "string" ? r.error : "";
  if (code) return `Timeline action failed (${code}).`;
  return "Timeline action failed — no reason was reported.";
}

export function timelineGenerateEmpty(result: unknown): boolean {
  if (!result || typeof result !== "object") return false;
  const r = result as Record<string, unknown>;
  if (r.ok === false) return false;
  const jobs = Array.isArray(r.jobs) ? r.jobs : [];
  return jobs.length === 0;
}
