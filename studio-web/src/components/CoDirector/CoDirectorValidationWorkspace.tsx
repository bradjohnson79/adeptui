import { useCallback, useEffect, useState } from "react";
import { api, type CoDirectorProposal } from "../../api";
import { CoDirectorProposalCard } from "./CoDirectorProposalCard";

type VisionFinding = {
  validatorId: string;
  status: string;
  score: number;
  summary?: string;
  blocking?: boolean;
  issues?: { code: string; message: string; severity: string }[];
};

type VisionReport = {
  reportId: string;
  sessionId: string;
  overallScore: number;
  passed: boolean;
  band: string;
  strengths: string[];
  warnings: string[];
  failures: string[];
  recommendations: string[];
  findings: VisionFinding[];
  blockingFailures: string[];
  provider: string;
};

type VisionSession = {
  sessionId: string;
  projectId: string;
  assetId?: string | null;
  planId?: string | null;
  status: string;
  reportId?: string | null;
  comparisonId?: string | null;
  provider: string;
  createdAt?: string;
};

type VisionComparison = {
  comparisonId: string;
  referenceAssetId?: string | null;
  generatedAssetId?: string | null;
  referenceMeta: Record<string, unknown>;
  generatedMeta: Record<string, unknown>;
  differences: Record<string, unknown>[];
};

function mapPackageReferenceSet(pkg: {
  referenceSet?: {
    id?: string;
    version?: number;
    bindings?: Array<{
      bindingId?: string;
      role?: string;
      influence?: string;
      referenceAssetId?: string;
      assetId?: string;
    }>;
  } | null;
}):
  | {
      id: string;
      version: number;
      bindings: Array<{
        bindingId: string;
        role: string;
        influence?: string;
        assetId: string;
      }>;
    }
  | undefined {
  const rs = pkg?.referenceSet;
  if (!rs?.id || !Array.isArray(rs.bindings) || rs.bindings.length === 0) {
    return undefined;
  }
  return {
    id: String(rs.id),
    version: Number(rs.version || 1),
    bindings: rs.bindings
      .map((b) => ({
        bindingId: String(b.bindingId || ""),
        role: String(b.role || "other"),
        influence: b.influence ? String(b.influence) : "moderate",
        assetId: String(b.referenceAssetId || b.assetId || ""),
      }))
      .filter((b) => b.bindingId && b.assetId),
  };
}

export function CoDirectorValidationWorkspace({
  projectId,
  enabled,
  pending,
  planId,
  sceneId,
  timelineItemId,
  onClose,
}: {
  projectId: string;
  enabled: boolean;
  pending: boolean;
  planId?: string | null;
  sceneId?: string | null;
  /** Optional Director clip id; when omitted, first image clip with refs (or first clip) is used. */
  timelineItemId?: string | null;
  onClose?: () => void;
}) {
  const [open, setOpen] = useState(pending);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<VisionSession[]>([]);
  const [session, setSession] = useState<VisionSession | null>(null);
  const [report, setReport] = useState<VisionReport | null>(null);
  const [comparison, setComparison] = useState<VisionComparison | null>(null);
  const [proposals, setProposals] = useState<CoDirectorProposal[]>([]);
  const [proposalActingId, setProposalActingId] = useState<string | null>(null);
  const [notes, setNotes] = useState("");

  const refreshHistory = useCallback(async () => {
    if (!enabled || !projectId) return;
    try {
      const data = await api.visionValidationHistory(projectId);
      setHistory((data.sessions || []) as VisionSession[]);
    } catch {
      /* flag may be off mid-session */
    }
  }, [enabled, projectId]);

  const loadSession = useCallback(
    async (sessionId: string) => {
      setBusy(true);
      setError(null);
      try {
        const data = (await api.visionValidationSession(sessionId, projectId)) as VisionSession & {
          report?: VisionReport | null;
        };
        setSession(data);
        if (data.report) setReport(data.report);
        else if (data.reportId) {
          setReport((await api.visionValidationReport(data.reportId, projectId)) as VisionReport);
        }
        if (data.comparisonId) {
          setComparison(
            (await api.visionValidationComparison(data.comparisonId, projectId)) as VisionComparison,
          );
        }
        const proposalList = await api.listProposals(projectId, "pending");
        setProposals(
          (proposalList.proposals || []).filter(
            (p) =>
              p.proposalType === "tool_call" &&
              ["propose_vision_correction", "propose_asset_bible_link", "record_vision_review"].includes(
                p.toolCall?.toolId || "",
              ),
          ),
        );
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load validation session.");
      } finally {
        setBusy(false);
      }
    },
    [projectId],
  );

  useEffect(() => {
    if (pending && enabled) setOpen(true);
  }, [pending, enabled]);

  useEffect(() => {
    if (open && enabled) void refreshHistory();
  }, [open, enabled, refreshHistory]);

  if (!enabled) return null;

  async function resolveReferenceSet(): Promise<
    | {
        id: string;
        version: number;
        bindings: Array<{
          bindingId: string;
          role: string;
          influence?: string;
          assetId: string;
        }>;
      }
    | undefined
  > {
    if (!sceneId) return undefined;
    try {
      let itemId = timelineItemId || undefined;
      if (!itemId) {
        const director = await api.getDirector(projectId, sceneId);
        const clips = (director?.image_clips || []) as Array<{ id?: string }>;
        if (!clips.length) return undefined;
        // Prefer a clip that already has bindings so closed-loop validation is binding-aware.
        for (const clip of clips) {
          if (!clip.id) continue;
          const refs = await api.getTimelineReferences(projectId, sceneId, clip.id);
          if (Number(refs?.count || 0) > 0) {
            itemId = clip.id;
            break;
          }
        }
        itemId = itemId || clips[0]?.id;
      }
      if (!itemId) return undefined;
      const pkg = await api.getTimelineReferencePackage(projectId, sceneId, itemId);
      return mapPackageReferenceSet(pkg);
    } catch {
      // References flag may be off — validate without referenceSet.
      return undefined;
    }
  }

  async function runValidate() {
    setBusy(true);
    setError(null);
    try {
      const referenceSet = await resolveReferenceSet();
      const result = await api.visionValidate({
        projectId,
        planId: planId || undefined,
        sceneId: sceneId || undefined,
        referenceSet,
        provider: "local",
      });
      const nextSession = result.session as VisionSession;
      setSession(nextSession);
      setReport(result.report as VisionReport);
      setComparison(result.comparison as VisionComparison);
      await refreshHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Validation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function decide(kind: "approve" | "reject") {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      const body = {
        projectId,
        sessionId: session.sessionId,
        notes,
        linkToBible: kind === "approve",
      };
      if (kind === "approve") await api.visionApprove(body);
      else await api.visionReject(body);
      await loadSession(session.sessionId);
      await refreshHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Review decision failed.");
    } finally {
      setBusy(false);
    }
  }

  async function proposeCorrection() {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      await api.visionCorrection({
        projectId,
        sessionId: session.sessionId,
        notes,
      });
      await loadSession(session.sessionId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create correction proposal.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="codirector-validation-workspace" data-testid="codirector-validation-workspace">
      {!open && pending && (
        <div className="codirector-cta-card" role="status">
          <p className="scene-meta">Visual validation pending</p>
          <p className="muted">A production plan is waiting for M2.5 vision review.</p>
          <div className="row-actions">
            <button
              type="button"
              className="primary"
              data-testid="open-validation-workspace"
              onClick={() => setOpen(true)}
            >
              Open Validation Workspace
            </button>
          </div>
        </div>
      )}

      {open && (
        <div className="codirector-cta-card codirector-validation-panel">
          <div className="codirector-validation-header">
            <p className="scene-meta">Validation Workspace</p>
            <button
              type="button"
              className="ghost"
              onClick={() => {
                setOpen(false);
                onClose?.();
              }}
            >
              Hide
            </button>
          </div>

          <p className="muted">
            Inspectors only — no auto-regenerate, no silent Bible writes. Approve creates a Bible link
            proposal.
          </p>

          <div className="row-actions">
            <button type="button" className="primary" disabled={busy} onClick={() => void runValidate()}>
              {busy ? "Working…" : "Run mock validation"}
            </button>
            {session && (
              <>
                <button type="button" className="ghost" disabled={busy} onClick={() => void decide("approve")}>
                  Approve
                </button>
                <button type="button" className="ghost" disabled={busy} onClick={() => void decide("reject")}>
                  Reject
                </button>
                <button
                  type="button"
                  className="ghost"
                  disabled={busy}
                  onClick={() => void proposeCorrection()}
                >
                  Propose correction
                </button>
              </>
            )}
          </div>

          <label className="codirector-validation-notes">
            <span className="scene-meta">Review notes</span>
            <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} />
          </label>

          {error && (
            <p className="codirector-proposal-warning" role="alert">
              {error}
            </p>
          )}

          {report && (
            <section className="codirector-validation-summary" data-testid="validation-summary">
              <p className="codirector-proposal-title">
                Score {report.overallScore} · {report.band}
                {report.passed ? " · passed" : ""}
              </p>
              <p className="muted">
                Provider {report.provider} · session {report.sessionId.slice(0, 8)}…
              </p>
              {report.blockingFailures?.length > 0 && (
                <p className="codirector-proposal-warning">
                  Blocking: {report.blockingFailures.join(", ")}
                </p>
              )}
              <ul className="assistant-setup-list">
                {report.failures.map((line) => (
                  <li key={`f-${line}`}>Fail — {line}</li>
                ))}
                {report.warnings.map((line) => (
                  <li key={`w-${line}`}>Warn — {line}</li>
                ))}
                {report.recommendations.slice(0, 6).map((line) => (
                  <li key={`r-${line}`}>{line}</li>
                ))}
              </ul>
            </section>
          )}

          {comparison && (
            <section className="codirector-validation-comparison" data-testid="validation-comparison">
              <p className="eyebrow">Side-by-side comparison</p>
              <div className="codirector-validation-compare-grid">
                <div>
                  <p className="scene-meta">Reference</p>
                  <p className="muted">
                    {(comparison.referenceMeta.filename as string) ||
                      comparison.referenceAssetId ||
                      "None"}
                  </p>
                </div>
                <div>
                  <p className="scene-meta">Generated</p>
                  <p className="muted">
                    {(comparison.generatedMeta.filename as string) ||
                      comparison.generatedAssetId ||
                      "Mock / pending asset"}
                  </p>
                </div>
              </div>
              {comparison.differences.length > 0 && (
                <ul className="assistant-setup-list">
                  {comparison.differences.map((diff, idx) => (
                    <li key={idx}>{JSON.stringify(diff)}</li>
                  ))}
                </ul>
              )}
            </section>
          )}

          {report?.findings?.length ? (
            <section>
              <p className="eyebrow">Issues by validator</p>
              <ul className="assistant-setup-list">
                {report.findings.map((f) => (
                  <li key={f.validatorId}>
                    <strong>{f.validatorId}</strong> {f.status} ({f.score})
                    {f.summary ? ` — ${f.summary}` : ""}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {history.length > 0 && (
            <section data-testid="validation-history">
              <p className="eyebrow">History</p>
              <ul className="assistant-setup-list">
                {history.slice(0, 8).map((item) => (
                  <li key={item.sessionId}>
                    <button
                      type="button"
                      className="ghost"
                      disabled={busy}
                      onClick={() => void loadSession(item.sessionId)}
                    >
                      {item.status} · {item.provider} · {item.sessionId.slice(0, 8)}
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {proposals.map((proposal) => (
            <CoDirectorProposalCard
              key={proposal.id}
              proposal={proposal}
              busy={proposalActingId === proposal.id}
              onApprove={async () => {
                setProposalActingId(proposal.id);
                try {
                  await api.approveProposal(projectId, proposal.id);
                  setProposals((prev) => prev.filter((p) => p.id !== proposal.id));
                } finally {
                  setProposalActingId(null);
                }
              }}
              onReject={async (note) => {
                setProposalActingId(proposal.id);
                try {
                  await api.rejectProposal(projectId, proposal.id, { note });
                  setProposals((prev) => prev.filter((p) => p.id !== proposal.id));
                } finally {
                  setProposalActingId(null);
                }
              }}
              onRequestRevision={async (note) => {
                setProposalActingId(proposal.id);
                try {
                  await api.requestProposalRevision(projectId, proposal.id, { note });
                } finally {
                  setProposalActingId(null);
                }
              }}
              onCancel={async () => {
                setProposalActingId(proposal.id);
                try {
                  await api.cancelProposal(projectId, proposal.id);
                  setProposals((prev) => prev.filter((p) => p.id !== proposal.id));
                } finally {
                  setProposalActingId(null);
                }
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}
