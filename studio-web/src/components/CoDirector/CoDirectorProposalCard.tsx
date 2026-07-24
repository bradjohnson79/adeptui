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

/**
 * Renders a durable Co-Director proposal as an approve/reject/request-revision card — never
 * as raw JSON. The Bible is never mutated until the user explicitly approves.
 */
export function CoDirectorProposalCard({
  proposal,
  busy,
  onApprove,
  onReject,
  onRequestRevision,
  onCancel,
}: {
  proposal: CoDirectorProposal;
  busy: boolean;
  onApprove: () => void;
  onReject: (note?: string) => void;
  onRequestRevision: (note?: string) => void;
  onCancel: () => void;
}) {
  const [note, setNote] = useState("");
  const mutationLines = describeMutations(proposal);
  const isStale = proposal.isStale || proposal.status === "stale";
  const isExecuting = proposal.status === "executing";
  const isReviewable = proposal.status === "pending" || proposal.status === "revision_requested";

  return (
    <div className="codirector-cta-card codirector-proposal-card" role="group" aria-label={`Proposal: ${proposal.title}`}>
      <p className="scene-meta">
        Production Bible proposal
        {proposal.status === "revision_requested" && " · revision requested"}
      </p>
      <p className="codirector-proposal-title">{proposal.title}</p>
      {proposal.summary && <p className="muted">{proposal.summary}</p>}
      {mutationLines.length > 0 && (
        <ul className="assistant-setup-list">
          {mutationLines.map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </ul>
      )}

      {isStale && (
        <p className="codirector-proposal-stale" role="alert">
          The Production Bible changed since this proposal was created. It can no longer be
          approved as-is — cancel it and ask Co-Director again.
        </p>
      )}

      {isExecuting && <p className="muted">Applying…</p>}

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
            <button type="button" className="primary" disabled={busy} onClick={onApprove}>
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
