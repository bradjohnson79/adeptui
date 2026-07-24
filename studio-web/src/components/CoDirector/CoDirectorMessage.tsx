import type { CoDirectorMessage as Msg } from "./types";

export function CoDirectorMessage({
  message,
  onRetry,
}: {
  message: Msg;
  onRetry?: () => void;
}) {
  return (
    <article className={`codirector-msg ${message.role}`}>
      <div className="codirector-msg-bubble">
        {message.content}
        {message.status === "streaming" && !message.content ? "…" : null}
      </div>
      {message.status === "cancelled" && (
        <span className="codirector-msg-status">Stopped</span>
      )}
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
