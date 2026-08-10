/**
 * Central API origin configuration — shared by api.ts and studioApiConnection.ts.
 *
 * Extracted to avoid circular imports between the API client and the
 * outage coordinator.
 *
 * - Local dev: BASE="" → relative /api/* paths proxied by Vite to Studio API
 * - Hosted (Vercel): BASE=VITE_API_BASE → absolute HTTPS URL of the secure
 *   Studio API bridge (e.g. https://api-beta.adeptui.org)
 *
 * VITE_API_BASE is a PUBLIC, client-visible configuration value (never secrets).
 */

export const API_BASE: string = import.meta.env.VITE_API_BASE ?? "";

/** Resolve a relative API path against the configured BASE origin. */
export function apiUrl(path: string): string {
  if (!API_BASE) return path;
  return `${API_BASE}${path}`;
}
