import { useEffect, useRef } from "react";
import { useCoDirectorSession } from "./CoDirectorSession";
import { CoDirectorMessage } from "./CoDirectorMessage";
import { CoDirectorWelcome } from "./CoDirectorWelcome";
import { CoDirectorTaskStatus } from "./CoDirectorTaskStatus";
import { CoDirectorProposalCard } from "./CoDirectorProposalCard";
import { CoDirectorToolStatus } from "./CoDirectorToolStatus";
import { CoDirectorIntelligenceStatus } from "./CoDirectorIntelligenceStatus";
import { CoDirectorProductionAnalysisPanel } from "./CoDirectorProductionAnalysis";
import { CoDirectorValidationWorkspace } from "./CoDirectorValidationWorkspace";
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
    proposals,
    proposalActingId,
    toolActivity,
    intelligenceProgress,
    productionAnalysis,
    productionAnalysisExpanded,
    expertiseMode,
    setExpertiseMode,
    toggleProductionAnalysis,
    approveProposal,
    rejectProposal,
    requestProposalRevision,
    cancelProposal,
    uiContext,
    send,
    busy,
    sendError,
    dismissSendError,
    retryLastSend,
    openSettings,
    visionValidationEnabled,
  } = useCoDirectorSession();
  const visualValidationPending = Boolean(
    productionAnalysis?.recommendation?.visualValidationPending,
  );
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, plan, setup, suggestedPrompt, proposals, toolActivity, intelligenceProgress, productionAnalysis]);

  return (
    <div className="codirector-conversation" aria-live="polite">
      {!conversationStarted && <CoDirectorWelcome compact={compactWelcome} />}
      {intelligenceProgress && <CoDirectorIntelligenceStatus progress={intelligenceProgress} />}

      {uiContext.projectId && (
        <CoDirectorValidationWorkspace
          projectId={uiContext.projectId}
          enabled={Boolean(visionValidationEnabled)}
          pending={visualValidationPending}
          sceneId={uiContext.sceneId}
        />
      )}
      <CoDirectorProductionAnalysisPanel
        analysis={productionAnalysis}
        expanded={productionAnalysisExpanded}
        onToggle={toggleProductionAnalysis}
        expertiseMode={expertiseMode}
        onExpertiseModeChange={setExpertiseMode}
      />
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

      {toolActivity && <CoDirectorToolStatus activity={toolActivity} />}

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

      {proposals.map((proposal) => (
        <CoDirectorProposalCard
          key={proposal.id}
          proposal={proposal}
          busy={proposalActingId === proposal.id}
          onApprove={() => void approveProposal(proposal.id)}
          onReject={(note) => void rejectProposal(proposal.id, note)}
          onRequestRevision={(note) => void requestProposalRevision(proposal.id, note)}
          onCancel={() => void cancelProposal(proposal.id)}
        />
      ))}

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
