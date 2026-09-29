import { useState } from "react";
import type { TimelineGeneratorOption } from "../../timelineMaster/draftCapabilities";
import { useTimelineEditorModal } from "./useTimelineEditorModal";

function formatSec(value: number) {
  return `${Math.round(value * 10) / 10}s`;
}

export function TimelineRetakePromptModal({
  sceneStart,
  length,
  batchLabel,
  generator,
  busy,
  error,
  onCancel,
  onConfirm,
}: {
  sceneStart: number;
  length: number;
  batchLabel: string;
  generator: TimelineGeneratorOption | null;
  busy?: boolean;
  error?: string | null;
  onCancel: () => void;
  onConfirm: (prompt: string) => void;
}) {
  const [prompt, setPrompt] = useState("");
  const { dialogRef, stopHotkeys } = useTimelineEditorModal(true, onCancel, "textarea");
  const engine = generator?.label || "No engine selected";
  const supportsRange = Boolean(
    generator?.executable &&
      generator.supportsTimelineGeneration !== false &&
      (generator.inPaintStrategies || []).includes("range_replacement"),
  );
  const hosted = generator?.executionType === "api" || generator?.locality === "hosted";
  const limitation = !generator
    ? "Select an engine for this shot. Adept will not pick one for you."
    : !generator.executable
      ? generator.disabledReason || generator.readiness || `${engine} is not ready for Re-take yet.`
      : !supportsRange
        ? `${engine} cannot replace a marked region. Use New take to remake the whole shot.`
        : hosted
          ? `${engine} uses paid credits. Bounded Re-take is not started from here.`
          : null;
  const canReplace = supportsRange && !hosted && !busy && prompt.trim().length > 0;

  return (
    <div className="codirector-modal-backdrop" role="presentation" onClick={onCancel} onKeyDown={stopHotkeys}>
      <div
        ref={dialogRef}
        className="codirector-modal card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="timeline-retake-title"
        data-testid="timeline-retake-prompt-modal"
        onClick={(event) => event.stopPropagation()}
        onKeyDown={stopHotkeys}
      >
        <div className="codirector-modal-head">
          <h2 id="timeline-retake-title">Replace this part</h2>
        </div>
        <p className="scene-meta" data-testid="timeline-retake-range-summary">
          {formatSec(sceneStart)}–{formatSec(sceneStart + length)} on {batchLabel}
        </p>
        <p className="scene-meta" data-testid="timeline-retake-engine">
          Engine: {engine}
        </p>
        {limitation ? (
          <p className="scene-meta" data-testid="timeline-retake-limitation">
            {limitation}
          </p>
        ) : (
          <label className="field">
            <span>What should happen here</span>
            <textarea
              data-testid="timeline-retake-prompt"
              rows={6}
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="Describe only the marked part. The rest of the shot stays as it is."
            />
          </label>
        )}
        {error ? (
          <p className="scene-meta" data-testid="timeline-retake-error">
            {error}
          </p>
        ) : null}
        <div className="codirector-modal-actions">
          <button type="button" data-testid="timeline-retake-cancel" onClick={onCancel}>
            Cancel
          </button>
          <button
            type="button"
            className="primary"
            data-testid="timeline-retake-confirm"
            disabled={!canReplace}
            onClick={() => onConfirm(prompt.trim())}
          >
            {busy ? "Replacing…" : "Replace this part"}
          </button>
        </div>
      </div>
    </div>
  );
}
