import type { HelperKind, HelperMemory, PromptPreset } from "./types";

const ORDER: HelperKind[] = ["scene", "camera", "lighting"];

function stripExact(source: string, fragment: string): { rest: string; found: boolean } {
  const index = source.indexOf(fragment);
  if (index < 0) return { rest: source, found: false };
  const rest = `${source.slice(0, index)}${source.slice(index + fragment.length)}`
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  return { rest, found: true };
}

/** Insert or replace one helper paragraph. Filmmaker text that no longer matches is kept. */
export function applyPromptFragment(
  prompt: string,
  kind: HelperKind,
  fragment: string,
  memory: HelperMemory,
): { prompt: string; memory: HelperMemory } {
  const nextFragment = fragment.trim();
  let rest = prompt || "";
  const placed: Partial<Record<HelperKind, string>> = {};
  for (const key of ORDER) {
    const known = memory[key];
    if (!known) continue;
    const stripped = stripExact(rest, known);
    rest = stripped.rest;
    if (stripped.found && key !== kind) placed[key] = known;
  }
  placed[kind] = nextFragment;
  const header = ORDER.map((key) => placed[key]).filter(Boolean).join("\n\n");
  const user = rest.trim();
  const text = header && user ? `${header}\n\n${user}` : header || user;
  return { prompt: text, memory: { ...memory, [kind]: nextFragment } };
}

export function composeCameraFragment(lens: PromptPreset | null, shot: PromptPreset | null): string {
  if (lens && shot) {
    const look = lens.look || lens.description.replace(/\.$/, "");
    return `${shot.label} photographed with a ${lens.label} cinematic lens, ${look.charAt(0).toLowerCase()}${look.slice(1)}.`;
  }
  if (lens) return lens.promptFragment;
  if (shot) return shot.promptFragment;
  return "";
}
