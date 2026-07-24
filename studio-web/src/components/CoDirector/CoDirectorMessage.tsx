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
      <div className="codirector-msg-bubble">{message.content}</div>
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
