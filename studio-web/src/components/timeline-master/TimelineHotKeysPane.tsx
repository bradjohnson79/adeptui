import { useMemo, useRef, useState } from "react";
import {
  applyUserShortcut,
  effectiveChord,
  formatChord,
  loadHotkeys,
  resetHotkeys,
  saveHotkeys,
  type HotkeyCategory,
  type ShortcutChord,
  type TimelineHotkeyBinding,
  chordFromEvent,
} from "../../timelineMaster/timelineHotkeys";

const CATEGORIES: HotkeyCategory[] = ["Playback", "Editing", "Generation", "Clips & Tracks", "Reference Authoring"];

export function TimelineHotKeysPane({
  onCloseOverlay,
}: {
  onCloseOverlay?: () => void;
}) {
  const [bindings, setBindings] = useState(() => loadHotkeys());
  const [capturingId, setCapturingId] = useState<string | null>(null);
  const capturingIdRef = useRef<string | null>(null);
  const [conflict, setConflict] = useState<{ actionId: string; chord: ShortcutChord; other: TimelineHotkeyBinding } | null>(null);
  const [status, setStatus] = useState("");

  const grouped = useMemo(() => {
    return CATEGORIES.map((category) => ({
      category,
      rows: bindings.filter((item) => item.category === category),
    })).filter((group) => group.rows.length);
  }, [bindings]);

  const assign = (actionId: string, chord: ShortcutChord, replace: boolean) => {
    const result = applyUserShortcut(bindings, actionId, chord, replace);
    if (result.conflict) {
      setConflict({ actionId, chord, other: result.conflict });
      return;
    }
    setBindings(result.bindings);
    setConflict(null);
    setCapturingId(null);
    capturingIdRef.current = null;
  };

  return (
    <section className="panel timeline-hotkeys-pane" data-testid="timeline-hotkeys-pane">
      <div className="timeline-inspector__eyebrow">Hot Keys</div>
      <p className="scene-meta">Shortcuts run the same Timeline buttons. They stay off while you type.</p>
      <p className="scene-meta">@ # * stay inside Prompt and Lip Sync fields. They are not global shortcuts.</p>
      {grouped.map((group) => (
        <details key={group.category} className="timeline-inspector__accordion" open={group.category === "Generation" || group.category === "Playback"}>
          <summary>{group.category}</summary>
          <div className="timeline-hotkeys-pane__rows">
            {group.rows.map((row) => (
              <div key={row.actionId} className="timeline-hotkeys-pane__row" data-testid={`hotkey-row-${row.actionId}`}>
                <span>{row.label}</span>
                <button
                  type="button"
                  className={capturingId === row.actionId ? "primary" : "ghost"}
                  data-testid={`hotkey-capture-${row.actionId}`}
                  data-hotkey-capture="true"
                  onClick={() => {
                    capturingIdRef.current = row.actionId;
                    setCapturingId(row.actionId);
                  }}
                  onKeyDown={(event) => {
                    if (capturingIdRef.current !== row.actionId) return;
                    event.preventDefault();
                    event.stopPropagation();
                    if (event.key === "Escape") {
                      capturingIdRef.current = null;
                      setCapturingId(null);
                      return;
                    }
                    assign(row.actionId, chordFromEvent(event.nativeEvent), false);
                  }}
                >
                  {capturingId === row.actionId ? "Press a key" : formatChord(effectiveChord(row))}
                </button>
              </div>
            ))}
          </div>
        </details>
      ))}
      {conflict ? (
        <div className="timeline-hotkeys-pane__conflict" data-testid="hotkey-conflict">
          <p>
            {formatChord(conflict.chord)} is currently assigned to {conflict.other.label}.
          </p>
          <p>Replace existing shortcut?</p>
          <div className="row-actions">
            <button type="button" className="ghost" data-testid="hotkey-conflict-cancel" onClick={() => { setConflict(null); capturingIdRef.current = null; setCapturingId(null); }}>
              Cancel
            </button>
            <button
              type="button"
              className="primary"
              data-testid="hotkey-conflict-replace"
              onClick={() => assign(conflict.actionId, conflict.chord, true)}
            >
              Replace
            </button>
          </div>
        </div>
      ) : null}
      <div className="row-actions">
        <button
          type="button"
          className="primary"
          data-testid="hotkey-save"
          onClick={() => {
            saveHotkeys(bindings);
            setStatus("Saved");
            onCloseOverlay?.();
          }}
        >
          Save
        </button>
        <button
          type="button"
          className="ghost"
          data-testid="hotkey-reset"
          onClick={() => {
            const next = resetHotkeys();
            setBindings(next);
            saveHotkeys(next);
            setStatus("Defaults restored");
          }}
        >
          Reset to Defaults
        </button>
      </div>
      {status ? <p className="scene-meta">{status}</p> : null}
    </section>
  );
}
