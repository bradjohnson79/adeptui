type TimeStepperFieldProps = {
  label: string;
  value: number;
  min?: number;
  step?: number;
  testId?: string;
  onChange: (next: number) => void;
};

function roundTime(value: number, step: number) {
  const places = step >= 1 ? 0 : String(step).split(".")[1]?.length || 2;
  const factor = 10 ** places;
  return Math.round(value * factor) / factor;
}

export function TimeStepperField({
  label,
  value,
  min = 0,
  step = 0.01,
  testId,
  onChange,
}: TimeStepperFieldProps) {
  const display = Number.isFinite(value) ? roundTime(Math.max(min, value), step) : min;
  return (
    <label className="field">
      <span>{label}</span>
      <div className="row" style={{ alignItems: "center", gap: "0.4rem", flexWrap: "nowrap" }}>
        <button
          type="button"
          aria-label={`Decrease ${label}`}
          onClick={() => onChange(roundTime(Math.max(min, display - step), step))}
        >
          −
        </button>
        <input
          type="number"
          data-testid={testId}
          value={display.toFixed(2)}
          step={step}
          min={min}
          onChange={(event) => {
            const next = Number(event.target.value);
            onChange(Number.isFinite(next) ? Math.max(min, next) : min);
          }}
        />
        <span className="scene-meta">s</span>
        <button
          type="button"
          aria-label={`Increase ${label}`}
          onClick={() => onChange(roundTime(display + step, step))}
        >
          +
        </button>
      </div>
    </label>
  );
}
