import { useState } from "react";
import type { CoDirectorProposal } from "../../api";
import { approvalSummary, handleApprovalChoice } from "./approvalSummary";
import { STALE_APPROVAL_COPY, approvalCardIsActionable } from "./approvalLifetime";

const TERMINAL_NO_APPROVE = new Set([
  "approved",
  "completed",
  "rejected",
  "cancelled",
  "failed",
  "executing",
]);

/**
 * Creator-facing approval card. The stored proposal stays authoritative.
 * Tool ids and internal ids stay behind Technical details.
 */
export function CoDirectorProposalCard({
  proposal,
  busy,
  productionCapable = true,
  onApprove,
  onReject,
  onRevise,
  onCancel,
}: {
  proposal: CoDirectorProposal;
  busy: boolean;
  productionCapable?: boolean;
  onApprove: () => void;
  onReject: (note?: string) => void;
  onRevise: (correction: string) => void;
  onCancel: () => void;
}) {
  const [correction, setCorrection] = useState("");
  const [revising, setRevising] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const toolCall = proposal.proposalType === "tool_call" ? proposal.toolCall : null;
  const summary = approvalSummary(toolCall?.toolId || "", (toolCall?.arguments as Record<string, unknown>) || {});
  const isStale = proposal.isStale || proposal.status === "stale";
  const isExecuting = proposal.status === "executing";
  const isFailed = proposal.status === "failed";
  const isRejected = proposal.status === "rejected";
  const isReviewable = approvalCardIsActionable(proposal);
  const canApprove = approvalCardIsActionable(proposal) && productionCapable && !TERMINAL_NO_APPROVE.has(proposal.status);

  return (
    <div
      className={`codirector-cta-card codirector-proposal-card${toolCall ? " codirector-proposal-tool" : ""}`}
      role="group"
      aria-label="Approval needed"
      data-testid={`codirector-proposal-card-${proposal.id}`}
      data-status={proposal.status}
    >
      <p className="scene-meta">Approval needed</p>
      <p className="codirector-proposal-title" data-testid="codirector-approval-wants">
        <strong>Co-Director wants to: </strong>
        {summary.wants}
      </p>
      {isReviewable ? <p className="muted">Prepared and waiting for approval.</p> : null}

      {summary.details.length > 0 && (
        <ul className="assistant-setup-list" data-testid="codirector-approval-details">
          {summary.details.map((detail) => (
            <li key={detail.label}>
              <strong>{detail.label}: </strong>
              {detail.value}
            </li>
          ))}
        </ul>
      )}

      {!productionCapable && isReviewable && (
        <p className="codirector-proposal-warning" role="status">
          Select a project before approving production changes.
        </p>
      )}

      {isStale && (
        <p className="codirector-proposal-stale" role="alert">
          {STALE_APPROVAL_COPY}
        </p>
      )}

      {isExecuting && <p className="muted">Working on it…</p>}
      {isFailed && (
        <p className="codirector-proposal-warning" role="alert">
          That did not finish. Nothing was marked complete.
        </p>
      )}
      {isRejected && <p role="status">Request rejected. Nothing was changed.</p>}

      <div className="row-actions">
        <button type="button" className="ghost" onClick={() => setDetailsOpen((open) => !open)}>
          {detailsOpen ? "Hide technical details" : "Technical details"}
        </button>
      </div>
      {detailsOpen && (
        <pre className="codirector-proposal-details" data-testid="codirector-proposal-details">
          {JSON.stringify(
            {
              toolId: toolCall?.toolId,
              arguments: toolCall?.arguments,
              proposalId: proposal.id,
              projectId: proposal.projectId,
            },
            null,
            2,
          )}
        </pre>
      )}

      {isReviewable && !isStale && revising && (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            const next = correction.trim();
            if (!next || busy) return;
            handleApprovalChoice("revise", {
              onApprove,
              onRevise: () => onRevise(next),
              onReject: () => onReject(),
            });
          }}
        >
          <label className="muted" htmlFor={`revise-${proposal.id}`}>
            What would you like changed?
          </label>
          <textarea
            id={`revise-${proposal.id}`}
            className="codirector-proposal-note"
            value={correction}
            onChange={(event) => setCorrection(event.target.value)}
            rows={3}
          />
          <div className="row-actions">
            <button type="submit" className="primary" disabled={busy || !correction.trim()} data-testid="codirector-proposal-revise-send">
              Send correction
            </button>
            <button type="button" className="ghost" disabled={busy} onClick={() => setRevising(false)}>
              Back
            </button>
          </div>
        </form>
      )}

      {isReviewable && !isStale && !revising && (
        <div className="row-actions">
          <button
            type="button"
            className="primary"
            disabled={busy || !canApprove}
            onClick={() =>
              handleApprovalChoice("approve", {
                onApprove,
                onRevise: () => setRevising(true),
                onReject: () => onReject(),
              })
            }
            data-testid="codirector-proposal-approve"
          >
            {busy ? "Approving…" : "Approve"}
          </button>
          <button
            type="button"
            className="ghost"
            disabled={busy}
            onClick={() =>
              handleApprovalChoice("revise", {
                onApprove,
                onRevise: () => setRevising(true),
                onReject: () => onReject(),
              })
            }
            data-testid="codirector-proposal-revise"
          >
            Revise
          </button>
          <button
            type="button"
            className="ghost"
            disabled={busy}
            onClick={() =>
              handleApprovalChoice("reject", {
                onApprove,
                onRevise: () => setRevising(true),
                onReject: () => onReject(),
              })
            }
            data-testid="codirector-proposal-reject"
          >
            Reject
          </button>
        </div>
      )}

      {isStale && (
        <div className="row-actions">
          <button type="button" className="ghost" disabled={busy} onClick={onCancel}>
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}
