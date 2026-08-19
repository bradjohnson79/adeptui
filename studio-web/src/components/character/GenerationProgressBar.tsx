/**
 * GenerationProgressBar — one honest overall progress bar shown above the
 * candidate cards while Character Sheet generation runs.
 *
 * Progress is derived from real backend state only (completed view-jobs +
 * completed sheet assembly). No fake smooth percentages. The label is
 * batch-accurate: it reports true totals across all candidates (never a
 * misleading "N of 4 views complete" for a multi-candidate batch).
 */
import { batchProgress } from "./types";
import type { CharacterCandidate } from "./types";

type Props = {
  candidates: CharacterCandidate[];
  active: boolean;
};

export function GenerationProgressBar({ candidates, active }: Props) {
  if (!active && !candidates.length) return null;

  const { doneViews, totalViews, doneSheets, totalSheets, percent } =
    batchProgress(candidates);
  const allComplete =
    totalSheets > 0 &&
    doneSheets >= totalSheets &&
    (totalViews <= 0 || doneViews >= totalViews);
  const displayPercent = active && !allComplete ? Math.min(percent, 99) : percent;

  // Choose the most truthful label available. When per-view counts exist,
  // report true totals (e.g. "11 of 16 views complete"); otherwise fall back
  // to whole-sheet completion.
  let label: string;
  if (totalViews > 0) {
    label = `${doneViews} of ${totalViews} views complete`;
  } else if (totalSheets > 0) {
    label = `${doneSheets} of ${totalSheets} character sheets complete`;
  } else {
    label = "Preparing generation…";
  }

  return (
    <div className="character-core__progress" data-testid="generation-progress">
      <div className="character-core__progress-head">
        <span className="character-core__progress-title">Generating Character Reference Sheet</span>
        <span className="character-core__progress-pct" data-testid="generation-progress-pct">
          {displayPercent}%
        </span>
      </div>
      <div
        className="character-core__progress-track"
        role="progressbar"
        aria-valuenow={displayPercent}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className="character-core__progress-fill"
          data-testid="generation-progress-fill"
          style={{ width: `${displayPercent}%` }}
        />
      </div>
      <p className="character-core__progress-label" data-testid="generation-progress-label">
        {label}
      </p>
    </div>
  );
}
