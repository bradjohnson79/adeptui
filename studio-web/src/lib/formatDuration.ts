/**
 * Creator-facing duration formatting.
 *
 * Raw float seconds like 5.166666666666667 (124 frames @ 24fps) must never reach
 * the UI. Prefer whole seconds; otherwise a single clean decimal.
 */
export function formatDurationSeconds(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const nearestInt = Math.round(value);
  if (Math.abs(value - nearestInt) <= 1e-6) {
    return `${nearestInt}s`;
  }
  const one = Math.round(value * 10) / 10;
  if (Math.abs(one - Math.round(one)) <= 1e-9) {
    return `${Math.round(one)}s`;
  }
  return `${one.toFixed(1)}s`;
}

/**
 * Creator-facing timestamp for job rows ("Aug 7, 12:20 AM").
 *
 * API timestamps are naive UTC ("2026-08-07 16:04:25.449425"); parse them as
 * UTC and render in the creator's local timezone so a stale failure is visibly
 * old instead of looking current.
 */
export function formatJobTimestamp(value: string | null | undefined): string {
  if (!value) return "";
  const normalized = value.includes("T") ? value : value.replace(" ", "T");
  const withZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(normalized) ? normalized : `${normalized}Z`;
  const date = new Date(withZone);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}
