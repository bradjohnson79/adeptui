import { useEffect, useRef } from "react";
import { useCoDirectorSession } from "./CoDirectorSession";
import { CoDirectorMessage } from "./CoDirectorMessage";
import { CoDirectorWelcome } from "./CoDirectorWelcome";
import { CoDirectorTaskStatus } from "./CoDirectorTaskStatus";
import { summarizeSetup } from "./types";

export function CoDirectorConversation({ compactWelcome = false }: { compactWelcome?: boolean }) {
  const {
    messages,
    conversationStarted,
    plan,
    setup,
    suggestedPrompt,
    applyNote,
    applying,
    applySetup,
    dismissSetup,
    applySuggestedPrompt,
    dismissSuggestedPrompt,
    uiContext,
    send,
    busy,
    sendError,
    dismissSendError,
    retryLastSend,
    openSettings,
  } = useCoDirectorSession();
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, plan, setup, suggestedPrompt]);

  return (
    <div className="codirector-conversation" aria-live="polite">
      {!conversationStarted && <CoDirectorWelcome compact={compactWelcome} />}
      <div className="codirector-messages">
        {messages.map((message) => (
          <CoDirectorMessage
            key={message.id}
            message={message}
            onRetry={
              message.role === "user"
                ? () => {
                    if (!busy) void send(message.content, "chat");
                  }
                : undefined
            }
          />
        ))}
      </div>

      {sendError && (
        <div className="codirector-cta-card codirector-error-card" role="alert">
          <p className="scene-meta">Co-Director couldn't send that message</p>
          <p>{sendError.message}</p>
          <div className="row-actions">
            <button type="button" className="ghost" onClick={() => dismissSendError()}>
              Dismiss
            </button>
            <button type="button" className="ghost" onClick={() => openSettings()}>
              Open Settings
            </button>
            {sendError.recoverable !== false && (
              <button type="button" className="primary" disabled={busy} onClick={() => retryLastSend()}>
                Retry
              </button>
            )}
          </div>
        </div>
      )}

      {plan && <CoDirectorTaskStatus />}

      {setup && (
        <div className="codirector-cta-card">
          <p className="scene-meta">Proposed scene setup</p>
          <ul className="assistant-setup-list">
            {summarizeSetup(setup).map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          {!uiContext.projectId || !uiContext.sceneId ? (
            <p className="muted">Open a project and select a scene to apply.</p>
          ) : (
            <div className="row-actions">
              <button type="button" className="ghost" disabled={applying} onClick={() => dismissSetup()}>
                Dismiss
              </button>
              <button type="button" className="primary" disabled={applying} onClick={() => void applySetup()}>
                {applying ? "Applying…" : "Add to Scene"}
              </button>
            </div>
          )}
        </div>
      )}

      {suggestedPrompt && !setup && (
        <div className="codirector-cta-card">
          <p className="scene-meta">Suggested prompt ready</p>
          <div className="row-actions">
            <button type="button" className="ghost" onClick={() => dismissSuggestedPrompt()}>
              Dismiss
            </button>
            <button type="button" className="primary" onClick={() => applySuggestedPrompt()}>
              Use this prompt
            </button>
          </div>
        </div>
      )}

      {applyNote && !setup && <div className="codirector-cta-card muted">{applyNote}</div>}
      <div ref={endRef} />
    </div>
  );
}
