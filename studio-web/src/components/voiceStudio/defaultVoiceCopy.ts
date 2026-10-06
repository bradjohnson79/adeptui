export function approvedDefaultVoiceMessage(characterName: string): string {
  const name = characterName.trim() || "This character";
  return `Approved. This is now ${name}'s default voice throughout Adept UI.`;
}

export function noApprovedDefaultVoiceMessage(characterName: string): string {
  const name = characterName.trim() || "This character";
  return `${name} has no voice currently assigned.`;
}

export function unassignVoiceConfirm(characterName: string): string {
  const name = characterName.trim() || "this character";
  return `Unassign this voice from ${name}?`;
}

export function unassignVoiceExplain(characterName: string): string {
  const name = characterName.trim() || "This character";
  return `The saved voice will remain available. ${name} will have no active Character Voice until another sample is approved.`;
}

export function approvedVoiceBannerTitle(profileName: string, characterName?: string): string {
  const profile = profileName.trim() || (characterName?.trim() ? `${characterName.trim()} Voice` : "Approved Voice");
  return `Approved Voice — ${profile}`;
}

export function approvedVoiceBannerSubtitle(): string {
  return "Default voice across Adept UI";
}

export function approveReplacementNote(characterName: string): string {
  const name = characterName.trim() || "this character";
  return `Approving a new sample will make it ${name}'s current voice. The previous approved voice will remain in version history.`;
}

export function approvedVoiceVersionLabel(versionNumber?: number | string | null): string {
  const raw = Number(versionNumber);
  if (!Number.isFinite(raw) || raw <= 0) return "";
  return `v${raw}`;
}
