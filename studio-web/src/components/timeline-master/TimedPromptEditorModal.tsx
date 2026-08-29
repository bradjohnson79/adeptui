import { useEffect, useState } from "react";
import { api } from "../../api";
import type { PromptSegment } from "../DirectorTracks";
import { resolveGeneratorOption } from "../../timelineMaster/draftCapabilities";
import { loadTimelineVideoGenerators } from "../../timelineMaster/useTimelineVideoGenerators";
import { generatorSupportsTemperature } from "./generatorSupportsTemperature";
import { DEFAULT_PROMPT_TEMPERATURE, TemperatureControl } from "./TemperatureControl";
import { TimeStepperField } from "./TimeStepperField";
import { useTimelineEditorModal } from "./useTimelineEditorModal";

type MovementChoice = { id: string; label: string; segmentNumber: number };

type Draft = {
  text: string;
  start: number;
  length: number;
  movementId: string;
  temperature: number;
};

export function TimedPromptEditorModal({
  segment,
  projectId,
  generatorId,
  generatorCapability,
  onCancel,
  onCommit,
}: {
  segment: PromptSegment;
  projectId: string;
  generatorId?: string | null;
  generatorCapability?: { supportsTemperature?: boolean } | null;
  onCancel: () => void;
  onCommit: (patch: Partial<PromptSegment>) => void | Promise<void>;
}) {
  const draftFromSegment = (row: PromptSegment): Draft => ({
    text: row.text || "",
    start: row.start,
    length: row.length,
    movementId: row.movement_segment_ref?.id || "",
    temperature: Number.isFinite(Number(row.temperature))
      ? Number(row.temperature)
      : DEFAULT_PROMPT_TEMPERATURE,
  });
  const [draft, setDraft] = useState<Draft>(() => draftFromSegment(segment));

  useEffect(() => {
    setDraft(draftFromSegment(segment));
  }, [segment.id, segment.text, segment.start, segment.length, segment.temperature, segment.movement_segment_ref?.id]);
  const [movementChoices, setMovementChoices] = useState<MovementChoice[]>([]);
  const [resolvedCapability, setResolvedCapability] = useState<{ supportsTemperature?: boolean } | null>(
    generatorCapability ?? null,
  );
  const { dialogRef, stopHotkeys } = useTimelineEditorModal(true, onCancel, "textarea");
  const supportsTemperature = generatorSupportsTemperature(generatorId, resolvedCapability);

  useEffect(() => {
    if (typeof generatorCapability?.supportsTemperature === "boolean") {
      setResolvedCapability(generatorCapability);
      return;
    }
    let alive = true;
    void loadTimelineVideoGenerators()
      .then((options) => {
        if (!alive) return;
        setResolvedCapability(resolveGeneratorOption(options, generatorId));
      })
      .catch(() => {
        if (alive) setResolvedCapability(null);
      });
    return () => {
      alive = false;
    };
  }, [generatorCapability, generatorId]);

  useEffect(() => {
    let alive = true;
    void api.spatialMap
      .listMaps(projectId)
      .then((res) => {
        if (!alive) return;
        const docs = (res.documents || []) as Array<{
          movementSegments?: Array<{ id: string; segmentNumber: number; beatName?: string }>;
        }>;
        const rows = docs[0]?.movementSegments || [];
        setMovementChoices(
          [...rows]
            .sort((a, b) => a.segmentNumber - b.segmentNumber)
            .map((row) => ({
              id: row.id,
              segmentNumber: row.segmentNumber,
              label: row.beatName ? `M${row.segmentNumber} — ${row.beatName}` : `Movement ${row.segmentNumber}`,
            })),
        );
      })
      .catch(() => {
        if (alive) setMovementChoices([]);
      });
    return () => {
      alive = false;
    };
  }, [projectId]);

  const commit = () => {
    const chosen = movementChoices.find((row) => row.id === draft.movementId);
    const patch: Partial<PromptSegment> = {
      text: draft.text,
      start: Math.max(0, draft.start),
      length: Math.max(0.15, draft.length),
      movement_segment_ref: chosen
        ? { id: chosen.id, segmentNumber: chosen.segmentNumber, alias: `M${chosen.segmentNumber}` }
        : null,
      movement_segment_revision: chosen ? 1 : null,
    };
    if (supportsTemperature) {
      patch.temperature = draft.temperature;
    }
    void onCommit(patch);
  };

  return (
    <div className="codirector-modal-backdrop" role="presentation" onClick={onCancel} onKeyDown={stopHotkeys}>
      <div
        ref={dialogRef}
        className="codirector-modal card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="timed-prompt-editor-title"
        data-testid="timeline-timed-prompt-modal"
        onClick={(event) => event.stopPropagation()}
        onKeyDown={stopHotkeys}
      >
        <div className="codirector-modal-head">
          <h2 id="timed-prompt-editor-title">Timed Prompt</h2>
        </div>
        <label className="field">
          <span>Timed Prompt</span>
          <textarea
            data-testid="timeline-timed-prompt-text"
            rows={8}
            value={draft.text}
            onChange={(event) => setDraft((current) => ({ ...current, text: event.target.value }))}
          />
        </label>
        <TimeStepperField
          label="Start"
          value={draft.start}
          min={0}
          testId="timeline-timed-prompt-start"
          onChange={(start) => setDraft((current) => ({ ...current, start }))}
        />
        <TimeStepperField
          label="Length"
          value={draft.length}
          min={0.15}
          testId="timeline-timed-prompt-length"
          onChange={(length) => setDraft((current) => ({ ...current, length }))}
        />
        {movementChoices.length ? (
          <label className="field">
            <span>Movement</span>
            <select
              data-testid="timeline-prompt-movement"
              value={draft.movementId}
              onChange={(event) => setDraft((current) => ({ ...current, movementId: event.target.value }))}
            >
              <option value="">None</option>
              {movementChoices.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.label}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        <TemperatureControl
          value={draft.temperature}
          supported={supportsTemperature}
          onChange={(temperature) => setDraft((current) => ({ ...current, temperature }))}
        />
        <div className="codirector-modal-actions">
          <button type="button" data-testid="timeline-timed-prompt-cancel" onClick={onCancel}>
            Cancel
          </button>
          <button type="button" className="primary" data-testid="timeline-timed-prompt-ok" onClick={commit}>
            OK
          </button>
        </div>
      </div>
    </div>
  );
}
