import { HelpTip } from "../HelpTip";
import { Button } from "../ui";
import { CandidateCard } from "./CandidateCard";
import { GenerationProgressBar } from "./GenerationProgressBar";
import type { AudioCandidate, AudioGenerationProgress } from "./types";

type MusicPanelProps = {
  busy: boolean;
  mood: string;
  genre: string;
  durationSec: number;
  energy: string;
  instrumentation: string;
  loop: boolean;
  prompt: string;
  candidates: AudioCandidate[];
  previewAssetId?: string | null;
  approvedAssetIds: Record<string, boolean>;
  generationProgress?: AudioGenerationProgress | null;
  onMoodChange: (value: string) => void;
  onGenreChange: (value: string) => void;
  onDurationChange: (value: number) => void;
  onEnergyChange: (value: string) => void;
  onInstrumentationChange: (value: string) => void;
  onLoopChange: (value: boolean) => void;
  onPromptChange: (value: string) => void;
  onGenerate: () => Promise<void> | void;
  onCancelGeneration?: () => Promise<void> | void;
  onPreview: (candidate: AudioCandidate) => void;
  onApprove: (candidate: AudioCandidate) => Promise<void> | void;
  onAddToTimeline: (candidate: AudioCandidate) => Promise<void> | void;
  onOpenAdvanced: () => void;
};

const MOODS = ["Hopeful", "Tense", "Playful", "Epic", "Melancholic", "Dreamy"];
const GENRES = ["Cinematic", "Electronic", "Orchestral", "Ambient", "Acoustic", "Hybrid"];
const ENERGIES = ["Gentle", "Steady", "Rising", "Punchy", "Explosive"];

export function MusicPanel({
  busy,
  mood,
  genre,
  durationSec,
  energy,
  instrumentation,
  loop,
  prompt,
  candidates,
  previewAssetId,
  approvedAssetIds,
  generationProgress = null,
  onMoodChange,
  onGenreChange,
  onDurationChange,
  onEnergyChange,
  onInstrumentationChange,
  onLoopChange,
  onPromptChange,
  onGenerate,
  onCancelGeneration,
  onPreview,
  onApprove,
  onAddToTimeline,
  onOpenAdvanced,
}: MusicPanelProps) {
  return (
    <section className="audio-studio-panel">
      <div className="audio-studio-panel__hero">
        <div>
          <p className="audio-studio-panel__eyebrow">Original score ideas</p>
          <h3>Shape the feeling before you generate.</h3>
          <p className="muted">
            Start with the mood, then add just enough detail for the first three track ideas.
          </p>
        </div>
        <Button variant="ghost" onClick={onOpenAdvanced}>
          Advanced
        </Button>
      </div>

      <div className="audio-form-grid">
        <label className="audio-field">
          <span className="audio-field__label">
            Mood
            <HelpTip text="Choose the emotional tone you want the score to carry." />
          </span>
          <select value={mood} onChange={(e) => onMoodChange(e.target.value)}>
            {MOODS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>

        <label className="audio-field">
          <span className="audio-field__label">
            Genre
            <HelpTip text="This guides the musical style, not the final arrangement." />
          </span>
          <select value={genre} onChange={(e) => onGenreChange(e.target.value)}>
            {GENRES.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>

        <label className="audio-field">
          <span className="audio-field__label">Duration</span>
          <input
            type="number"
            min={5}
            max={20}
            step={1}
            value={durationSec}
            onChange={(e) => onDurationChange(Number(e.target.value) || 5)}
          />
        </label>

        <label className="audio-field">
          <span className="audio-field__label">Energy</span>
          <select value={energy} onChange={(e) => onEnergyChange(e.target.value)}>
            {ENERGIES.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>

        <label className="audio-field audio-field--wide">
          <span className="audio-field__label">Instrumentation</span>
          <input
            type="text"
            value={instrumentation}
            onChange={(e) => onInstrumentationChange(e.target.value)}
            placeholder="Warm strings, airy piano, light pulses"
          />
        </label>

        <label className="audio-toggle">
          <input type="checkbox" checked={loop} onChange={(e) => onLoopChange(e.target.checked)} />
          <span>Loop</span>
        </label>

        <label className="audio-field audio-field--full">
          <span className="audio-field__label">
            Prompt
            <HelpTip text="Describe the scene or emotional arc in plain language." />
          </span>
          <textarea
            rows={4}
            value={prompt}
            onChange={(e) => onPromptChange(e.target.value)}
            placeholder="A hopeful build that feels like sunrise over a city waking up."
          />
        </label>
      </div>

      <div className="audio-studio-panel__footer">
        <div className="audio-studio-panel__generate">
          <Button
            variant="primary"
            loading={busy}
            onClick={() => void onGenerate()}
            data-testid="audio-music-generate"
          >
            Generate 3 Tracks
          </Button>
          <GenerationProgressBar
            visible={Boolean(generationProgress?.visible || busy)}
            percent={generationProgress?.percent ?? (busy ? 0 : 0)}
            label={
              generationProgress?.label ||
              (busy ? "Starting generation…" : "Ready")
            }
            active={Boolean(busy || generationProgress?.active)}
            onCancel={onCancelGeneration}
            cancelDisabled={!onCancelGeneration}
          />
        </div>
        <p className="muted">Preview one, approve your favorite, then send it to your project audio shelf.</p>
      </div>

      {candidates.length ? (
        <div className="audio-candidate-grid">
          {candidates.map((candidate) => (
            <CandidateCard
              key={candidate.id}
              candidate={candidate}
              ctaLabel="Track"
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
          <strong>Your three track ideas will land here.</strong>
          <p className="muted">Use simple creative language. You can refine the details after you hear the first pass.</p>
        </div>
      )}
    </section>
  );
}
