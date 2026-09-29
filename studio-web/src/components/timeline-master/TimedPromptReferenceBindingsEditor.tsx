import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import {
  applyTimedPromptNameBindingPatch,
  emptyTimedPromptNameBinding,
  sceneSheetBindings,
  TIMED_PROMPT_BINDING_TYPES,
  timedPromptBindingLabel,
  timedPromptBindingMissing,
  type TimedPromptBindingType,
  type TimedPromptNameBinding,
} from "../../timelineMaster/timedPromptNameBindings";
import type { ReferenceBindingView } from "../../sceneReferences/referenceTokens";
import { CharacterVoiceGapNotice } from "./CharacterVoiceGapNotice";

const PROMPT_NAME_IDLE_MS = 400;

export type TimedPromptReferenceBindingsEditorHandle = {
  /** Commit all pending Prompt Name drafts (blur/OK/Close). */
  flush: () => { rows: TimedPromptNameBinding[]; error: string | null };
};

export const TimedPromptReferenceBindingsEditor = forwardRef<
  TimedPromptReferenceBindingsEditorHandle,
  {
    value: TimedPromptNameBinding[];
    bindings: ReferenceBindingView[];
    compact?: boolean;
    projectId?: string;
    /** Fired when committed rows change (blur / idle / OK / type / reference / add / remove). */
    onChange: (next: TimedPromptNameBinding[], error: string | null) => void;
    /** Prompt Name validation messages; cleared while typing. Does not imply a row commit. */
    onValidationError?: (error: string | null) => void;
  }
>(function TimedPromptReferenceBindingsEditor(
  { value, bindings, compact = false, projectId, onChange, onValidationError },
  ref,
) {
  // Local Prompt Name drafts — typing does not patch Timeline until commit.
  const [draftNames, setDraftNames] = useState<Record<number, string>>({});
  const draftNamesRef = useRef(draftNames);
  draftNamesRef.current = draftNames;
  const valueRef = useRef(value);
  valueRef.current = value;
  const bindingsRef = useRef(bindings);
  bindingsRef.current = bindings;
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  const onValidationErrorRef = useRef(onValidationError);
  onValidationErrorRef.current = onValidationError;
  const idleTimerRef = useRef<number | null>(null);
  const pendingIndexRef = useRef<number | null>(null);

  const clearIdleTimer = useCallback(() => {
    if (idleTimerRef.current != null) {
      window.clearTimeout(idleTimerRef.current);
      idleTimerRef.current = null;
    }
    pendingIndexRef.current = null;
  }, []);

  const setValidationError = useCallback((error: string | null) => {
    onValidationErrorRef.current?.(error);
  }, []);

  // Drop drafts that match committed props (or vanished rows).
  useEffect(() => {
    setDraftNames((current) => {
      let changed = false;
      const next: Record<number, string> = {};
      for (const [key, draft] of Object.entries(current)) {
        const index = Number(key);
        const row = value[index];
        if (!row) {
          changed = true;
          continue;
        }
        if (draft === row.prompt_name) {
          changed = true;
          continue;
        }
        next[index] = draft;
      }
      return changed ? next : current;
    });
  }, [value]);

  useEffect(() => () => clearIdleTimer(), [clearIdleTimer]);

  const emit = useCallback((next: TimedPromptNameBinding[], error: string | null) => {
    onChangeRef.current(next, error);
  }, []);

  const commitPromptName = useCallback(
    (index: number, rawName?: string): { rows: TimedPromptNameBinding[]; error: string | null } => {
      const rows = valueRef.current;
      if (index < 0 || index >= rows.length) {
        return { rows, error: "Missing reference row." };
      }
      const name =
        rawName !== undefined
          ? rawName
          : draftNamesRef.current[index] !== undefined
            ? draftNamesRef.current[index]
            : rows[index].prompt_name;
      if (draftNamesRef.current[index] === undefined && name === rows[index].prompt_name) {
        return { rows, error: null };
      }
      const result = applyTimedPromptNameBindingPatch(
        rows,
        index,
        { prompt_name: name },
        bindingsRef.current,
      );
      if (result.error) {
        // Keep local draft so the controlled input does not snap back / fight typing.
        setValidationError(result.error);
        return result;
      }
      setDraftNames((current) => {
        if (current[index] === undefined) return current;
        const next = { ...current };
        delete next[index];
        return next;
      });
      setValidationError(null);
      emit(result.rows, null);
      return result;
    },
    [emit, setValidationError],
  );

  const scheduleCommit = useCallback(
    (index: number) => {
      clearIdleTimer();
      pendingIndexRef.current = index;
      idleTimerRef.current = window.setTimeout(() => {
        idleTimerRef.current = null;
        const target = pendingIndexRef.current;
        pendingIndexRef.current = null;
        if (target != null) commitPromptName(target);
      }, PROMPT_NAME_IDLE_MS);
    },
    [clearIdleTimer, commitPromptName],
  );

  const flush = useCallback((): { rows: TimedPromptNameBinding[]; error: string | null } => {
    clearIdleTimer();
    const pending = { ...draftNamesRef.current };
    let rows = valueRef.current;
    let error: string | null = null;
    let rowsChanged = false;
    const indices = Object.keys(pending)
      .map(Number)
      .sort((a, b) => a - b);
    for (const index of indices) {
      const result = applyTimedPromptNameBindingPatch(
        rows,
        index,
        { prompt_name: pending[index] },
        bindingsRef.current,
      );
      if (result.error) {
        error = result.error;
        continue;
      }
      rows = result.rows;
      rowsChanged = true;
      setDraftNames((current) => {
        if (current[index] === undefined) return current;
        const next = { ...current };
        delete next[index];
        return next;
      });
      delete pending[index];
    }
    draftNamesRef.current = pending;
    setValidationError(error);
    if (rowsChanged) emit(rows, error);
    else if (error) setValidationError(error);
    return { rows, error };
  }, [clearIdleTimer, emit, setValidationError]);

  useImperativeHandle(ref, () => ({ flush }), [flush]);

  const addRow = () => {
    clearIdleTimer();
    setDraftNames({});
    setValidationError(null);
    emit([...value, emptyTimedPromptNameBinding()], null);
  };

  const removeRow = (index: number) => {
    clearIdleTimer();
    setDraftNames({});
    setValidationError(null);
    emit(
      value.filter((_, itemIndex) => itemIndex !== index),
      null,
    );
  };

  const patchRow = (index: number, patch: Partial<TimedPromptNameBinding>) => {
    // Type / Reference changes commit immediately (not the Prompt Name hot path).
    const result = applyTimedPromptNameBindingPatch(value, index, patch, bindings);
    if (result.error) setValidationError(result.error);
    else setValidationError(null);
    emit(result.rows, result.error);
  };

  const onPromptNameChange = (index: number, nextName: string) => {
    setDraftNames((current) => ({ ...current, [index]: nextName }));
    // Clear stale duplicate error while typing; do not validate or emit row commits.
    setValidationError(null);
    scheduleCommit(index);
  };

  const onPromptNameBlur = (index: number) => {
    clearIdleTimer();
    commitPromptName(index);
  };

  const onPromptNameKeyDown = (index: number, event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    clearIdleTimer();
    commitPromptName(index);
    (event.target as HTMLInputElement).blur();
  };

  return (
    <div
      className={`timed-prompt-ref-editor${compact ? " timed-prompt-ref-editor--compact" : ""}`}
      data-testid="timed-prompt-references"
    >
      <div className="timed-prompt-ref-editor__head">
        <span>References</span>
        <button type="button" className="ghost" data-testid="timed-prompt-add-reference" onClick={addRow}>
          Add Reference
        </button>
      </div>
      {value.length ? (
        <div className="timed-prompt-ref-editor__rows">
          {value.map((row, index) => {
            const options = sceneSheetBindings(bindings, row.type);
            const missing = timedPromptBindingMissing(row, bindings);
            const selectedMissing = Boolean(row.binding_id && !options.some((item) => item.id === row.binding_id));
            const promptNameValue =
              draftNames[index] !== undefined ? draftNames[index] : row.prompt_name;
            return (
              <div
                key={`${row.binding_id || "new"}-${index}`}
                className={`timed-prompt-ref-editor__row${missing ? " timed-prompt-ref-editor__row--missing" : ""}`}
                data-testid={`timed-prompt-ref-row-${index}`}
              >
                <label className="timed-prompt-ref-editor__field">
                  <span className="sr-only">Type</span>
                  <select
                    data-testid="timed-prompt-ref-type"
                    value={row.type}
                    onChange={(event) =>
                      patchRow(index, { type: event.target.value as TimedPromptBindingType })
                    }
                  >
                    {TIMED_PROMPT_BINDING_TYPES.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="timed-prompt-ref-editor__field">
                  <span className="sr-only">Reference</span>
                  <select
                    data-testid="timed-prompt-ref-binding"
                    value={row.binding_id}
                    onChange={(event) => patchRow(index, { binding_id: event.target.value })}
                  >
                    <option value="">{missing || selectedMissing ? "Unavailable" : "Select reference"}</option>
                    {selectedMissing ? (
                      <option value={row.binding_id}>
                        {row.tag || "Missing from References"}
                      </option>
                    ) : null}
                    {options.map((item) => (
                      <option key={item.id} value={item.id}>
                        {timedPromptBindingLabel(item)}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="timed-prompt-ref-editor__field">
                  <span className="sr-only">Prompt Name</span>
                  <input
                    data-testid="timed-prompt-ref-name"
                    type="text"
                    value={promptNameValue}
                    placeholder="Prompt Name"
                    onChange={(event) => onPromptNameChange(index, event.target.value)}
                    onBlur={() => onPromptNameBlur(index)}
                    onKeyDown={(event) => onPromptNameKeyDown(index, event)}
                  />
                </label>
                <button
                  type="button"
                  className="ghost"
                  data-testid="timed-prompt-ref-remove"
                  aria-label="Remove reference"
                  onClick={() => removeRow(index)}
                >
                  remove
                </button>
                {missing ? (
                  <p className="timed-prompt-ref-editor__missing" data-testid="timed-prompt-ref-missing">
                    This name is no longer in References. It was not redirected.
                  </p>
                ) : null}
              </div>
            );
          })}
        </div>
      ) : (
        <p className="scene-meta">Add a Character, Prop, Environment, Video, or Audio already named in References.</p>
      )}
      {projectId ? <CharacterVoiceGapNotice projectId={projectId} rows={value} bindings={bindings} /> : null}
    </div>
  );
});
