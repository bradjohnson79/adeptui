import { useEffect, useRef, useState } from "react";

type TimeStepperFieldProps = {
  label: string;
  value: number;
  min?: number;
  max?: number;
  step?: number;
  testId?: string;
  suffix?: string;
  /** Live typed number. Does not replace the text — callers must not push it back into `value` until it is saved. */
  onDraft?: (next: number | null) => void;
  onChange: (next: number) => void;
};

function decimalPlaces(step: number) {
  return step >= 1 ? 0 : String(step).split(".")[1]?.length || 2;
}

export function roundTime(value: number, step: number) {
  const factor = 10 ** decimalPlaces(step);
  return Math.round(value * factor) / factor;
}

export function formatTime(value: number, step: number) {
  return roundTime(value, step).toFixed(decimalPlaces(step));
}

/** Parse a typed duration. Empty or unfinished input keeps the previous number. */
export function commitTypedTime(
  raw: string,
  fallback: number,
  min: number,
  step: number,
  max?: number,
): number {
  const trimmed = raw.trim();
  const clamp = (value: number) => {
    let next = roundTime(Math.max(min, value), step);
    if (max != null && Number.isFinite(max)) next = Math.min(next, roundTime(max, step));
    return next;
  };
  if (!trimmed || trimmed === ".") return clamp(fallback);
  const next = Number(trimmed);
  if (!Number.isFinite(next)) return clamp(fallback);
  return clamp(next);
}

export function TimeStepperField({
  label,
  value,
  min = 0,
  max,
  step = 0.01,
  testId,
  suffix = "s",
  onDraft,
  onChange,
}: TimeStepperFieldProps) {
  const display = Number.isFinite(value) ? roundTime(Math.max(min, value), step) : min;
  const [text, setText] = useState(() => formatTime(display, step));
  const textRef = useRef(text);
  textRef.current = text;
  const focusedRef = useRef(false);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  const onDraftRef = useRef(onDraft);
  onDraftRef.current = onDraft;
  const pendingDraftRef = useRef<number | null>(null);

  useEffect(() => {
    if (focusedRef.current) return;
    if (
      pendingDraftRef.current != null &&
      roundTime(pendingDraftRef.current, step) !== display
    ) {
      return;
    }
    pendingDraftRef.current = null;
    setText(formatTime(display, step));
  }, [display, step]);

  const commit = (raw: string) => {
    const next = commitTypedTime(raw, display, min, step, max);
    pendingDraftRef.current = next !== display ? next : null;
    setText(formatTime(next, step));
    if (next !== display) onChangeRef.current(next);
  };

  return (
    <label className="field">
      <span>{label}</span>
      <div className="row" style={{ alignItems: "center", gap: "0.4rem", flexWrap: "nowrap" }}>
        <button
          type="button"
          aria-label={`Decrease ${label}`}
          onClick={() =>
            onChange(roundTime(Math.max(min, (max != null ? Math.min(max, display) : display) - step), step))
          }
        >
          −
        </button>
        <input
          type="text"
          inputMode="decimal"
          autoComplete="off"
          data-testid={testId}
          value={text}
          onFocus={(event) => {
            focusedRef.current = true;
            const field = event.currentTarget;
            requestAnimationFrame(() => field.select());
          }}
          onChange={(event) => {
            const raw = event.target.value;
            if (raw !== "" && !/^\d*\.?\d*$/.test(raw)) return;
            textRef.current = raw;
            setText(raw);
            const parsed = Number(raw);
            onDraftRef.current?.(raw.trim() && Number.isFinite(parsed) ? parsed : null);
          }}
          onBlur={() => {
            focusedRef.current = false;
            commit(textRef.current);
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              (event.currentTarget as HTMLInputElement).blur();
            }
          }}
        />
        {suffix ? <span className="scene-meta">{suffix}</span> : null}
        <button
          type="button"
          aria-label={`Increase ${label}`}
          onClick={() => {
            const raised = roundTime(display + step, step);
            onChange(max != null ? Math.min(roundTime(max, step), raised) : raised);
          }}
        >
          +
        </button>
      </div>
    </label>
  );
}
