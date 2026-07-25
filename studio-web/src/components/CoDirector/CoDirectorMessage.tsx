import type { CoDirectorMessage as Msg } from "./types";
import { renderAssistantMarkdown } from "./assistantMarkdown";

const MESSAGE_TYPE_LABELS: Record<string, string> = {
  recommendation: "Recommendation",
  clarification: "Clarification",
  warning: "Warning",
  proposal: "Proposal",
  plan: "Production plan",
  answer: "Answer",
};

export function CoDirectorMessage({
  message,
  onRetry,
}: {
  message: Msg;
  onRetry?: () => void;
}) {
  const typeLabel = message.messageType ? MESSAGE_TYPE_LABELS[message.messageType] : null;
  const isAssistant = message.role === "assistant";
  const html = isAssistant ? renderAssistantMarkdown(message.content) : "";

  return (
    <article
      className={`codirector-msg ${message.role}${message.messageType ? ` type-${message.messageType}` : ""}`}
    >
      {typeLabel && isAssistant ? <span className="codirector-msg-type">{typeLabel}</span> : null}
      {isAssistant ? (
        <div
          className="codirector-msg-bubble codirector-msg-html"
          dangerouslySetInnerHTML={{
            __html:
              html ||
              (message.status === "streaming" && !message.content ? "<p>…</p>" : ""),
          }}
        />
      ) : (
        <div className="codirector-msg-bubble">
          {message.content}
          {message.status === "streaming" && !message.content ? "…" : null}
        </div>
      )}
      {message.status === "cancelled" && <span className="codirector-msg-status">Stopped</span>}
      {message.status === "interrupted" && (
        <span className="codirector-msg-status">Interrupted — you can retry</span>
      )}
      {message.role === "user" && onRetry ? (
        <div className="codirector-msg-actions">
          <button type="button" className="ghost" onClick={onRetry}>
            Retry
          </button>
        </div>
      ) : null}
    </article>
  );
}
