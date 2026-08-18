/**
 * Live ERS generation viewport — shared by Spatial Map Express + Standard.
 * One image element; src is replaced when the final asset arrives.
 * Cancel is omitted: Image Core cancel is not a genuine interrupt for this path
 * (Comfy WS is not connected; Kie/API poll is not cancellable).
 */
import { useState } from "react";
import { api } from "../../../api";
import { formatErsProvenance } from "./ersGenerator";
import { SpatialMapSaveControls } from "./SpatialMapSaveControls";
import type { SpatialMapSaveStatus } from "./useSpatialMapSave";
import type { ErsGenerationState } from "./useErsGeneration";

type Props = {
  state: ErsGenerationState;
  onRetry: () => void;
  onOpenInLibrary?: () => void;
  onUseInSceneCreator?: () => void;
  onOpenFullSize?: (url: string) => void;
  onUseAnyway?: () => void;
  /** Save Gate: disable "Use in Scene Creator" until the map is saved & clean. */
  useInSceneCreatorDisabled?: boolean;
  saveStatus?: SpatialMapSaveStatus;
  saveIsDirty?: boolean;
  saveError?: string | null;
  saveDisabled?: boolean;
  onSaveSpatialMap?: () => void;
};

function formatElapsed(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return m > 0 ? `${m}:${String(s).padStart(2, "0")}` : `${s}s`;
}

export function ERSGenerationMonitor({
  state,
  onRetry,
  onOpenInLibrary,
  onUseInSceneCreator,
  onOpenFullSize,
  onUseAnyway,
  useInSceneCreatorDisabled = false,
  saveStatus = "idle",
  saveIsDirty = false,
  saveError = null,
  saveDisabled = false,
  onSaveSpatialMap,
}: Props) {
  const [showDetails, setShowDetails] = useState(false);
  if (state.phase === "idle" && !state.compositeAssetId) return null;

  const imageId = state.compositeAssetId || state.progress.finalAssetId;
  const imageUrl = imageId ? api.assetUrl(imageId) : state.progress.previewUrl;
  const live = state.phase === "queued" || state.phase === "generating";
  const failed = state.phase === "failed";
  const complete = state.phase === "complete" && !!imageUrl;
  const modelLine = state.provenance || formatErsProvenance(state.model);
  const gateMismatch =
    complete &&
    !state.gateOverride &&
    (state.semanticGate?.verdict === "ERS_CONTEXT_NONCOMPLIANT" ||
      state.semanticGate?.verdict === "ERS_LAYOUT_NONCOMPLIANT");

  return (
    <div
      className="spatial-map__ers-live"
      data-testid="ers-generation-monitor"
      data-phase={state.phase}
      data-zombie={state.zombie ? "true" : "false"}
    >
      <div className="spatial-map__ers-live-frame" data-testid="ers-generation-viewport">
        {imageUrl ? (
          <img
            className="spatial-map__ers-live-img"
            src={imageUrl}
            alt={complete ? "Environment Reference Sheet" : "ERS generation preview"}
          />
        ) : (
          <div className="spatial-map__ers-live-placeholder" aria-live="polite">
            {failed ? "ERS generation failed" : live ? "Preparing ERS generation…" : "Environment Reference Sheet"}
          </div>
        )}
      </div>

      <div className="spatial-map__ers-live-status">
        <p className="spatial-map__ers-live-stage" data-testid="ers-generation-stage">
          {failed
            ? state.error || "ERS generation failed"
            : state.progress.message || state.progress.stage || (live ? "Preparing ERS generation…" : "Complete")}
        </p>
        {live ? (
          <div
            className={`spatial-map__ers-live-bar${state.progress.indeterminate ? " is-indeterminate" : ""}`}
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={state.progress.indeterminate ? undefined : state.progress.progressPercent ?? undefined}
            aria-label={state.progress.indeterminate ? "Generating" : `Generating ${state.progress.progressPercent ?? 0} percent`}
            data-testid="ers-generation-progress"
            data-indeterminate={state.progress.indeterminate ? "true" : "false"}
          >
            <span
              className="spatial-map__ers-live-bar-fill"
              style={
                state.progress.indeterminate || state.progress.progressPercent == null
                  ? undefined
                  : { width: `${state.progress.progressPercent}%` }
              }
            />
          </div>
        ) : null}
        {modelLine ? (
          <p className="spatial-map__ers-live-model" data-testid="ers-generation-model">
            {modelLine}
          </p>
        ) : null}
        <p className="spatial-map__ers-live-context" data-testid="ers-generation-context">
          Environment {state.counts.environment} · Characters {state.counts.characters} · Props {state.counts.props} ·
          Cameras {state.counts.cameras}
          {live && state.elapsedSec > 0 ? ` · ${formatElapsed(state.elapsedSec)}` : ""}
        </p>
      </div>

      {state.stale && !live ? (
        <div className="spatial-map__ers-live-banner" data-testid="ers-stale-banner" role="status">
          This Environment Reference Sheet is out of date — the scene description or Atlas changed since it
          was generated. Regenerate it when you're ready.
        </div>
      ) : null}

      {gateMismatch ? (
        <div className="spatial-map__ers-live-banner spatial-map__ers-live-banner--warn" data-testid="ers-gate-banner" role="alert">
          <p data-testid="ers-gate-message">
            This Environment Reference Sheet does not match the source environment.
            {state.semanticGate?.summary ? ` ${state.semanticGate.summary}` : ""}
          </p>
          <div className="spatial-map__ers-live-actions">
            <button
              type="button"
              className="ui-btn ui-btn--primary"
              onClick={onRetry}
              disabled={state.busy}
              data-testid="ers-gate-retry"
            >
              Retry
            </button>
            <button
              type="button"
              className="ui-btn ui-btn--secondary"
              onClick={onUseAnyway}
              data-testid="ers-gate-use-anyway"
            >
              Use Anyway
            </button>
          </div>
          {state.error ? (
            <p className="spatial-map__ers-live-details" role="alert" data-testid="ers-gate-use-anyway-error">
              {state.error}
            </p>
          ) : null}
        </div>
      ) : null}

      {failed ? (
        <div className="spatial-map__ers-live-actions">
          <button type="button" className="ui-btn ui-btn--primary" onClick={onRetry} data-testid="ers-generation-retry">
            Retry
          </button>
          <button
            type="button"
            className="ui-btn ui-btn--secondary"
            onClick={() => setShowDetails((v) => !v)}
            data-testid="ers-generation-details"
          >
            {showDetails ? "Hide details" : "Details"}
          </button>
          {showDetails && state.errorDetail ? (
            <p className="spatial-map__ers-live-details" data-testid="ers-generation-error-detail">
              {state.errorDetail}
            </p>
          ) : null}
        </div>
      ) : null}

      {complete ? (
        <div className="spatial-map__ers-live-actions">
          <button
            type="button"
            className="ui-btn ui-btn--secondary"
            onClick={() => imageUrl && (onOpenFullSize ? onOpenFullSize(imageUrl) : window.open(imageUrl, "_blank", "noopener,noreferrer"))}
          >
            Open Full Size
          </button>
          <button type="button" className="ui-btn ui-btn--secondary" onClick={onRetry} disabled={state.busy}>
            Regenerate
          </button>
          <button type="button" className="ui-btn ui-btn--secondary" onClick={onOpenInLibrary}>
            Open in Library
          </button>
          {onSaveSpatialMap ? (
            <SpatialMapSaveControls
              status={saveStatus}
              isDirty={saveIsDirty}
              error={saveError}
              disabled={saveDisabled}
              onSave={onSaveSpatialMap}
              saveTestId="spatial-map-save-bottom"
              stateTestId="spatial-map-save-state-bottom"
              errorTestId="spatial-map-save-error-bottom"
              buttonClassName="ui-btn ui-btn--secondary"
            />
          ) : null}
          <button
            type="button"
            className="ui-btn ui-btn--primary"
            onClick={onUseInSceneCreator}
            disabled={useInSceneCreatorDisabled}
            data-testid="use-in-scene-creator"
            title={useInSceneCreatorDisabled ? "Save Spatial Map first" : undefined}
          >
            Use in Scene Creator
          </button>
        </div>
      ) : null}
    </div>
  );
}
