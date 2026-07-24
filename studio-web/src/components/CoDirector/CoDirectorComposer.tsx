import { useRef } from "react";
import { IconGallery, IconMic, IconPaperclip, IconSend } from "./icons";
import { useCoDirectorSession } from "./CoDirectorSession";
import { CoDirectorAttachmentTray } from "./CoDirectorAttachmentTray";
import { useSpeechToText } from "./useSpeechToText";

export function CoDirectorComposer() {
  const {
    draft,
    setDraft,
    send,
    busy,
    cancelSend,
    attachments,
    addFiles,
    setAssetPickerOpen,
    setOverflowPanel,
    appendTranscript,
  } = useCoDirectorSession();
  const fileRef = useRef<HTMLInputElement>(null);
  const speech = useSpeechToText(appendTranscript);

  const canSend = Boolean(draft.trim() || attachments.length) && !busy;
  const micLabel =
    speech.state === "listening"
      ? "Stop listening"
      : speech.state === "denied"
        ? "Microphone permission denied"
        : speech.state === "unsupported"
          ? "Speech recognition unsupported"
          : "Start voice input";

  return (
    <div className="codirector-composer">
      <CoDirectorAttachmentTray />
      {speech.error && <p className="codirector-composer-error" role="alert">{speech.error}</p>}
      <div className={`codirector-composer-box ${speech.state === "listening" ? "listening" : ""}`}>
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Ask Co-Director anything…"
          rows={3}
          disabled={busy}
          aria-label="Message Co-Director"
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              if (canSend) {
                const mode = /build|set\s*up|setup|configure|assemble/i.test(draft)
                  ? "setup"
                  : /prompt|rewrite|write/i.test(draft)
                    ? "prompt"
                    : "chat";
                void send(undefined, mode);
              }
            }
          }}
        />
        <div className="codirector-composer-toolbar">
          <div className="codirector-composer-tools">
            <button
              type="button"
              className="codirector-icon-btn"
              aria-label="Attach files"
              title="Attach files"
              disabled={busy}
              onClick={() => fileRef.current?.click()}
            >
              <IconPaperclip />
            </button>
            <button
              type="button"
              className="codirector-icon-btn"
              aria-label="Choose from Library"
              title="Library"
              disabled={busy}
              onClick={() => setAssetPickerOpen(true)}
            >
              <IconGallery />
            </button>
            <button
              type="button"
              className={`codirector-icon-btn ${speech.state === "listening" ? "active" : ""}`}
              aria-label={micLabel}
              aria-pressed={speech.state === "listening"}
              title={micLabel}
              disabled={busy || speech.state === "unsupported"}
              onClick={() => speech.toggle()}
            >
              <IconMic />
            </button>
            <button
              type="button"
              className="ghost"
              onClick={() => setOverflowPanel("options")}
              disabled={busy}
            >
              Options
            </button>
          </div>
          {busy ? (
            <button
              type="button"
              className="codirector-send codirector-stop"
              aria-label="Stop generating"
              title="Stop generating"
              onClick={() => cancelSend()}
            >
              Stop
            </button>
          ) : (
            <button
              type="button"
              className="codirector-send"
              aria-label="Send message"
              title="Send"
              disabled={!canSend}
              onClick={() => {
                const mode = /build|set\s*up|setup|configure|assemble/i.test(draft)
                  ? "setup"
                  : /prompt|rewrite|write/i.test(draft)
                    ? "prompt"
                    : "chat";
                void send(undefined, mode);
              }}
            >
              <IconSend />
            </button>
          )}
        </div>
      </div>
      <input
        ref={fileRef}
        type="file"
        multiple
        accept="image/*,video/*,.txt,.md,.pdf,.doc,.docx"
        hidden
        onChange={(e) => {
          if (e.target.files?.length) addFiles(e.target.files);
          e.target.value = "";
        }}
      />
    </div>
  );
}
