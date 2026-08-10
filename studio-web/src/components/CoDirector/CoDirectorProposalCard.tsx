import { useState } from "react";
import type { CoDirectorProposal } from "../../api";

function describeMutations(proposal: CoDirectorProposal): string[] {
  const lines: string[] = [];
  for (const m of proposal.payload.entityMutations) {
    if (m.remove) {
      lines.push(`Remove ${m.entityType}: ${m.displayName || m.entityKey}`);
    } else {
      lines.push(`${m.entityType}: ${m.displayName || m.entityKey}`);
    }
  }
  for (const f of proposal.payload.factMutations) {
    if (!f.remove) lines.push(`Fact: ${f.statement.slice(0, 120)}`);
  }
  return lines;
}

const TERMINAL_NO_APPROVE = new Set([
  "approved",
  "completed",
  "rejected",
  "cancelled",
  "failed",
  "executing",
]);

/**
 * Renders a durable Co-Director proposal as an approve/reject/request-revision card — never as
 * raw JSON, and never as something the model can apply itself.
 */
export function CoDirectorProposalCard({
  proposal,
  busy,
  productionCapable = true,
  onApprove,
  onReject,
  onRequestRevision,
  onCancel,
}: {
  proposal: CoDirectorProposal;
  busy: boolean;
  productionCapable?: boolean;
  onApprove: () => void;
  onReject: (note?: string) => void;
  onRequestRevision: (note?: string) => void;
  onCancel: () => void;
}) {
  const [note, setNote] = useState("");
  const [detailsOpen, setDetailsOpen] = useState(false);
  const toolCall = proposal.proposalType === "tool_call" ? proposal.toolCall : null;
  const preview = toolCall?.preview;
  const lines = toolCall ? preview?.lines ?? [] : describeMutations(proposal);
  const warnings = preview?.warnings ?? [];
  const isStale = proposal.isStale || proposal.status === "stale";
  const isExecuting = proposal.status === "executing";
  const isFailed = proposal.status === "failed";
  const isReviewable = proposal.status === "pending" || proposal.status === "revision_requested";
  const canApprove = isReviewable && !isStale && productionCapable && !TERMINAL_NO_APPROVE.has(proposal.status);
  const providerHint =
    (toolCall?.capabilitySnapshot?.provider as string | undefined) ||
    (toolCall?.capabilitySnapshot?.model as string | undefined) ||
    null;
  const cloudLocal =
    typeof toolCall?.capabilitySnapshot?.execution === "string"
      ? String(toolCall.capabilitySnapshot.execution)
      : typeof toolCall?.capabilitySnapshot?.local === "boolean"
        ? toolCall.capabilitySnapshot.local
          ? "local"
          : "cloud"
        : null;

  return (
    <div
      className={`codirector-cta-card codirector-proposal-card${toolCall ? " codirector-proposal-tool" : ""}`}
      role="group"
      aria-label={`Proposal: ${proposal.title}`}
      data-testid={`codirector-proposal-card-${proposal.id}`}
      data-status={proposal.status}
    >
      <p className="scene-meta">
        {toolCall ? "Co-Director action · needs your approval" : "Production Bible proposal"}
        {proposal.status === "revision_requested" && " · revision requested"}
        {isFailed && " · failed"}
      </p>
      <p className="codirector-proposal-title">{proposal.title}</p>
      {(preview?.summary || proposal.summary) && <p className="muted">{preview?.summary || proposal.summary}</p>}

      {/* W6P-4: never bury approval inside generic chat — structured disclosure */}
      <div className="codirector-approval-disclosure" data-testid="codirector-approval-disclosure">
        <p className="scene-meta">Approval disclosure</p>
        <ul className="assistant-setup-list">
          <li>
            <strong>Intended action:</strong> {toolCall?.toolId || proposal.proposalType}
          </li>
          <li>
            <strong>Capability:</strong>{" "}
            {String(
              (toolCall?.capabilitySnapshot as Record<string, unknown> | undefined)?.capability ||
                (toolCall?.capabilitySnapshot as Record<string, unknown> | undefined)?.workflowKey ||
                toolCall?.toolId ||
                "—",
            )}
          </li>
          <li>
            <strong>Provider:</strong> {cloudLocal || providerHint || "local (default)"}
          </li>
          <li>
            <strong>Expected outputs:</strong>{" "}
            {lines.length ? `${lines.length} change(s) listed below` : "See summary"}
          </li>
          <li>
            <strong>May consume credits:</strong>{" "}
            {cloudLocal === "cloud" ? "Yes — paid cloud" : "No (local path)"}
          </li>
        </ul>
      </div>

      <dl className="codirector-proposal-meta">
        <div>
          <dt>Project</dt>
          <dd>{proposal.projectId || "—"}</dd>
        </div>
        <div>
          <dt>Records</dt>
          <dd>{lines.length || 0}</dd>
        </div>
        {toolCall?.toolId ? (
          <div>
            <dt>Tool</dt>
            <dd>{toolCall.toolId}</dd>
          </div>
        ) : null}
        {providerHint ? (
          <div>
            <dt>Provider / model</dt>
            <dd>{providerHint}</dd>
          </div>
        ) : null}
        {cloudLocal ? (
          <div>
            <dt>Execution</dt>
            <dd>{cloudLocal}</dd>
          </div>
        ) : null}
        <div>
          <dt>Created</dt>
          <dd>{proposal.createdAt ? new Date(proposal.createdAt).toLocaleString() : "—"}</dd>
        </div>
      </dl>

      {lines.length > 0 && (
        <ul className="assistant-setup-list">
          {lines.map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </ul>
      )}

      {warnings.map((warning) => (
        <p key={warning} className="codirector-proposal-warning">
          {warning}
        </p>
      ))}

      {!productionCapable && isReviewable && (
        <p className="codirector-proposal-warning" role="status">
          Select a project before approving production changes.
        </p>
      )}

      {isStale && (
        <p className="codirector-proposal-stale" role="alert">
          {toolCall
            ? "The project changed since this action was proposed. It can no longer be approved as-is — cancel it and ask Co-Director again."
            : "The Production Bible changed since this proposal was created. It can no longer be approved as-is — cancel it and ask Co-Director again."}
        </p>
      )}

      {isExecuting && <p className="muted">Applying…</p>}
      {isFailed && <p className="codirector-proposal-warning" role="alert">Proposal failed. Partial work was not marked complete.</p>}

      <div className="row-actions">
        <button type="button" className="ghost" onClick={() => setDetailsOpen((v) => !v)}>
          {detailsOpen ? "Hide details" : "Details"}
        </button>
      </div>
      {detailsOpen && (
        <pre className="codirector-proposal-details" data-testid="codirector-proposal-details">
          {JSON.stringify(
            {
              id: proposal.id,
              status: proposal.status,
              proposalType: proposal.proposalType,
              toolId: toolCall?.toolId,
              warnings,
            },
            null,
            2,
          )}
        </pre>
      )}

      {isReviewable && !isStale && (
        <>
          <textarea
            className="codirector-proposal-note"
            placeholder="Optional note (used for reject / request revision)"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={2}
          />
          <div className="row-actions">
            <button type="button" className="ghost" disabled={busy} onClick={() => onReject(note || undefined)}>
              Reject
            </button>
            <button
              type="button"
              className="ghost"
              disabled={busy}
              onClick={() => onRequestRevision(note || undefined)}
            >
              Request Revision
            </button>
            <button
              type="button"
              className="primary"
              disabled={busy || !canApprove}
              onClick={onApprove}
              data-testid="codirector-proposal-approve"
            >
              {busy ? "Approving…" : "Approve"}
            </button>
          </div>
        </>
      )}

      {isStale && (
        <div className="row-actions">
          <button type="button" className="ghost" disabled={busy} onClick={onCancel}>
            Cancel proposal
          </button>
        </div>
      )}
    </div>
  );
}
