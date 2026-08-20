/**
 * timelineErrors — creator-facing error extraction for Timeline actions.
 *
 * Timeline endpoints return structured { ok, error, message, errors } bodies
 * with HTTP 200 even on domain failures (GENERATOR_REQUIRED,
 * BATCH_ALREADY_IN_FLIGHT, CAPABILITY_VALIDATION_FAILED, ...). Every generate
 * call site must surface these — a silent ok:false is a creator-facing
 * failure with no feedback (Timeline UX blocker 1).
 */
export function timelineActionError(result: unknown): string | null {
  if (!result || typeof result !== "object") return null;
  const r = result as Record<string, unknown>;
  if (r.ok === false) {
    const code = typeof r.error === "string" ? r.error : "";
    const message = typeof r.message === "string" ? r.message : "";
    if (Array.isArray(r.errors)) {
      const joined = (r.errors as unknown[]).map(String).filter(Boolean).join("; ");
      if (joined) return joined;
    }
    if (message) return message;
    if (code) return `Timeline action failed (${code}).`;
    return "Timeline action failed — no reason was reported.";
  }
  return null;
}
