/** Strip bracket/XML performance tags and speaker headers for the plain dialogue editor. */
export function extractPlainDialogue(source: string): string {
  return source
    .split("\n")
    .filter((l) => {
      const t = l.trim();
      if (!t) return true;
      if (/^[A-Z][A-Z0-9_\- ]{0,24}$/.test(t) && !t.includes(" ")) return false;
      if (t.startsWith("[") && t.endsWith("]")) return false;
      if (t.startsWith("<") && t.endsWith(">")) return false;
      return true;
    })
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

/** Build canonical markup from creative controls + plain dialogue. */
export function buildPerformanceMarkup(opts: {
  speaker?: string;
  emotion: string;
  delivery: string;
  pace: string;
  pauseMs: number;
  reaction: string;
  dialogue: string;
}): string {
  const speaker = (opts.speaker || "KORRI").toUpperCase();
  const lines = opts.dialogue
    .split("\n")
    .map((l) => l.trimEnd())
    .filter((l, i, arr) => !(l === "" && arr[i - 1] === ""));
  const body: string[] = [];
  let injectedBeat = false;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]!;
    body.push(line);
    if (!injectedBeat && line.trim() && i < lines.length - 1) {
      body.push(`[pause: ${opts.pauseMs}ms]`);
      if (opts.reaction.trim()) body.push(`[reaction: ${opts.reaction.trim()}]`);
      injectedBeat = true;
    }
  }
  if (!injectedBeat && opts.reaction.trim()) {
    body.push(`[pause: ${opts.pauseMs}ms]`);
    body.push(`[reaction: ${opts.reaction.trim()}]`);
  }
  return [
    speaker,
    `[emotion: ${opts.emotion}]`,
    `[delivery: ${opts.delivery}]`,
    `[pace: ${opts.pace}]`,
    ...body,
  ].join("\n");
}
