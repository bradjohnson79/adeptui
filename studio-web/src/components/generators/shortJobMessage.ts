const DETAILS_SPLIT = /---\s*details\s*---/i;

/** Keep the short job summary; never show worker traceback on a candidate card. */
export function shortJobMessage(raw: string): string {
  const text = String(raw || "");
  const cut = text.search(DETAILS_SPLIT);
  return (cut >= 0 ? text.slice(0, cut) : text).trim();
}
