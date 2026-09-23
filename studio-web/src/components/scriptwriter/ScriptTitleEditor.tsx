import { useEffect, useRef, useState } from "react";
import "./ScriptTitleEditor.css";

type Props = {
  /** Canonical title from the script or story document. */
  title: string;
  /** Persist the new title to the canonical document. Reject to revert. */
  onRename: (next: string) => Promise<void>;
  className?: string;
  testId?: string;
  defaultTitle?: string;
  ariaLabel?: string;
};

const DEFAULT_TITLE = "Untitled Script";

/**
 * Inline-editable script title shared by Script Writer Express and Standard.
 *
 * Click → edit. Enter or blur saves (persists to the canonical script
 * document via onRename). Escape cancels. No local-only title state: the
 * displayed value always comes from the canonical document; edit mode holds
 * only the in-progress draft text.
 */
export function ScriptTitleEditor({ title, onRename, className, testId = "script-title", defaultTitle = DEFAULT_TITLE, ariaLabel }: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const display = title || defaultTitle;

  useEffect(() => {
    if (editing) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [editing]);

  const begin = () => {
    if (saving) return;
    setDraft(display);
    setError(null);
    setEditing(true);
  };

  const cancel = () => {
    setEditing(false);
    setError(null);
  };

  const save = async () => {
    if (saving) return;
    const next = draft.trim() || defaultTitle;
    setEditing(false);
    if (next === display) return;
    setSaving(true);
    setError(null);
    try {
      await onRename(next);
    } catch {
      setError("Couldn't save the title. Try again.");
    } finally {
      setSaving(false);
    }
  };

  if (editing) {
    return (
      <input
        ref={inputRef}
        className={`script-title-editor__input ${className ?? ""}`.trim()}
        data-testid={testId}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => void save()}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            void save();
          } else if (e.key === "Escape") {
            e.preventDefault();
            cancel();
          }
        }}
        maxLength={200}
        aria-label={ariaLabel || "Script title"}
      />
    );
  }

  return (
    <span className={`script-title-editor ${className ?? ""}`.trim()}>
      <button
        type="button"
        className="script-title-editor__display"
        data-testid={`${testId}-display`}
        onClick={begin}
        title="Click to rename"
        disabled={saving}
      >
        {display}
        <span className="script-title-editor__pencil" aria-hidden="true"> ✎</span>
      </button>
      {error ? (
        <span className="script-title-editor__error" data-testid={`${testId}-error`} role="alert">
          {error}
        </span>
      ) : null}
    </span>
  );
}
