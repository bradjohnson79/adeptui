import { Button } from "../ui";
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
  return (
    <article className="audio-candidate-card" data-testid={`audio-candidate-${candidate.id}`}>
      <div className="audio-candidate-card__meta">
        <div>
          <p className="audio-candidate-card__eyebrow">{candidate.typeLabel || ctaLabel}</p>
          <h4>{candidate.title}</h4>
        </div>
        <div className="audio-candidate-card__chips">
          {typeof candidate.durationSec === "number" ? (
            <span className="audio-chip audio-chip--subtle">{candidate.durationSec}s</span>
          ) : null}
          {candidate.loop ? <span className="audio-chip audio-chip--subtle">Loopable</span> : null}
          {approved ? <span className="audio-chip audio-chip--success">Approved</span> : null}
        </div>
      </div>

      {candidate.subtitle ? <p className="audio-candidate-card__subtitle">{candidate.subtitle}</p> : null}
      {candidate.description ? <p className="audio-candidate-card__description">{candidate.description}</p> : null}
      {candidate.audioUrl ? (
        <audio
          key={candidate.audioUrl}
          controls
          preload="metadata"
          src={candidate.audioUrl}
          className="audio-candidate-card__player"
          data-asset-id={candidate.assetId || ""}
          data-testid={`audio-candidate-player-${candidate.id}`}
        />
      ) : null}

      <div className="audio-candidate-card__actions">
        <Button
          variant={previewSelected ? "secondary" : "ghost"}
          selected={previewSelected}
          onClick={onPreview}
        >
          {previewSelected ? "Selected for Preview" : "Select for Preview"}
        </Button>
        <Button variant="primary" onClick={() => void onApprove()} disabled={busy || approved}>
          {approved ? "Approved Track" : "Approve Track"}
        </Button>
        {onPrimary && primaryLabel ? (
          <Button variant="secondary" onClick={() => void onPrimary()} disabled={busy}>
            {primaryLabel}
          </Button>
        ) : null}
      </div>
    </article>
  );
}
