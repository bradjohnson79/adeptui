const SELECTED_CHARACTER_KEY = "adept_selected_character";

export function persistSelectedCharacter(characterId: string): void {
  try {
    sessionStorage.setItem(SELECTED_CHARACTER_KEY, characterId);
    window.dispatchEvent(new CustomEvent("adept:selected-character", { detail: { characterId } }));
  } catch {
    /* ignore */
  }
}

export function readRememberedCharacter(): string {
  try {
    return sessionStorage.getItem(SELECTED_CHARACTER_KEY) || "";
  } catch {
    return "";
  }
}

export function clearRememberedCharacter(): void {
  try {
    sessionStorage.removeItem(SELECTED_CHARACTER_KEY);
    window.dispatchEvent(new CustomEvent("adept:selected-character", { detail: { characterId: "" } }));
  } catch {
    /* ignore */
  }
}

export function voiceStudioSearchForCharacter(currentSearch: string, characterId: string | null): string {
  const raw = currentSearch.startsWith("?") ? currentSearch.slice(1) : currentSearch;
  const params = new URLSearchParams(raw);
  params.set("workspace", "voicestudio");
  const nextId = (characterId || "").trim();
  if (nextId) params.set("characterId", nextId);
  else params.delete("characterId");
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export function resolveVoiceStudioActiveCharacterId(input: {
  urlCharacterId?: string | null;
  knownIds: string[];
}): string {
  const url = (input.urlCharacterId || "").trim();
  if (!url) return "";
  return input.knownIds.includes(url) ? url : "";
}

export function rememberedCharacterToRestore(input: {
  urlCharacterId?: string | null;
  rememberedCharacterId?: string | null;
  knownIds: string[];
}): string {
  if ((input.urlCharacterId || "").trim()) return "";
  const remembered = (input.rememberedCharacterId || "").trim();
  if (remembered && input.knownIds.includes(remembered)) return remembered;
  return "";
}

export function isCurrentCharacterRequest(requestedId: string, currentId: string): boolean {
  return Boolean(requestedId) && requestedId === currentId;
}
