import { useRef, type ChangeEvent } from "react";
import { TIMELINE_AUDIO_FILE_ACCEPT, type AudioClipDraft } from "../../timelineMaster/audioClipModal";
import { useTimelineEditorModal } from "./useTimelineEditorModal";

export function AudioSfxClipModal({
  draft,
  busy,
  error,
  onChange,
  onFile,
  onCancel,
  onOk,
}: {
  draft: AudioClipDraft;
  busy: boolean;
  error: string | null;
  onChange: (next: AudioClipDraft) => void;
  onFile: (file: File) => void;
  onCancel: () => void;
  onOk: () => void;
}) {
  const { dialogRef, stopHotkeys } = useTimelineEditorModal(true, onCancel, "button.primary, input");
  const fileRef = useRef<HTMLInputElement>(null);
  const sound = draft.kind === "sfx";
  const titleId = sound ? "sfx-clip-modal-title" : "audio-clip-modal-title";

  const onPick = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (file) onFile(file);
  };

  return (
    <div className="codirector-modal-backdrop" role="presentation" onClick={onCancel} onKeyDown={stopHotkeys}>
      <div
        ref={dialogRef}
        className="codirector-modal card audio-sfx-clip-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        data-testid={sound ? "timeline-sfx-clip-modal" : "timeline-audio-clip-modal"}
        data-kind={draft.kind}
        onClick={(event) => event.stopPropagation()}
        onKeyDown={stopHotkeys}
      >
        <div className="codirector-modal-head">
          <h2 id={titleId}>{sound ? "Sound Effect" : "Audio"}</h2>
        </div>
        <div className="audio-sfx-clip-modal__body">
          <button
            type="button"
            className="primary"
            data-testid="timeline-audio-sfx-upload"
            disabled={busy}
            onClick={() => fileRef.current?.click()}
          >
            {sound ? "Upload SFX" : "Upload Audio"}
          </button>
          <input
            ref={fileRef}
            type="file"
            className="audio-sfx-clip-modal__file"
            accept={TIMELINE_AUDIO_FILE_ACCEPT}
            data-testid="timeline-audio-sfx-file"
            tabIndex={-1}
            onChange={onPick}
            disabled={busy}
          />
          {draft.pendingFileName ? (
            <p className="scene-meta" data-testid="timeline-audio-sfx-filename">
              {draft.pendingFileName}
            </p>
          ) : null}
          <label className="field">
            <span>Title</span>
            <input
              data-testid="timeline-audio-sfx-title"
              value={draft.title}
              onChange={(event) => onChange({ ...draft, title: event.target.value })}
            />
          </label>
          <label className="field">
            <span>Description</span>
            <input
              data-testid="timeline-audio-sfx-description"
              value={draft.description}
              onChange={(event) => onChange({ ...draft, description: event.target.value })}
            />
          </label>
          <label className="field">
            <span>Label</span>
            <input
              data-testid="timeline-audio-sfx-label"
              value={draft.label}
              onChange={(event) => onChange({ ...draft, label: event.target.value })}
            />
          </label>
          <label className="field">
            <span>Start</span>
            <input
              type="number"
              step={0.01}
              min={0}
              data-testid="timeline-audio-sfx-start"
              value={draft.start}
              onChange={(event) => onChange({ ...draft, start: Number(event.target.value) || 0 })}
            />
          </label>
          <label className="field">
            <span>Length</span>
            <input
              type="number"
              step={0.01}
              min={0}
              data-testid="timeline-audio-sfx-length"
              value={draft.length || ""}
              placeholder="From the sound file"
              onChange={(event) => onChange({ ...draft, length: Number(event.target.value) || 0 })}
            />
          </label>
          <label className="field">
            <span>Volume</span>
            <input
              type="number"
              step={0.01}
              min={0}
              max={2}
              data-testid="timeline-audio-sfx-volume"
              value={draft.volume}
              onChange={(event) => {
                const next = Number(event.target.value);
                onChange({ ...draft, volume: Number.isFinite(next) ? next : 1 });
              }}
            />
          </label>
          {error ? (
            <p className="scene-meta" role="alert" data-testid="timeline-audio-sfx-error">
              {error}
            </p>
          ) : null}
        </div>
        <div className="codirector-modal-actions">
          <button type="button" data-testid="timeline-audio-sfx-cancel" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
          <button type="button" className="primary" data-testid="timeline-audio-sfx-ok" onClick={onOk} disabled={busy}>
            OK
          </button>
        </div>
      </div>
    </div>
  );
}
