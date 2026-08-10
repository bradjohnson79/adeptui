import { HelpTip } from "../HelpTip";
import { Button } from "../ui";
import { CandidateCard } from "./CandidateCard";
import { GenerationProgressBar } from "./GenerationProgressBar";
import type { AudioCandidate, AudioGenerationProgress } from "./types";

type SfxPanelProps = {
  busy: boolean;
  generationProgress?: AudioGenerationProgress | null;
  onCancelGeneration?: () => Promise<void> | void;
  category: string;
  durationSec: number;
  intensity: string;
  prompt: string;
  candidates: AudioCandidate[];
  previewAssetId?: string | null;
  approvedAssetIds: Record<string, boolean>;
  onCategoryChange: (value: string) => void;
  onDurationChange: (value: number) => void;
  onIntensityChange: (value: string) => void;
  onPromptChange: (value: string) => void;
  onGenerate: () => Promise<void> | void;
  onPreview: (candidate: AudioCandidate) => void;
  onApprove: (candidate: AudioCandidate) => Promise<void> | void;
  onAddToTimeline: (candidate: AudioCandidate) => Promise<void> | void;
  onOpenAdvanced: () => void;
};

const CATEGORIES = [
  "Foley",
  "Reaction",
  "Impact",
  "Environment",
  "Technology",
  "Creature",
  "Mechanical",
  "Transition",
  "Room Tone",
  "Custom",
] as const;

const INTENSITIES = ["Soft", "Natural", "Bold", "Huge"] as const;

export function SfxPanel({
  busy,
  generationProgress = null,
  category,
  durationSec,
  intensity,
  prompt,
  candidates,
  previewAssetId,
  approvedAssetIds,
  onCategoryChange,
  onDurationChange,
  onIntensityChange,
  onPromptChange,
  onGenerate,
  onCancelGeneration,
  onPreview,
  onApprove,
  onAddToTimeline,
  onOpenAdvanced,
}: SfxPanelProps) {
  return (
    <section className="audio-studio-panel">
      <div className="audio-studio-panel__hero">
        <div>
          <p className="audio-studio-panel__eyebrow">Moments and details</p>
          <h3>Build the little sounds that sell the scene.</h3>
          <p className="muted">Choose a category, set the strength, and describe the action in plain language.</p>
        </div>
        <Button variant="ghost" onClick={onOpenAdvanced}>
          Advanced
        </Button>
      </div>

      <div className="audio-field audio-field--full">
        <span className="audio-field__label">
          Category
          <HelpTip text="Pick the type of sound you need. Use Custom when your idea crosses categories." />
        </span>
        <div className="audio-chip-row">
          {CATEGORIES.map((option) => (
            <button
              key={option}
              type="button"
              className={`audio-chip${category === option ? " is-selected" : ""}`}
              onClick={() => onCategoryChange(option)}
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
            min={1}
            max={60}
            step={1}
            value={durationSec}
            onChange={(e) => onDurationChange(Number(e.target.value) || 1)}
          />
        </label>

        <label className="audio-field">
          <span className="audio-field__label">Intensity</span>
          <select value={intensity} onChange={(e) => onIntensityChange(e.target.value)}>
            {INTENSITIES.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>

        <label className="audio-field audio-field--full">
          <span className="audio-field__label">
            Prompt
            <HelpTip text="Describe the action, texture, and perspective of the sound." />
          </span>
          <textarea
            rows={4}
            value={prompt}
            onChange={(e) => onPromptChange(e.target.value)}
            placeholder="Tight leather glove gripping a steering wheel, close-mic detail."
          />
        </label>
      </div>

      <div className="audio-studio-panel__footer">
        <div className="audio-studio-panel__generate">
          <Button
            variant="primary"
            loading={busy}
            onClick={() => void onGenerate()}
            data-testid="audio-sfx-generate"
          >
            Generate 3 Sounds
          </Button>
          <GenerationProgressBar
            visible={Boolean(generationProgress?.visible || busy)}
            percent={generationProgress?.percent ?? 0}
            label={generationProgress?.label || (busy ? "Starting generation…" : "Ready")}
            active={Boolean(busy || generationProgress?.active)}
            onCancel={onCancelGeneration}
          />
        </div>
        <p className="muted">Great for hits, textures, movement, and tiny storytelling moments.</p>
      </div>

      {candidates.length ? (
        <div className="audio-candidate-grid">
          {candidates.map((candidate) => (
            <CandidateCard
              key={candidate.id}
              candidate={candidate}
              ctaLabel="Sound"
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
          <strong>Your sound ideas will appear here.</strong>
          <p className="muted">Start with what the audience should feel, then add the physical detail.</p>
        </div>
      )}
    </section>
  );
}
