import { useEffect, useState } from "react";
import { api, type CoDirectorProposal } from "../../api";
import { CoDirectorEmptyState } from "./cards";

/**
 * Legacy M2.1.4 Approval Center surface.
 * Wave 2: never seed fake hitchhiker / sample pending items.
 * Prefer Co-Director Project Content Approvals tab for product UI.
 */
export function ApprovalCenterPanel({ projectId }: { projectId: string }) {
  const [proposals, setProposals] = useState<CoDirectorProposal[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.listProposals(projectId);
        if (!cancelled) {
          setProposals(res.proposals || []);
          setLoaded(true);
        }
      } catch {
        if (!cancelled) {
          setProposals([]);
          setLoaded(true);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const pending = proposals.filter((p) => p.status === "pending" || p.status === "revision_requested");

  return (
    <section className="m214-approval-center" data-testid="m214-approval-center" aria-label="Approval Center">
      <h3>Approval Center</h3>
      {!loaded ? (
        <p className="muted">Loading…</p>
      ) : pending.length === 0 ? (
        <CoDirectorEmptyState
          testId="m214-approvals-empty"
          title="No approvals are waiting."
          description="Co-Director will place proposed production changes here before applying them."
        />
      ) : (
        <>
          <p>Pending: {pending.length}</p>
          <ul>
            {pending.map((p) => (
              <li key={p.id}>
                <span className="m214-status m214-status-pending" aria-label={`${p.title} pending`}>
                  {p.title}: {p.status}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
      <p className="eyebrow">No silent approvals · No sample seeds</p>
    </section>
  );
}
