type GenerationProgressBarProps = {
  visible: boolean;
  percent: number;
  label: string;
  active?: boolean;
  onCancel?: () => void;
  cancelDisabled?: boolean;
};

export function GenerationProgressBar({
  visible,
  percent,
  label,
  active = false,
  onCancel,
  cancelDisabled = false,
}: GenerationProgressBarProps) {
  if (!visible) return null;
  const clamped = Math.max(0, Math.min(100, Math.round(percent)));
  return (
    <div
      className={`audio-gen-progress${active ? " is-active" : ""}`}
      data-testid="audio-generation-progress"
    >
      <div className="audio-gen-progress__meta">
        <span className="audio-gen-progress__label">{label || "Generating…"}</span>
        <span className="audio-gen-progress__percent" aria-live="polite">
          {clamped}%
        </span>
      </div>
      <div
        className="audio-gen-progress__track"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={clamped}
        aria-label={label || "Generation progress"}
      >
        <div className="audio-gen-progress__fill" style={{ width: `${clamped}%` }} />
      </div>
      {active && onCancel ? (
        <button
          type="button"
          className="audio-gen-progress__cancel"
          data-testid="audio-generation-cancel"
          disabled={cancelDisabled}
          onClick={() => onCancel()}
        >
          Cancel generation
        </button>
      ) : null}
    </div>
  );
}
