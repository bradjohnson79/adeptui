import { useEffect, useRef } from "react";
import { Button } from "../ui";
import { useCoDirectorSession } from "./CoDirectorSession";
import { CoDirectorActivityPanel } from "./CoDirectorActivityPanel";
import { CoDirectorChangeReview } from "./CoDirectorChangeReview";
import { CoDirectorMessage } from "./CoDirectorMessage";
import { CoDirectorWelcome } from "./CoDirectorWelcome";
import { CoDirectorProposalCard } from "./CoDirectorProposalCard";
import { CoDirectorRelationshipCard } from "./CoDirectorRelationshipCard";
import { CoDirectorProjectPulse } from "./CoDirectorProjectPulse";
import { CoDirectorProcessingStatus } from "./CoDirectorProcessingStatus";
import { CoDirectorNextStepChips } from "./CoDirectorNextStepChips";
import { CoDirectorMomentumCard } from "./CoDirectorMomentumCard";
import { CoDirectorDeliverableReview } from "./CoDirectorPartnershipPanels";
import { isAgentWork, isTerminal } from "./AgentWorkSurface/types";
import { summarizeSetup } from "./types";

/**
 * Chat-first conversation surface.
 * Dense dashboards are omitted from the default stream — use Project Content / menu.
 */
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
    activity,
    approveProposal,
    rejectProposal,
    requestProposalRevision,
    cancelProposal,
    productionCapable,
    send,
    busy,
    sendError,
    dismissSendError,
    retryLastSend,
    openSettings,
    uiContext,
    activeExecution,
  } = useCoDirectorSession();
  const endRef = useRef<HTMLDivElement>(null);

  // Spec §9/§30: when an agent execution is in flight (terminal or not),
  // suppress generic conversational chips/cards. The AgentWorkSurface footer
  // owns contextual result actions (e.g. "Regenerate Frame", "Open in Library")
  // when the execution is terminal.
  const executionActive = isAgentWork(activeExecution) && !isTerminal(activeExecution);
  const agentWorkPresent = isAgentWork(activeExecution);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, plan, setup, suggestedPrompt, proposals, activity]);

  return (
    <div className="codirector-conversation" aria-live="polite" data-testid="codirector-conversation">
      {!conversationStarted && <CoDirectorWelcome compact={compactWelcome} />}
      <CoDirectorRelationshipCard />
      <CoDirectorActivityPanel />
      <CoDirectorProcessingStatus />
      <CoDirectorMomentumCard />
      <CoDirectorProjectPulse />
      <CoDirectorChangeReview />
      <CoDirectorDeliverableReview />
      {activity?.conversationActions?.length ? (
        <div
          className="codirector-content-card"
          data-testid="codirector-conversation-actions"
          style={{ marginTop: "0.5rem", display: "flex", flexWrap: "wrap", gap: "0.35rem" }}
        >
          {activity.conversationActions.map((action) => (
            <Button
              key={action.id}
              variant={action.id === "continue_explaining" ? undefined : "ghost"}
              compact
              data-testid={`codirector-action-${action.id}`}
              disabled={busy}
              onClick={() => {
                if (busy) return;
                if (action.id === "continue_explaining") {
                  void send("I’d like to continue explaining. Keep listening.", "chat");
                } else if (action.id === "answer_questions") {
                  void send("I’ll answer a few discovery questions next.", "chat");
                } else if (action.id === "research_comparables") {
                  void send("Please authorize research into similar works and note what makes this project different.", "chat");
                } else if (action.id === "create_story_template" || action.id === "expand_preview") {
                  void send("Please expand that preview into a draft story template for me to review.", "chat");
                } else if (action.id === "prepare_short_pitch") {
                  void send("Please prepare a short pitch draft from what we have so I can review it.", "chat");
                } else if (action.id === "review_draft") {
                  void send("Let’s revise the draft together — keep what works and improve what feels thin.", "chat");
                }
              }}
            >
              {action.label}
            </Button>
          ))}
        </div>
      ) : null}

      <div className="codirector-messages">
        {messages.map((message, index) => {
          const isLatestAssistant =
            message.role === "assistant" &&
            index === messages.map((m) => m.role).lastIndexOf("assistant");
          return (
            <div key={message.id}>
              <CoDirectorMessage
                message={message}
                onRetry={
                  message.role === "user"
                    ? () => {
                        if (!busy) void send(message.content, "chat");
                      }
                    : undefined
                }
              />
              {isLatestAssistant && !agentWorkPresent ? <CoDirectorNextStepChips /> : null}
            </div>
          );
        })}
      </div>

      {sendError && (
        <div className="codirector-action-card" role="alert" data-testid="codirector-send-error">
          <h3>{sendError.category === "tool" ? "Change not saved" : "Request failed"}</h3>
          <p>{sendError.message}</p>
          {sendError.details || sendError.technical_evidence ? (
            <details>
              <summary>Technical details</summary>
              <pre className="codirector-retrieval-json">
                {JSON.stringify(
                  {
                    code: sendError.code,
                    details: sendError.details || undefined,
                    technicalEvidence: sendError.technical_evidence || undefined,
                  },
                  null,
                  2,
                )}
              </pre>
            </details>
          ) : null}
          <div className="row">
            <Button variant="ghost" compact onClick={() => dismissSendError()}>
              Dismiss
            </Button>
            <Button variant="ghost" compact onClick={() => openSettings()}>
              Settings
            </Button>
            {sendError.recoverable !== false && (
              <Button variant="primary" compact disabled={busy} onClick={() => retryLastSend()}>
                Retry
              </Button>
            )}
          </div>
        </div>
      )}


      {!executionActive &&
        proposals.map((proposal) => (
          <CoDirectorProposalCard
            key={proposal.id}
            proposal={proposal}
            busy={proposalActingId === proposal.id}
            productionCapable={productionCapable}
            onApprove={() => void approveProposal(proposal.id)}
            onReject={(note) => void rejectProposal(proposal.id, note)}
            onRequestRevision={(note) => void requestProposalRevision(proposal.id, note)}
            onCancel={() => void cancelProposal(proposal.id)}
          />
        ))}

      {setup && (
        <div className="codirector-action-card" data-testid="codirector-setup-card">
          <h3>Next step</h3>
          <ul>
            {summarizeSetup(setup).map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          {!uiContext.projectId || !uiContext.sceneId ? (
            <p className="muted">Open a project and select a scene to apply.</p>
          ) : (
            <div className="row">
              <Button variant="ghost" compact disabled={applying} onClick={() => dismissSetup()}>
                Dismiss
              </Button>
              <Button variant="primary" compact disabled={applying} onClick={() => void applySetup()}>
                {applying ? "Applying…" : "Add to Scene"}
              </Button>
            </div>
          )}
        </div>
      )}

      {suggestedPrompt && !setup && (
        <div className="codirector-action-card">
          <h3>Suggested prompt</h3>
          <div className="row">
            <Button variant="ghost" compact onClick={() => dismissSuggestedPrompt()}>
              Dismiss
            </Button>
            <Button variant="primary" compact onClick={() => applySuggestedPrompt()}>
              Use this prompt
            </Button>
          </div>
        </div>
      )}

      {applyNote && !setup && <div className="codirector-action-card muted">{applyNote}</div>}
      <div ref={endRef} />
    </div>
  );
}
