/**
 * Honest Atlas Shot progress — same sampler rules as ERS.
 * Percent only when the runtime reports real steps. Otherwise indeterminate.
 */
import type { NormalizedJobProgress } from "./normalizeJobProgress";

type Props = {
  progress: NormalizedJobProgress;
  live: boolean;
  modelLine?: string;
  elapsedSec?: number;
};

function formatElapsed(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return m > 0 ? `${m}:${String(s).padStart(2, "0")}` : `${s}s`;
}

export function AtlasGenerationMonitor({
  progress,
  live,
  modelLine,
  elapsedSec = 0,
}: Props) {
  if (!live) return null;

  const stage =
    progress.message ||
    progress.stage ||
    "Analyzing the location…";

  return (
    <div
      className="spatial-map__atlas-progress"
      data-testid="atlas-generation-monitor"
      role="status"
      aria-live="polite"
    >
      <p className="spatial-map__ers-live-stage" data-testid="atlas-generation-stage">
        {stage}
      </p>
      <div
        className={`spatial-map__ers-live-bar${progress.indeterminate ? " is-indeterminate" : ""}`}
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={progress.indeterminate ? undefined : progress.progressPercent ?? undefined}
        aria-label={
          progress.indeterminate
            ? "Creating Spatial Map"
            : `Creating Spatial Map ${progress.progressPercent ?? 0} percent`
        }
        data-testid="atlas-generation-progress"
        data-indeterminate={progress.indeterminate ? "true" : "false"}
      >
        <span
          className="spatial-map__ers-live-bar-fill"
          style={
            progress.indeterminate || progress.progressPercent == null
              ? undefined
              : { width: `${progress.progressPercent}%` }
          }
        />
      </div>
      {modelLine ? (
        <p className="spatial-map__ers-live-model" data-testid="atlas-generation-model">
          {modelLine}
        </p>
      ) : null}
      {elapsedSec > 0 ? (
        <p className="spatial-map__ers-live-context" data-testid="atlas-generation-elapsed">
          {formatElapsed(elapsedSec)}
        </p>
      ) : null}
    </div>
  );
}
