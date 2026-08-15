/**
 * CharacterCandidateGrid — renders composed character-sheet candidates with
 * provenance labels (LOCAL — Illustrious XL / LOCAL — Z-Image / API — provider/model).
 * The creator-facing candidate image is the composed canonical sheet asset.
 *
 * Per-card state machine (truthful):
 *  - queued / generating → centered spinner + "Generating..." + generator/model + stage
 *  - assembling          → spinner + "Assembling Sheet"
 *  - complete            → spinner removed, composed sheet preview shown
 *  - failed              → spinner removed, error state + Retry. Never an infinite loader.
 */
import { api } from "../../api";
import { candidateErrorMessage, candidateStage, characterSheetBatchLabel, characterSheetProvenanceLabel, isLayoutNoncompliant, SHEET_VIEW_LABELS } from "./types";
import type { CharacterCandidate } from "./types";

type Props = {
  candidates: CharacterCandidate[];
  selectedAssetId?: string | null;
  disabled?: boolean;
  onApprove: (candidate: CharacterCandidate) => void;
  onRetry?: (candidate: CharacterCandidate) => void;
};

function generatorName(c: CharacterCandidate): string {
  return c.provenance || c.modelVariant || c.model || "Local generator";
}

/** Friendly current stage for a generating candidate (e.g. "Front / Side"). */
function stageLabel(c: CharacterCandidate): string {
  const views = c.viewJobs || [];
  if (!views.length) return "";
  const active = views
    .filter((v) => v.status !== "done" && !v.assetId)
    .map((v) => SHEET_VIEW_LABELS[v.role || ""] || v.role || "View");
  if (!active.length) return "Assembling Sheet";
  return active.join(" / ");
}

export function CharacterCandidateGrid({
  candidates,
  selectedAssetId,
  disabled,
  onApprove,
  onRetry,
}: Props) {
  if (!candidates.length) return null;
  return (
    <div className="character-core__candidates" data-testid="character-candidate-grid">
      {candidates.map((c, i) => {
        // Creator-facing image is the composed canonical sheet.
        const assetId = c.sheetAssetId || c.assetId || null;
        const src = assetId ? api.assetUrl(assetId) : "";
        const layoutNoncompliant = isLayoutNoncompliant(c);
        const isSelected = !layoutNoncompliant && !!selectedAssetId && assetId === selectedAssetId;
        const stage = candidateStage(c);
        const ready = stage === "complete";
        const failed = stage === "failed";
        const busy = stage === "queued" || stage === "generating" || stage === "assembling";
        const failMessage = failed ? candidateErrorMessage(c) : "";
        const canApprove = ready && !!assetId && !layoutNoncompliant;
        return (
          <div
            key={c.jobId || assetId || `cand-${i}`}
            className={`character-core__candidate${isSelected ? " is-selected" : ""}${failed ? " is-failed" : ""}${layoutNoncompliant ? " is-layout-noncompliant" : ""}`}
            data-testid={`character-candidate-${i}`}
            data-stage={stage}
          >
            <div className="character-core__candidate-media">
              {src && ready ? (
                <img src={src} alt={c.label || `Candidate ${i + 1}`} loading="lazy" />
              ) : busy ? (
                <div
                  className="character-core__candidate-loading"
                  data-testid={`candidate-loading-${i}`}
                  role="status"
                >
                  <span className="character-core__spinner" aria-hidden="true" />
                  <span className="character-core__candidate-loading-text">
                    {stage === "assembling" ? "Assembling Sheet…" : "Generating..."}
                  </span>
                  <span className="character-core__candidate-loading-model">
                    {generatorName(c)}
                  </span>
                  {stage === "generating" && stageLabel(c) ? (
                    <span className="character-core__candidate-loading-stage">
                      {stageLabel(c)}
                    </span>
                  ) : null}
                </div>
              ) : failed ? (
                <div
                  className="character-core__candidate-error"
                  data-testid={`candidate-error-${i}`}
                  role="alert"
                >
                  <span className="character-core__candidate-error-title">Generation failed:</span>
                  {failMessage ? (
                    <span className="character-core__candidate-error-msg">{failMessage}</span>
                  ) : null}
                </div>
              ) : (
                <div className="character-core__candidate-placeholder">No preview</div>
              )}
            </div>
            <div className="character-core__candidate-meta">
              <span className="character-core__candidate-prov" data-testid={`candidate-provenance-${i}`}>
                {characterSheetProvenanceLabel(c)}
              </span>
              {characterSheetBatchLabel(c) ? (
                <span className="character-core__candidate-batch" data-testid={`candidate-batch-${i}`}>
                  {characterSheetBatchLabel(c)}
                </span>
              ) : null}
              {layoutNoncompliant ? (
                <span
                  className="character-core__candidate-layout-flag"
                  data-testid={`candidate-layout-noncompliant-${i}`}
                  role="status"
                >
                  layout noncompliant / not a four-view sheet
                </span>
              ) : null}
              {(failed || layoutNoncompliant) && onRetry ? (
                <button
                  type="button"
                  className="character-core__button"
                  data-testid={`candidate-retry-${i}`}
                  disabled={disabled}
                  onClick={() => onRetry(c)}
                >
                  Retry
                </button>
              ) : null}
              {!failed ? (
                <button
                  type="button"
                  className="character-core__button primary"
                  data-testid={`candidate-approve-${i}`}
                  disabled={disabled || !canApprove}
                  onClick={() => onApprove(c)}
                >
                  {isSelected ? "Selected" : "Use This Look"}
                </button>
              ) : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}
