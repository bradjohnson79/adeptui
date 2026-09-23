import { HelpTip } from "../HelpTip";
import { Button } from "../ui";
import { CandidateCard } from "./CandidateCard";
import { GenerationProgressBar } from "./GenerationProgressBar";
import type { AudioCandidate, AudioGenerationProgress } from "./types";

type MusicPanelProps = {
  busy: boolean;
  sourceReady: boolean;
  sourceLabel: string;
  mood: string;
  genre: string;
  durationSec: number;
  energy: string;
  instrumentation: string;
  loop: boolean;
  prompt: string;
  candidateCount: 1 | 2 | 3;
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
  onCandidateCountChange: (value: 1 | 2 | 3) => void;
  onGenerate: () => Promise<void> | void;
  onCancelGeneration?: () => Promise<void> | void;
  onPreview: (candidate: AudioCandidate) => void;
  onApprove: (candidate: AudioCandidate) => Promise<void> | void;
  onAddToTimeline: (candidate: AudioCandidate) => Promise<void> | void;
};

const MOODS = ["Hopeful", "Tense", "Playful", "Epic", "Melancholic", "Dreamy"];
const GENRES = ["Cinematic", "Electronic", "Orchestral", "Ambient", "Acoustic", "Hybrid"];
const ENERGIES = ["Gentle", "Steady", "Rising", "Punchy", "Explosive"];
const STARTERS = [
  { label: "Tense orchestral", prompt: "A tense orchestral cue for a corridor standoff.", mood: "Tense", genre: "Orchestral" },
  { label: "Hopeful rise", prompt: "A cinematic rise that feels warm and ready for the next chapter.", mood: "Hopeful", genre: "Cinematic" },
  { label: "Quiet tension", prompt: "Low strings and held breath under a silent chase.", mood: "Tense", genre: "Ambient" },
];

export function MusicPanel({
  busy,
  sourceReady,
  sourceLabel,
  mood,
  genre,
  durationSec,
  energy,
  instrumentation,
  loop,
  prompt,
  candidateCount,
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
  onCandidateCountChange,
  onGenerate,
  onCancelGeneration,
  onPreview,
  onApprove,
  onAddToTimeline,
}: MusicPanelProps) {
  return (
    <section className="audio-studio-panel" data-testid="audio-music-panel">
      <div className="audio-studio-panel__hero">
        <div>
          <h3>Music</h3>
          <p className="muted">Describe the cue. Hear a few takes. Keep the one you want.</p>
        </div>
        <span className={`audio-source${sourceReady ? " is-ready" : " is-blocked"}`}>{sourceLabel}</span>
      </div>

      <div className="audio-chip-row" data-testid="audio-music-starters">
        {STARTERS.map((item) => (
          <button
            key={item.label}
            type="button"
            className="audio-chip"
            onClick={() => {
              onPromptChange(item.prompt);
              onMoodChange(item.mood);
              onGenreChange(item.genre);
            }}
          >
            {item.label}
          </button>
        ))}
      </div>

      <label className="audio-field audio-field--full">
        <span className="audio-field__label">
          What should it sound like?
          <HelpTip text="Say the feeling and the scene in plain language." />
        </span>
        <textarea
          rows={3}
          value={prompt}
          onChange={(e) => onPromptChange(e.target.value)}
          placeholder="A tense orchestral cue for this corridor scene."
          data-testid="audio-music-prompt"
        />
      </label>

      <div className="audio-form-grid audio-form-grid--compact">
        <label className="audio-field">
          <span className="audio-field__label">Mood</span>
          <select value={mood} onChange={(e) => onMoodChange(e.target.value)}>
            {MOODS.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </label>
        <label className="audio-field">
          <span className="audio-field__label">How long?</span>
          <input
            type="number"
            min={4}
            max={20}
            step={1}
            value={durationSec}
            onChange={(e) => onDurationChange(Number(e.target.value) || 8)}
          />
        </label>
        <label className="audio-field">
          <span className="audio-field__label">Takes</span>
          <select
            value={candidateCount}
            onChange={(e) => onCandidateCountChange(Number(e.target.value) as 1 | 2 | 3)}
          >
            <option value={1}>1</option>
            <option value={2}>2</option>
            <option value={3}>3</option>
          </select>
        </label>
        <label className="audio-toggle">
          <input type="checkbox" checked={loop} onChange={(e) => onLoopChange(e.target.checked)} />
          <span>Loop</span>
        </label>
      </div>

      <details className="audio-more">
        <summary>More</summary>
        <div className="audio-form-grid audio-form-grid--compact">
          <label className="audio-field">
            <span className="audio-field__label">Genre</span>
            <select value={genre} onChange={(e) => onGenreChange(e.target.value)}>
              {GENRES.map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
          </label>
          <label className="audio-field">
            <span className="audio-field__label">Energy</span>
            <select value={energy} onChange={(e) => onEnergyChange(e.target.value)}>
              {ENERGIES.map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
          </label>
          <label className="audio-field audio-field--wide">
            <span className="audio-field__label">Instruments</span>
            <input
              type="text"
              value={instrumentation}
              onChange={(e) => onInstrumentationChange(e.target.value)}
              placeholder="Warm strings, piano"
            />
          </label>
        </div>
      </details>

      <div className="audio-studio-panel__footer">
        <Button
          variant="primary"
          loading={busy}
          disabled={!sourceReady || !prompt.trim()}
          onClick={() => void onGenerate()}
          data-testid="audio-music-generate"
        >
          {`Generate ${candidateCount} ${candidateCount === 1 ? "Track" : "Tracks"}`}
        </Button>
        <GenerationProgressBar
          visible={Boolean(generationProgress?.visible || busy)}
          percent={generationProgress?.percent ?? 0}
          label={generationProgress?.label || (busy ? "Starting…" : "Ready")}
          active={Boolean(busy || generationProgress?.active)}
          onCancel={onCancelGeneration}
          cancelDisabled={!onCancelGeneration}
        />
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
          <strong>Your tracks will appear here.</strong>
          <p className="muted">Play them, pick one, approve it, then send it to Timeline.</p>
        </div>
      )}
    </section>
  );
}
