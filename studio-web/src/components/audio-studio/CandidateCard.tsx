import { Button } from "../ui";
import { AudioRow } from "./AudioRow";
import type { AudioCandidate } from "./types";

type CandidateCardProps = {
  candidate: AudioCandidate;
  ctaLabel: string;
  previewSelected?: boolean;
  approved?: boolean;
  busy?: boolean;
  onPreview: () => void;
  onApprove: () => Promise<void> | void;
  onPrimary?: () => Promise<void> | void;
  primaryLabel?: string;
};

export function CandidateCard({
  candidate,
  ctaLabel,
  previewSelected = false,
  approved = false,
  busy = false,
  onPreview,
  onApprove,
  onPrimary,
  primaryLabel,
}: CandidateCardProps) {
  const playable = Boolean(candidate.audioUrl);
  const failed = candidate.status === "failed";
  return (
    <article
      className={`audio-candidate-card${previewSelected ? " is-selected" : ""}${approved ? " is-approved" : ""}`}
      data-testid={`audio-candidate-${candidate.id}`}
    >
      <div className="audio-candidate-card__meta">
        <div>
          <p className="audio-candidate-card__eyebrow">{candidate.typeLabel || ctaLabel}</p>
          <h4>{candidate.title}</h4>
        </div>
        <div className="audio-candidate-card__chips">
          {typeof candidate.durationSec === "number" ? (
            <span className="audio-chip">{candidate.durationSec}s</span>
          ) : null}
          {candidate.loop ? <span className="audio-chip">Loop</span> : null}
          {approved ? <span className="audio-chip audio-chip--success">Approved</span> : null}
          {failed ? <span className="audio-chip audio-chip--warn">Failed</span> : null}
        </div>
      </div>

      {candidate.subtitle && failed ? <p className="audio-candidate-card__error">{candidate.subtitle}</p> : null}
      {playable ? (
        <AudioRow audioUrl={candidate.audioUrl} label={candidate.title} testId={`audio-candidate-player-${candidate.id}`} />
      ) : (
        <p className="muted">{failed ? "This take did not finish." : "Still making this take…"}</p>
      )}

      <div className="audio-candidate-card__actions">
        <Button
          variant={previewSelected ? "secondary" : "ghost"}
          selected={previewSelected}
          onClick={onPreview}
          disabled={!playable}
        >
          {previewSelected ? "Selected" : "Select"}
        </Button>
        <Button variant="primary" onClick={() => void onApprove()} disabled={busy || approved || !playable}>
          {approved ? "Approved" : "Approve"}
        </Button>
        {onPrimary && primaryLabel ? (
          <Button variant="secondary" onClick={() => void onPrimary()} disabled={busy || !playable}>
            {primaryLabel}
          </Button>
        ) : null}
      </div>
    </article>
  );
}
