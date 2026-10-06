/**
 * Prompt-facing identity tags — mirrors studio-api creator_scope/identity_tag.py.
 * Prefix law: character=@  prop=%  environment=#
 * Do not invent aliases; prefer stored canonical when already grammar-tagged.
 */

export type CreatorIdentityKind = "character" | "prop" | "environment";

const PREFIX: Record<CreatorIdentityKind, "@" | "%" | "#"> = {
  character: "@",
  prop: "%",
  environment: "#",
};

/** Venture Spaceship → VentureSpaceship. Cade's Starfighter → CadeSStarfighter. */
export function promptCanonicalToken(displayName: string): string {
  const text = String(displayName || "").replace(/['’]s\b/gi, "S");
  const parts = text.match(/[A-Za-z0-9]+/g) || [];
  return parts.map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join("");
}

function withPrefix(kind: CreatorIdentityKind, tokenOrTag: string): string {
  const mark = PREFIX[kind];
  const raw = String(tokenOrTag || "").trim();
  if (!raw) return "";
  if (raw.startsWith("@") || raw.startsWith("#") || raw.startsWith("%")) {
    return `${mark}${raw.slice(1)}`;
  }
  return `${mark}${raw}`;
}

export function promptCanonicalIdentityTag(
  kind: CreatorIdentityKind,
  displayName?: string | null,
  stored?: string | null,
): string {
  const storedRaw = String(stored || "").trim();
  if (storedRaw) return withPrefix(kind, storedRaw);
  const token = promptCanonicalToken(String(displayName || ""));
  return token ? withPrefix(kind, token) : "";
}

export function promptCanonicalCharacterTag(name?: string | null, stored?: string | null): string {
  return promptCanonicalIdentityTag("character", name, stored);
}

export function promptCanonicalEnvironmentTag(name?: string | null, stored?: string | null): string {
  return promptCanonicalIdentityTag("environment", name, stored);
}

export function promptCanonicalPropTagFromName(name?: string | null, stored?: string | null): string {
  return promptCanonicalIdentityTag("prop", name, stored);
}
