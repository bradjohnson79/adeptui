import { HelpTip } from "../HelpTip";
import { Button } from "../ui";
import { CandidateCard } from "./CandidateCard";
import { GenerationProgressBar } from "./GenerationProgressBar";
import type { AudioCandidate, AudioGenerationProgress } from "./types";

type AmbiencePanelProps = {
  busy: boolean;
  generationProgress?: AudioGenerationProgress | null;
  onCancelGeneration?: () => Promise<void> | void;
  preset: string;
  durationSec: number;
  loop: boolean;
  prompt: string;
  candidates: AudioCandidate[];
  previewAssetId?: string | null;
  approvedAssetIds: Record<string, boolean>;
  onPresetChange: (value: string) => void;
  onDurationChange: (value: number) => void;
  onLoopChange: (value: boolean) => void;
  onPromptChange: (value: string) => void;
  onGenerate: () => Promise<void> | void;
  onPreview: (candidate: AudioCandidate) => void;
  onApprove: (candidate: AudioCandidate) => Promise<void> | void;
  onAddToTimeline: (candidate: AudioCandidate) => Promise<void> | void;
  onOpenAdvanced: () => void;
};

const PRESETS = [
  "Forest Morning",
  "Busy Marketplace",
  "Spaceship Engine",
  "Wind",
  "Rain",
  "Electrical Hum",
  "Hospital",
  "Night Jungle",
] as const;

export function AmbiencePanel({
  busy,
  generationProgress = null,
  preset,
  durationSec,
  loop,
  prompt,
  candidates,
  previewAssetId,
  approvedAssetIds,
  onPresetChange,
  onDurationChange,
  onLoopChange,
  onPromptChange,
  onGenerate,
  onCancelGeneration,
  onPreview,
  onApprove,
  onAddToTimeline,
  onOpenAdvanced,
}: AmbiencePanelProps) {
  return (
    <section className="audio-studio-panel">
      <div className="audio-studio-panel__hero">
        <div>
          <p className="audio-studio-panel__eyebrow">Scene beds</p>
          <h3>Lay down the world before the dialogue begins.</h3>
          <p className="muted">Choose a bed you can loop under the whole moment, then refine with a custom note.</p>
        </div>
        <Button variant="ghost" onClick={onOpenAdvanced}>
          Advanced
        </Button>
      </div>

      <div className="audio-field audio-field--full">
        <span className="audio-field__label">
          Scene bed preset
          <HelpTip text="Presets are fast starting points. Add a custom note to guide the texture or mood." />
        </span>
        <div className="audio-chip-row">
          {PRESETS.map((option) => (
            <button
              key={option}
              type="button"
              className={`audio-chip${preset === option ? " is-selected" : ""}`}
              onClick={() => onPresetChange(option)}
            >
              {option}
            </button>
          ))}
        </div>
      </div>

      <div className="audio-form-grid">
        <label className="audio-field">
          <span className="audio-field__label">Duration</span>
          <input
            type="number"
            min={5}
            max={300}
            step={1}
            value={durationSec}
            onChange={(e) => onDurationChange(Number(e.target.value) || 5)}
          />
        </label>

        <label className="audio-toggle">
          <input type="checkbox" checked={loop} onChange={(e) => onLoopChange(e.target.checked)} />
          <span>Loop by default</span>
        </label>

        <label className="audio-field audio-field--full">
          <span className="audio-field__label">
            Custom prompt
            <HelpTip text="Use this to steer density, time of day, weather, or emotional tone." />
          </span>
          <textarea
            rows={4}
            value={prompt}
            onChange={(e) => onPromptChange(e.target.value)}
            placeholder="Add soft faraway birds and a cool dawn breeze without crowd noise."
          />
        </label>
      </div>

      <div className="audio-studio-panel__footer">
        <div className="audio-studio-panel__generate">
          <Button
            variant="primary"
            loading={busy}
            onClick={() => void onGenerate()}
            data-testid="audio-ambience-generate"
          >
            Generate 3 Beds
          </Button>
          <GenerationProgressBar
            visible={Boolean(generationProgress?.visible || busy)}
            percent={generationProgress?.percent ?? 0}
            label={generationProgress?.label || (busy ? "Starting generation…" : "Ready")}
            active={Boolean(busy || generationProgress?.active)}
            onCancel={onCancelGeneration}
          />
        </div>
        <p className="muted">Ambience stays loop-friendly by default so creators can stretch it under the scene.</p>
      </div>

      {candidates.length ? (
        <div className="audio-candidate-grid">
          {candidates.map((candidate) => (
            <CandidateCard
              key={candidate.id}
              candidate={candidate}
              ctaLabel="Bed"
              busy={busy}
              previewSelected={previewAssetId === (candidate.assetId || candidate.id)}
              approved={Boolean(candidate.assetId && approvedAssetIds[candidate.assetId])}
              onPreview={() => onPreview(candidate)}
              onApprove={() => onApprove(candidate)}
              onPrimary={() => onAddToTimeline(candidate)}
              primaryLabel="Add to Timeline"
            />
          ))}
        </div>
      ) : (
        <div className="audio-empty-state">
          <strong>Your ambience beds will show up here.</strong>
          <p className="muted">Start broad first. Fine texture is easier to tune after you hear the room.</p>
        </div>
      )}
    </section>
  );
}
