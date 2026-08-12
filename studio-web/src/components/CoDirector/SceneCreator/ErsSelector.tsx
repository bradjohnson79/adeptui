/**
 * ErsSelector — picks the Environment Reference Sheet (ERS) package backing
 * a Scene Creator run.
 *
 * The ERS list comes from the existing `api.environmentReferenceSheet.listSheets`
 * endpoint (same data the Spatial Map → ERS panel uses). The most recent
 * sheet is auto-selected; creators can switch via a friendly dropdown.
 *
 * Law #9 (every control wired): switching the dropdown calls onSelected with
 * the new sheet id, which the parent uses for generation.
 * Creator-first UI: show name + status only, no raw IDs.
 */
import { useMemo } from "react";
import type { EnvironmentReferenceSheetSummary } from "../../../contracts/environmentReferenceSheet";

export type ErsSelectorProps = {
  sheets: EnvironmentReferenceSheetSummary[];
  selectedId: string;
  onSelected: (sheetId: string) => void;
  disabled?: boolean;
};

function friendlyStatus(status: string): string {
  return (status || "").replace(/_/g, " ");
}

export function ErsSelector({ sheets, selectedId, onSelected, disabled }: ErsSelectorProps) {
  const selected = useMemo(
    () => sheets.find((s) => s.sheetId === selectedId) || null,
    [sheets, selectedId],
  );

  if (!sheets.length) {
    return (
      <p className="muted" data-testid="scene-creator-ers-selector-empty">
        No Environment Reference Sheet found for this project.
      </p>
    );
  }

  return (
    <div className="row" data-testid="scene-creator-ers-selector" style={{ alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
      <div>
        <p className="eyebrow" style={{ margin: 0 }}>Environment Reference Sheet</p>
        <h3 style={{ margin: 0 }}>{selected?.name || "Select a sheet"}</h3>
        {selected ? (
          <p className="muted" style={{ margin: 0 }}>
            Status: {friendlyStatus(selected.status)} · Directions: {selected.approvedDirections.length}/4
          </p>
        ) : null}
      </div>
      <label className="scene-meta" style={{ minWidth: "12rem" }}>
        Open Sheet
        <select
          value={selectedId}
          onChange={(e) => onSelected(e.target.value)}
          disabled={disabled}
          data-testid="scene-creator-ers-select"
        >
          {sheets.map((s) => (
            <option key={s.sheetId} value={s.sheetId}>
              {s.name}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
