/**
 * Honest readiness mark for a model/provider row.
 *
 * ✓ ONLY when actually installed AND healthy. Never ✓ for a default-but-uninstalled
 * provider (e.g. the default minimax-h3 with no local weights) — the previous logic
 * showed ✓ for the default even when uninstalled, which falsely implied readiness.
 *
 * Extracted as a pure module so it can be unit-tested without importing the React
 * component (which pulls in api/Link/etc.).
 */
export function modelMark(installed?: boolean, healthy?: boolean): string {
  return installed && healthy ? "✓" : "○";
}
