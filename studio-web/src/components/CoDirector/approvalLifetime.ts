/** Approval-card state. Freshness is a server flag. Rendering does not age a proposal. */

export const STALE_APPROVAL_COPY =
  "This approval is no longer current. Ask Co-Director to prepare it again.";

const REVIEWABLE = new Set(["pending", "revision_requested"]);

export function approvalCardIsActionable(proposal: { status: string; isStale?: boolean }): boolean {
  return REVIEWABLE.has(proposal.status) && proposal.isStale !== true;
}
