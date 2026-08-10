/** Compact dock chip labels so Local/API → modalities → Co-Director fit one row. */
export function truncateDockLabel(value: string, maxChars = 14): string {
  const text = (value || "").trim();
  if (text.length <= maxChars) return text;
  return `${text.slice(0, Math.max(1, maxChars - 1)).trimEnd()}…`;
}
