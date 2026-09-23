import { useRef, useState } from "react";
import { Button, IconButton } from "../ui";
import { IconGallery, IconMic, IconPaperclip, IconSend, IconStop } from "./icons";
import { useCoDirectorSession } from "./CoDirectorSession";
import { CoDirectorAttachmentTray } from "./CoDirectorAttachmentTray";
import { useSpeechToText } from "./useSpeechToText";

const COMPOSER_IMAGE_MIME = /^(image\/png|image\/jpeg|image\/jpg|image\/webp)$/i;
const COMPOSER_IMAGE_EXT = /\.(png|jpe?g|webp)$/i;

export function isComposerImageFile(file: File): boolean {
  if (COMPOSER_IMAGE_MIME.test(file.type || "")) return true;
  return COMPOSER_IMAGE_EXT.test(file.name || "");
}

export function filesFromClipboardItems(items: DataTransferItemList | undefined | null): File[] {
  if (!items) return [];
  const out: File[] = [];
  for (const item of Array.from(items)) {
    if (item.kind !== "file") continue;
    const file = item.getAsFile();
    if (file && isComposerImageFile(file)) out.push(file);
  }
  return out;
}

export function filesFromDataTransfer(data: DataTransfer | null | undefined): File[] {
  if (!data) return [];
  return Array.from(data.files || []).filter(isComposerImageFile);
}

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
    overflowPanel,
    setOverflowPanel,
    appendTranscript,
    uiContext,
  } = useCoDirectorSession();
  const fileRef = useRef<HTMLInputElement>(null);
  const [dropActive, setDropActive] = useState(false);
  const speech = useSpeechToText(appendTranscript);

  const canSend = Boolean(draft.trim() || attachments.length) && !busy;
  const listening = speech.state === "listening" || speech.state === "permission";
  const processing = speech.state === "processing";
  const elapsedSec = Math.max(0, Math.floor((speech.elapsedMs || 0) / 1000));
  const micLabel =
    listening
      ? "Stop listening"
      : speech.state === "denied"
        ? "Microphone permission denied"
        : speech.state === "unavailable"
          ? "No microphone detected"
          : speech.state === "unsupported"
            ? "Speech recognition unsupported"
            : processing
              ? "Processing speech"
              : "Start voice input";

  const chips = [
    uiContext.sceneName ? { id: "scene", label: uiContext.sceneName } : null,
    uiContext.workspaceId ? { id: "workspace", label: uiContext.workspaceId } : null,
  ].filter(Boolean) as Array<{ id: string; label: string }>;

  return (
    <div className="codirector-composer" data-testid="codirector-composer">
      {busy ? (
        <div
          className="codirector-composer-processing"
          data-testid="codirector-composer-processing"
          aria-live="polite"
          aria-busy="true"
        >
          <span className="codirector-spinner codirector-spinner--lg" aria-hidden />
          <span>Processing… Co-Director is thinking</span>
        </div>
      ) : null}
      <CoDirectorAttachmentTray />
      {chips.length > 0 && (
        <div className="codirector-context-chips" data-testid="codirector-context-chips">
          {chips.slice(0, 4).map((chip) => (
            <span
              key={chip.id}
              className="codirector-context-chip"
              data-testid={chip.id === "scene" ? "codirector-context-chip-scene" : `codirector-context-chip-${chip.id}`}
            >
              {chip.label}
            </span>
          ))}
        </div>
      )}
      {speech.error && (
        <p className="codirector-composer-error" role="alert" data-testid="codirector-stt-error">
          {speech.error}
        </p>
      )}
      {(listening || processing) && (
        <div className="codirector-stt-status" data-testid="codirector-stt-status" aria-live="polite">
          <span>{listening ? `Listening… ${elapsedSec}s` : "Processing speech…"}</span>
          <Button
            variant="ghost"
            compact
            data-testid="codirector-stt-cancel"
            onClick={() => speech.cancel()}
          >
            Cancel
          </Button>
        </div>
      )}
      <div
        className={`codirector-composer-box ${listening ? "listening" : ""} ${dropActive ? "drop-active" : ""}`}
        data-testid="codirector-composer-drop-target"
        onDragEnter={(e) => {
          if (!filesFromDataTransfer(e.dataTransfer).length && !Array.from(e.dataTransfer?.types || []).includes("Files")) {
            return;
          }
          e.preventDefault();
          setDropActive(true);
        }}
        onDragOver={(e) => {
          e.preventDefault();
          e.dataTransfer.dropEffect = "copy";
          setDropActive(true);
        }}
        onDragLeave={(e) => {
          if (e.currentTarget.contains(e.relatedTarget as Node)) return;
          setDropActive(false);
        }}
        onDrop={(e) => {
          e.preventDefault();
          setDropActive(false);
          const images = filesFromDataTransfer(e.dataTransfer);
          if (images.length) addFiles(images);
        }}
      >
        {dropActive ? (
          <div className="codirector-composer-drop-hint" data-testid="codirector-composer-drop-hint">
            Drop image for Co-Director
          </div>
        ) : null}
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Ask Co-Director..."
          rows={2}
          disabled={busy}
          aria-label="Message Co-Director"
          data-testid="codirector-composer-input"
          onPaste={(e) => {
            const images = filesFromClipboardItems(e.clipboardData?.items);
            if (!images.length) return;
            e.preventDefault();
            addFiles(images);
            const text = e.clipboardData?.getData("text/plain") || "";
            if (text.trim()) {
              setDraft((prev) => (prev ? `${prev}${prev.endsWith("\n") || prev.endsWith(" ") ? "" : " "}${text}` : text));
            }
          }}
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
            <IconButton
              aria-label="Attach files"
              title="Attach files"
              disabled={busy}
              onClick={() => fileRef.current?.click()}
            >
              <IconPaperclip />
            </IconButton>
            <IconButton
              aria-label="Choose from Library"
              title="Library"
              disabled={busy}
              onClick={() => setAssetPickerOpen(true)}
            >
              <IconGallery />
            </IconButton>
            <IconButton
              className={listening ? "is-selected" : ""}
              aria-label={micLabel}
              aria-pressed={listening}
              title={micLabel}
              data-testid="codirector-mic-button"
              disabled={busy || speech.state === "unsupported"}
              onClick={() => speech.toggle()}
            >
              <IconMic />
            </IconButton>
            <Button
              variant="ghost"
              compact
              data-testid="codirector-options-button"
              aria-expanded={overflowPanel !== "none"}
              aria-controls="codirector-overflow-panel"
              disabled={busy}
              onClick={() => {
                const next = overflowPanel === "none" ? "options" : "none";
                setOverflowPanel(next);
                if (next !== "none") {
                  window.requestAnimationFrame(() => {
                    document.getElementById("codirector-overflow-panel")?.scrollIntoView({
                      block: "nearest",
                      behavior: "smooth",
                    });
                  });
                }
              }}
            >
              Options
            </Button>
          </div>
          {busy ? (
            <IconButton
              aria-label="Stop generating"
              title="Stop generating"
              data-testid="codirector-stop-button"
              onClick={() => cancelSend()}
            >
              <IconStop />
            </IconButton>
          ) : (
            <IconButton
              aria-label="Send message"
              title="Send"
              data-testid="codirector-send-button"
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
            </IconButton>
          )}
        </div>
      </div>
      <input
        ref={fileRef}
        type="file"
        multiple
        accept="image/*,video/*,audio/*,.txt,.md,.pdf,.doc,.docx"
        hidden
        data-testid="codirector-file-input"
        onChange={(e) => {
          if (e.target.files?.length) addFiles(e.target.files);
          e.target.value = "";
        }}
      />
    </div>
  );
}
