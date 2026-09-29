import { useEffect, useRef, useState } from "react";
import { api } from "../../api";
import type { PromptSegment } from "../DirectorTracks";
import type { ReferenceBindingView } from "../../sceneReferences/referenceTokens";
import { canonicalGeneratorId } from "../../timelineMaster/draftCapabilities";
import {
  bindingIdsFromNameBindings,
  hydrateTimedPromptNameBindings,
  validateTimedPromptNameBindings,
  type TimedPromptNameBinding,
} from "../../timelineMaster/timedPromptNameBindings";
import {
  TimedPromptReferenceBindingsEditor,
  type TimedPromptReferenceBindingsEditorHandle,
} from "./TimedPromptReferenceBindingsEditor";
import { TimeStepperField } from "./TimeStepperField";
import { useDraftField } from "./useDraftField";
import { ScenePromptTemplateBar } from "./ScenePromptTemplateBar";
import { useTimelineEditorModal } from "./useTimelineEditorModal";
import {
  decideTimedPromptRange,
  formatSceneClockSec,
  type TimedPromptRangeDecision,
} from "../../timelineMaster/sceneDurationAuthority";

type MovementChoice = { id: string; label: string; segmentNumber: number };

type Draft = {
  start: number;
  length: number;
  movementId: string;
  nameBindings: TimedPromptNameBinding[];
};

function buildPromptPatch(
  draft: Draft,
  text: string,
  movementChoices: MovementChoice[],
): Partial<PromptSegment> {
  const chosen = movementChoices.find((row) => row.id === draft.movementId);
  const nameBindings = draft.nameBindings.filter((row) => row.binding_id);
  return {
    text,
    start: Math.max(0, draft.start),
    length: Math.max(0.15, draft.length),
    movement_segment_ref: chosen
      ? { id: chosen.id, segmentNumber: chosen.segmentNumber, alias: `M${chosen.segmentNumber}` }
      : null,
    movement_segment_revision: chosen ? 1 : null,
    reference_name_bindings: nameBindings,
    reference_binding_ids: bindingIdsFromNameBindings(nameBindings),
    production_prompt: null,
  };
}

export function TimedPromptEditorModal({
  segment,
  bindings,
  projectId,
  generatorId,
  sourceSceneId,
  suggestedName,
  generatorFamily,
  onCancel,
  onPersist,
  onCommit,
  sceneDurationSec,
  sceneLabel = "Scene 1",
  onExtendScene,
}: {
  segment: PromptSegment;
  bindings: ReferenceBindingView[];
  projectId: string;
  generatorId?: string | null;
  sourceSceneId?: string | null;
  suggestedName?: string | null;
  generatorFamily?: string | null;
  sceneDurationSec: number;
  sceneLabel?: string;
  onExtendScene?: (neededSceneSec: number) => void | Promise<void>;
  onCancel: () => void;
  /** Debounced / blur persist without closing the modal (shared timeline store). */
  onPersist?: (patch: Partial<PromptSegment>) => void | Promise<void>;
  onCommit: (patch: Partial<PromptSegment>) => void | Promise<void>;
}) {
  const draftFromSegment = (row: PromptSegment): Draft => ({
    start: row.start,
    length: row.length,
    movementId: row.movement_segment_ref?.id || "",
    nameBindings: hydrateTimedPromptNameBindings({
      nameBindings: row.reference_name_bindings,
      bindingIds: row.reference_binding_ids,
      bindings,
    }),
  });
  const latestSegment = (): PromptSegment => {
    return segment;
  };
  const [draft, setDraft] = useState<Draft>(() => draftFromSegment(latestSegment()));
  const [bindingError, setBindingError] = useState<string | null>(null);
  const [rangeOffer, setRangeOffer] = useState<Extract<TimedPromptRangeDecision, { ok: false }> | null>(null);
  const [movementChoices, setMovementChoices] = useState<MovementChoice[]>([]);
  const liveText = latestSegment().text || "";
  const draftMetaReady = useRef(false);
  const bindingsEditorRef = useRef<TimedPromptReferenceBindingsEditorHandle | null>(null);

  const persistText = (text: string) => {
    if (!onPersist) return;
    void onPersist({ text, production_prompt: null });
  };

  const textField = useDraftField(liveText, persistText, {
    identity: `timed-prompt-modal-${segment.id}`,
    idleMs: 400,
  });

  const { dialogRef, stopHotkeys } = useTimelineEditorModal(true, onCancel, "textarea");

  useEffect(() => {
    setDraft(draftFromSegment(latestSegment()));
    setBindingError(null);
    draftMetaReady.current = false;
    const warm = window.setTimeout(() => {
      draftMetaReady.current = true;
    }, 0);
    return () => window.clearTimeout(warm);
    // Hydrate once per clip open from the shared shell snapshot.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [segment.id]);

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
              label: row.beatName ? `M${row.segmentNumber} - ${row.beatName}` : `Movement ${row.segmentNumber}`,
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

  const timingDecision = (start: number, length: number) =>
    decideTimedPromptRange(start, length, sceneDurationSec, sceneLabel);

  // Debounced autosave for non-text fields so OK is not required.
  // Text is owned by useDraftField; this path never writes text (avoids races).
  useEffect(() => {
    if (!onPersist || !draftMetaReady.current) return;
    const handle = window.setTimeout(() => {
      const decision = timingDecision(draft.start, draft.length);
      setRangeOffer(!decision.ok && decision.reason === "overflow" ? decision : null);
      const patch = buildPromptPatch(draft, textField.value, movementChoices);
      const meta: Partial<PromptSegment> = { ...patch };
      delete meta.text;
      delete meta.production_prompt;
      if (!decision.ok) {
        delete meta.start;
        delete meta.length;
      }
      void onPersist(meta);
    }, 400);
    return () => window.clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft, movementChoices, sceneDurationSec, sceneLabel]);

  const commit = () => {
    textField.flush();
    const text = textField.value;
    const flushed = bindingsEditorRef.current?.flush() ?? {
      rows: draft.nameBindings,
      error: bindingError,
    };
    setDraft((current) => ({ ...current, nameBindings: flushed.rows }));
    const authError = flushed.error || validateTimedPromptNameBindings(flushed.rows);
    if (authError) {
      setBindingError(authError);
      if (onPersist) void onPersist({ text, production_prompt: null });
      return;
    }
    setBindingError(null);
    const decision = timingDecision(draft.start, draft.length);
    if (!decision.ok) {
      setRangeOffer(decision.reason === "overflow" ? decision : null);
      if (onPersist) void onPersist({ text, production_prompt: null });
      return;
    }
    setRangeOffer(null);
    const patch = buildPromptPatch(
      { ...draft, nameBindings: flushed.rows },
      text,
      movementChoices,
    );
    void onCommit(patch);
  };

  const close = () => {
    textField.flush();
    const flushed = bindingsEditorRef.current?.flush() ?? {
      rows: draft.nameBindings,
      error: null,
    };
    // Preserve autosave for committed name drafts before unmount (meta debounce may not fire).
    if (onPersist && !flushed.error) {
      const patch = buildPromptPatch(
        { ...draft, nameBindings: flushed.rows },
        textField.value,
        movementChoices,
      );
      const meta: Partial<PromptSegment> = { ...patch };
      delete meta.text;
      delete meta.production_prompt;
      void onPersist(meta);
    } else if (flushed.error) {
      setBindingError(flushed.error);
    }
    onCancel();
  };

  return (
    <div className="codirector-modal-backdrop" role="presentation" onClick={close} onKeyDown={stopHotkeys}>
      <div
        ref={dialogRef}
        className="codirector-modal card timed-prompt-editor-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="timed-prompt-editor-title"
        data-testid="timeline-timed-prompt-modal"
        onClick={(event) => event.stopPropagation()}
        onKeyDown={stopHotkeys}
      >
        <div className="codirector-modal-head">
          <h2 id="timed-prompt-editor-title">Timed Prompt</h2>
          <p className="scene-meta" data-testid="timed-prompt-autosave-hint">
            Autosaves to the timeline (same store as Scene Inspector Prompt).
          </p>
        </div>
        <div className="timed-prompt-editor-modal__body">
          <TimedPromptReferenceBindingsEditor
            ref={bindingsEditorRef}
            projectId={projectId}
            value={draft.nameBindings}
            bindings={bindings}
            onValidationError={setBindingError}
            onChange={(nameBindings, error) => {
              // Always accept committed nameBindings into draft (show error; never freeze input).
              setBindingError(error);
              setDraft((current) =>
                current.nameBindings === nameBindings ? current : { ...current, nameBindings },
              );
            }}
          />
          {bindingError ? (
            <p className="scene-meta" data-testid="timed-prompt-ref-error">
              {bindingError}
            </p>
          ) : null}
          <label className="field">
            <span>Prompt</span>
            <textarea
              data-testid="timeline-timed-prompt-text"
              rows={8}
              value={textField.value}
              onChange={(event) => textField.onChange(event.target.value)}
              onFocus={textField.onFocus}
              onBlur={textField.onBlur}
            />
          </label>
          <ScenePromptTemplateBar
            projectId={projectId}
            workingText={textField.value}
            isDirty={textField.isDirty}
            sourceSceneId={sourceSceneId}
            suggestedName={suggestedName}
            generatorFamily={
              generatorFamily ||
              (generatorId ? canonicalGeneratorId(generatorId) : "") ||
              ""
            }
            generatorId={generatorId}
            onLoadText={async (text) => {
              textField.onChange(text);
              textField.flush();
              if (onPersist) {
                await onPersist({ text, production_prompt: null });
              }
            }}
            testIdPrefix="timed-prompt-template"
          />
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
          {rangeOffer ? (
            <div data-testid="timeline-timed-prompt-overflow">
              <p className="scene-meta" role="status">
                {rangeOffer.message}
              </p>
              {onExtendScene ? (
                <button
                  type="button"
                  data-testid="timeline-timed-prompt-extend-scene"
                  onClick={() => {
                    void Promise.resolve(onExtendScene(rangeOffer.neededSceneSec)).then(() => {
                      setRangeOffer(null);
                      if (!onPersist) return;
                      const patch = buildPromptPatch(draft, textField.value, movementChoices);
                      const meta: Partial<PromptSegment> = { ...patch };
                      delete meta.text;
                      delete meta.production_prompt;
                      void onPersist(meta);
                    });
                  }}
                >
                  Extend scene to {formatSceneClockSec(rangeOffer.neededSceneSec)}s
                </button>
              ) : null}
            </div>
          ) : null}
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
        </div>
        <div className="codirector-modal-actions">
          <button type="button" data-testid="timeline-timed-prompt-cancel" onClick={close}>
            Close
          </button>
          <button type="button" className="primary" data-testid="timeline-timed-prompt-ok" onClick={commit}>
            OK
          </button>
        </div>
      </div>
    </div>
  );
}