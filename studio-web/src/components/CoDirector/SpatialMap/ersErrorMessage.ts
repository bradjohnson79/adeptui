import { shortJobMessage } from "../../generators/shortJobMessage";

const HANDLER_PREFIX = /^HANDLER_ERROR:\s*/i;
const TYPE_PREFIX = /^(?:TypeError|AttributeError):\s*/i;
const NO_ATTR = /'([^']+)' object has no attribute '([^']+)'/i;

/** Peel HANDLER_ERROR / TypeError prefixes and --- details --- traceback. */
export function stripHandlerError(raw: string | null | undefined): string {
  let text = shortJobMessage(String(raw || ""));
  for (let i = 0; i < 3; i += 1) {
    const next = text.replace(HANDLER_PREFIX, "").replace(TYPE_PREFIX, "").trim();
    if (next === text) break;
    text = next;
  }
  return text;
}

/**
 * Creator-facing ERS failure banner.
 * Example: HANDLER_ERROR: 'ImageGenerationPlan' object has no attribute 'prompt'
 *       -> ERS generation failed — ImageGenerationPlan has no prompt
 */
export function normalizeErsError(raw: string | null | undefined): string {
  const reason = stripHandlerError(raw);
  if (!reason) return "ERS generation failed";

  if (/NoneType|unsupported operand|None x/i.test(reason)) {
    return "ERS generation failed — an attached prop is missing a position";
  }

  const attr = reason.match(NO_ATTR);
  if (attr) {
    return `ERS generation failed — ${attr[1]} has no ${attr[2]}`;
  }

  if (/^(TypeError|AttributeError|HANDLER_ERROR)\b/i.test(reason)) {
    return "ERS generation failed";
  }

  const short = reason.length > 160 ? `${reason.slice(0, 157)}…` : reason;
  return `ERS generation failed — ${short}`;
}
