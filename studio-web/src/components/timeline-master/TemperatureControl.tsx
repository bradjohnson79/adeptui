import { useState } from "react";

export const TEMPERATURE_HELP_TEXT =
  "Temperature controls how creatively the generator interprets this timed prompt. Lower values favor more consistent and predictable interpretation. Higher values allow more variation and creative freedom.";

export const DEFAULT_PROMPT_TEMPERATURE = 1.0;

function TemperatureTip({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  return (
    <span data-testid="timeline-temperature-tooltip" style={{ position: "relative", display: "inline-block" }}>
      <button
        type="button"
        className={`help-tip${open ? " help-tip--open" : ""}`}
        aria-label="Temperature help"
        aria-expanded={open}
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          onToggle();
        }}
      >
        <span className="help-tip-icon" aria-hidden="true">
          ?
        </span>
      </button>
      {open ? (
        <span className="help-tip-bubble" role="tooltip" data-testid="timeline-temperature-tooltip-text">
          {TEMPERATURE_HELP_TEXT}
        </span>
      ) : null}
    </span>
  );
}

export function TemperatureControl({
  value,
  supported,
  onChange,
}: {
  value: number | null | undefined;
  supported: boolean;
  onChange: (next: number) => void;
}) {
  const [tipOpen, setTipOpen] = useState(false);
  const display = Number.isFinite(Number(value)) ? Number(value) : DEFAULT_PROMPT_TEMPERATURE;

  if (!supported) {
    return (
      <label className="field" data-testid="timeline-temperature-control">
        <span>
          Temperature <TemperatureTip open={tipOpen} onToggle={() => setTipOpen((open) => !open)} />
        </span>
        <p className="scene-meta" data-testid="timeline-temperature-unavailable">
          Temperature unavailable for this generator.
        </p>
      </label>
    );
  }

  return (
    <label className="field" data-testid="timeline-temperature-control">
      <span>
        Temperature <TemperatureTip open={tipOpen} onToggle={() => setTipOpen((open) => !open)} />
      </span>
      <div className="row" style={{ alignItems: "center", gap: "0.6rem" }}>
        <input
          type="range"
          min={0}
          max={2}
          step={0.05}
          value={display}
          aria-label="Temperature"
          onChange={(event) => onChange(Number(event.target.value))}
        />
        <input
          type="number"
          min={0}
          max={2}
          step={0.05}
          value={display}
          aria-label="Temperature value"
          onChange={(event) => {
            const next = Number(event.target.value);
            onChange(Number.isFinite(next) ? Math.min(2, Math.max(0, next)) : DEFAULT_PROMPT_TEMPERATURE);
          }}
        />
      </div>
    </label>
  );
}
