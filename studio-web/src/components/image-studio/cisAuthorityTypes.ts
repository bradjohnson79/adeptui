/** Shared CIS authority reference types (Image Generator Journey 1). */
export type CisAuthorityKind = "character" | "prop" | "environment" | "posecraft" | "other";

export type CisAuthorityRef = {
  /** Stable selection key (entity or asset scoped). */
  key: string;
  kind: CisAuthorityKind;
  assetId: string;
  name: string;
  /** Visible chip label including sigil where applicable. */
  chip: string;
};
