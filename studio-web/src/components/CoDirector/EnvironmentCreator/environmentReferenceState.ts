/** Draft profile vs a real Environment Reference Sheet. */

export const ERS_NOT_CREATED_MESSAGE =
  "The Environment Reference Sheet wasn’t created, so nothing was added to your reference sheets.";

type SheetIdentity = {
  ers_composite_asset_id?: string | null;
  composite?: string | null;
  projectId?: string | null;
  status?: string | null;
  recordKind?: string | null;
  isSnapshot?: boolean | null;
  isEditableMaster?: boolean | null;
  snapshotNumber?: number | null;
  snapshotOfSheetId?: string | null;
  parentSheetId?: string | null;
  name?: string | null;
  directionMovement?: string | null;
  movementSequenceIndex?: number | null;
};

export function isProjectEnvironmentReferenceSheet(sheet: SheetIdentity): boolean {
  return Boolean(String(sheet.ers_composite_asset_id || sheet.composite || "").trim());
}

export function isOwnedEnvironmentDraft(sheet: SheetIdentity, projectId: string): boolean {
  if (isProjectEnvironmentReferenceSheet(sheet)) return false;
  const owner = String(sheet.projectId || "").trim();
  return !owner || owner === projectId;
}

export function isErsSnapshotSheet(sheet: SheetIdentity): boolean {
  if (sheet.isSnapshot === true) return true;
  if (String(sheet.recordKind || "").toLowerCase() === "snapshot") return true;
  if (sheet.isEditableMaster === false && (sheet.snapshotNumber != null || sheet.snapshotOfSheetId)) {
    return true;
  }
  return Boolean(sheet.snapshotOfSheetId);
}

export function environmentReferenceStatusLabel(sheet: SheetIdentity): string {
  if (isErsSnapshotSheet(sheet)) {
    const n = sheet.snapshotNumber != null ? ` SS-${sheet.snapshotNumber}` : "";
    return `Snapshot${n}`;
  }
  const base = String(sheet.status || "").toLowerCase() === "approved" ? "Approved Environment" : "ERS Ready";
  return `${base} (Original)`;
}

export function resolveErsEditMasterId(sheet: SheetIdentity, fallbackSheetId: string): string {
  if (!isErsSnapshotSheet(sheet)) return fallbackSheetId;
  return String(sheet.snapshotOfSheetId || sheet.parentSheetId || fallbackSheetId).trim() || fallbackSheetId;
}


/** UI-only list label. Original keeps exact name; SS-# only on snapshots. */
export function ersListDisplayLabel(sheet: SheetIdentity & { name?: string | null }): string {
  const raw = String(sheet.name || "Environment Reference Sheet").trim() || "Environment Reference Sheet";
  if (!isErsSnapshotSheet(sheet)) {
    // Original: exact existing name — never append Prime Movement / movement labels.
    return raw;
  }
  const base = raw.replace(/\s+SS-\d+\s*$/i, "").trim() || raw;
  const n =
    sheet.snapshotNumber != null && Number(sheet.snapshotNumber) > 0
      ? Number(sheet.snapshotNumber)
      : (() => {
          const m = raw.match(/\s+SS-(\d+)\s*$/i);
          return m ? Number(m[1]) : 0;
        })();
  return n > 0 ? `${base} SS-${n}` : raw;
}

export function environmentDraftStatusLabel(input: { generating?: boolean; failed?: boolean }): string {
  if (input.generating) return "Generating ERS";
  if (input.failed) return "Generation Failed";
  return "Draft";
}
