import { HelpTip } from "../HelpTip";
import { Button } from "../ui";
import { CandidateCard } from "./CandidateCard";
import { GenerationProgressBar } from "./GenerationProgressBar";
import type { AudioCandidate, AudioGenerationProgress } from "./types";

type AmbiencePanelProps = {
  busy: boolean;
  sourceReady: boolean;
  sourceLabel: string;
  generationProgress?: AudioGenerationProgress | null;
  onCancelGeneration?: () => Promise<void> | void;
  durationSec: number;
  intensity: string;
  loop: boolean;
  prompt: string;
  candidateCount: 1 | 2 | 3;
  candidates: AudioCandidate[];
  previewAssetId?: string | null;
  approvedAssetIds: Record<string, boolean>;
  onDurationChange: (value: number) => void;
  onIntensityChange: (value: string) => void;
  onLoopChange: (value: boolean) => void;
  onPromptChange: (value: string) => void;
  onCandidateCountChange: (value: 1 | 2 | 3) => void;
  onGenerate: () => Promise<void> | void;
  onPreview: (candidate: AudioCandidate) => void;
  onApprove: (candidate: AudioCandidate) => Promise<void> | void;
  onAddToTimeline: (candidate: AudioCandidate) => Promise<void> | void;
};

const INTENSITIES = ["Still", "Quiet", "Alive", "Busy"] as const;
const STARTERS = [
  { label: "Spaceship corridor", prompt: "Quiet spaceship corridor, distant systems, low air.", eventType: "ambience" },
  { label: "Rain outside", prompt: "Rain outside an apartment window, soft and steady.", eventType: "ambience" },
  { label: "Ship ventilation", prompt: "Ship ventilation ambience, steady mechanical air and distant duct tone.", eventType: "ambience" },
];

export function AmbiencePanel({
  busy,
  sourceReady,
  sourceLabel,
  generationProgress = null,
  durationSec,
  intensity,
  loop,
  prompt,
  candidateCount,
  candidates,
  previewAssetId,
  approvedAssetIds,
  onDurationChange,
  onIntensityChange,
  onLoopChange,
  onPromptChange,
  onCandidateCountChange,
  onGenerate,
  onCancelGeneration,
  onPreview,
  onApprove,
  onAddToTimeline,
}: AmbiencePanelProps) {
  return (
    <section className="audio-studio-panel" data-testid="audio-ambience-panel">
      <div className="audio-studio-panel__hero">
        <div>
          <h3>Ambience</h3>
          <p className="muted">Lay a room under the scene. Loop it if the shot needs to breathe.</p>
        </div>
        <span className={`audio-source${sourceReady ? " is-ready" : " is-blocked"}`}>{sourceLabel}</span>
      </div>

      <div className="audio-chip-row">
        {STARTERS.map((item) => (
          <button key={item.label} type="button" className="audio-chip" onClick={() => onPromptChange(item.prompt)}>
            {item.label}
          </button>
        ))}
      </div>

      <label className="audio-field audio-field--full">
        <span className="audio-field__label">
          Where are we?
          <HelpTip text="Name the place first. Add weather or activity only if it matters." />
        </span>
        <textarea
          rows={3}
          value={prompt}
          onChange={(e) => onPromptChange(e.target.value)}
          placeholder="Quiet spaceship corridor, distant systems, low air."
          data-testid="audio-ambience-prompt"
        />
      </label>

      <div className="audio-form-grid audio-form-grid--compact">
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
          <span className="audio-field__label">Activity</span>
          <select value={intensity} onChange={(e) => onIntensityChange(e.target.value)}>
            {INTENSITIES.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
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

      <div className="audio-studio-panel__footer">
        <Button
          variant="primary"
          loading={busy}
          disabled={!sourceReady || !prompt.trim()}
          onClick={() => void onGenerate()}
          data-testid="audio-ambience-generate"
        >
          {`Generate ${candidateCount} ${candidateCount === 1 ? "Bed" : "Beds"}`}
        </Button>
        <GenerationProgressBar
          visible={Boolean(generationProgress?.visible || busy)}
          percent={generationProgress?.percent ?? 0}
          label={generationProgress?.label || (busy ? "Starting…" : "Ready")}
          active={Boolean(busy || generationProgress?.active)}
          onCancel={onCancelGeneration}
        />
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
          <strong>Your scene beds will appear here.</strong>
          <p className="muted">Approve a bed, then send it to the ambience track.</p>
        </div>
      )}
    </section>
  );
}
