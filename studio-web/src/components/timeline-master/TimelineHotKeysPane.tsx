import { useMemo, useRef, useState } from "react";
import { loadMagiHotkeys, resetMagiHotkeys, saveMagiHotkeys } from "../../magiSequence/magiHotkeys";
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

const TIMELINE_CATEGORIES: HotkeyCategory[] = ["Playback", "Editing", "Generation", "Clips & Tracks", "Reference Authoring"];
const MAGI_CATEGORIES: HotkeyCategory[] = ["Playback", "Editing", "View"];

export function TimelineHotKeysPane({
  onCloseOverlay,
  workspace = "timeline",
}: {
  onCloseOverlay?: () => void;
  workspace?: "timeline" | "magi";
}) {
  const [bindings, setBindings] = useState(() => (workspace === "magi" ? loadMagiHotkeys() : loadHotkeys()));
  const [capturingId, setCapturingId] = useState<string | null>(null);
  const capturingIdRef = useRef<string | null>(null);
  const [conflict, setConflict] = useState<{ actionId: string; chord: ShortcutChord; other: TimelineHotkeyBinding } | null>(null);
  const [status, setStatus] = useState("");

  const categories = workspace === "magi" ? MAGI_CATEGORIES : TIMELINE_CATEGORIES;
  const grouped = useMemo(() => {
    return categories.map((category) => ({
      category,
      rows: bindings.filter((item) => {
        if (item.category !== category) return false;
        if (workspace !== "magi") return true;
        return item.enabled && Boolean(effectiveChord(item).key);
      }),
    })).filter((group) => group.rows.length);
  }, [bindings, categories]);

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
    <section
      className="panel timeline-hotkeys-pane"
      data-testid={workspace === "magi" ? "magi-hotkeys-pane" : "timeline-hotkeys-pane"}
      data-hotkey-workspace={workspace}
    >
      <div className="timeline-inspector__eyebrow">Hot Keys</div>
      <p className="scene-meta">
        {workspace === "magi"
          ? "Shortcuts run MAGI while MAGI is open. They stay off while you type."
          : "Shortcuts run the same Timeline buttons. They stay off while you type."}
      </p>
      {workspace === "timeline" ? <p className="scene-meta">@ # * stay inside Prompt fields. They are not global shortcuts.</p> : null}
      {grouped.map((group) => (
        <details
          key={group.category}
          className="timeline-inspector__accordion"
          open={
            workspace === "magi"
              ? group.category === "Playback" || group.category === "Editing" || group.category === "View"
              : group.category === "Generation" || group.category === "Playback"
          }
        >
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
            if (workspace === "magi") saveMagiHotkeys(bindings);
            else saveHotkeys(bindings);
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
            const next = workspace === "magi" ? resetMagiHotkeys() : resetHotkeys();
            setBindings(next);
            if (workspace === "magi") saveMagiHotkeys(next);
            else saveHotkeys(next);
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
