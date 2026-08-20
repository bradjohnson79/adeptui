/**
 * Shared Save Spatial Map control — one hook, two locations (top cluster + ERS footer).
 * Does not own persistence; callers pass the panel's useSpatialMapSaveHooks state.
 */
import type { SpatialMapSaveStatus } from "./useSpatialMapSave";

export function spatialMapSaveButtonLabel(status: SpatialMapSaveStatus): string {
  return status === "saving" ? "Saving…" : "Save Spatial Map";
}

export function spatialMapSaveStateLabel(status: SpatialMapSaveStatus, isDirty: boolean): string {
  if (status === "error") return "Save failed";
  if (status === "saving") return "Saving…";
  if (isDirty) return "Unsaved changes";
  return "Saved";
}

export type SpatialMapSaveControlsProps = {
  status: SpatialMapSaveStatus;
  isDirty: boolean;
  error?: string | null;
  disabled?: boolean;
  onSave: () => void;
  saveTestId: string;
  stateTestId: string;
  errorTestId?: string;
  buttonClassName?: string;
};

export function SpatialMapSaveControls({
  status,
  isDirty,
  error,
  disabled = false,
  onSave,
  saveTestId,
  stateTestId,
  errorTestId = "spatial-map-save-error",
  buttonClassName = "ui-btn ui-btn--primary",
}: SpatialMapSaveControlsProps) {
  return (
    <>
      <button
        type="button"
        className={buttonClassName}
        onClick={onSave}
        disabled={disabled || status === "saving"}
        aria-label="Save Spatial Map"
        data-testid={saveTestId}
      >
        {spatialMapSaveButtonLabel(status)}
      </button>
      <span
        className={"spatial-map__save-state" + (isDirty || status === "saving" ? " is-dirty" : " is-saved")}
        data-testid={stateTestId}
      >
        {spatialMapSaveStateLabel(status, isDirty)}
      </span>
      {status === "error" && error ? (
        <p className="spatial-map__hint spatial-map__hint--error" role="alert" data-testid={errorTestId}>
          {error}
        </p>
      ) : null}
    </>
  );
}
