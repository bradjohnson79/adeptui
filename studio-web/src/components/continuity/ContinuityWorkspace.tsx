import { useCallback, useEffect, useState } from "react";
import { api } from "../../api";
import type { Project } from "../../types";

type Props = { project: Project; onChange?: () => void; onGo?: (tab: string) => void };

const STATUS_LABELS: Record<string, string> = {
  not_assessable: "Not assessed / Not assessable",
  review: "Review required",
  drift: "Drift",
  pass: "Pass",
  error: "Evaluation error",
  approved: "Approved",
  overridden: "Overridden",
};

export function ContinuityWorkspace({ project, onGo }: Props) {
  const [issues, setIssues] = useState<any[]>([]);
  const [identities, setIdentities] = useState<any[]>([]);
  const [summary, setSummary] = useState<any | null>(null);
  const [evaluation, setEvaluation] = useState<any | null>(null);
  const [packetPreview, setPacketPreview] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [assetId, setAssetId] = useState("");
  const [selectedIdentity, setSelectedIdentity] = useState("");

  const reload = useCallback(async () => {
    const [iss, ids, sum] = await Promise.all([
      api.continuity.issues(project.id),
      api.continuity.listIdentities(project.id),
      api.continuity.summary(project.id),
    ]);
    setIssues(iss.items || []);
    setIdentities(ids.items || []);
    setSummary(sum);
  }, [project.id]);

  useEffect(() => {
    void reload().catch((e) => setError(String(e?.message || e)));
  }, [reload]);

  const runPreflight = async () => {
    if (!selectedIdentity) return;
    setError(null);
    try {
      const result = await api.continuity.preflight(project.id, {
        bindings: [
          {
            identityId: selectedIdentity,
            expectedVisibility: "fully_visible",
            requiredRoles: ["canonical_front", "full_body"],
          },
        ],
        workflowSupportsReferences: true,
      });
      setPacketPreview(result);
      if (result.packetId && assetId.trim()) {
        const ev = await api.continuity.evaluate(project.id, {
          assetId: assetId.trim(),
          packetId: String(result.packetId),
        });
        setEvaluation(ev);
      }
    } catch (e: any) {
      setError(String(e?.message || e));
    }
  };

  const review = async (decision: string) => {
    if (!evaluation?.id) return;
    const next = await api.continuity.review(project.id, String(evaluation.id), {
      decision,
      reason: decision === "override_warning" ? "Approved intentional variant." : "",
      notes: "",
      reviewer: "user",
    });
    setEvaluation(next);
  };

  return (
    <div className="workspace-root" data-testid="continuity-workspace">
      <header className="workspace-header">
        <h1>Continuity Workspace</h1>
        <p>
          Compare outputs to frozen Continuity Packets. Automated scores never replace human decisions.
        </p>
      </header>

      {error ? (
        <div role="alert" className="error-banner">
          {error}
        </div>
      ) : null}

      <div
        style={{ display: "grid", gridTemplateColumns: "240px 1fr 320px", gap: 12, minHeight: 480 }}
        data-testid="continuity-workspace-layout"
      >
        <aside data-testid="continuity-nav">
          <h2>Identities</h2>
          <ul>
            {identities.map((id) => (
              <li key={id.id}>
                <button
                  type="button"
                  aria-current={selectedIdentity === id.id}
                  onClick={() => setSelectedIdentity(id.id)}
                >
                  {id.displayName || id.canonicalName}
                </button>
              </li>
            ))}
          </ul>
          <h2>Issues</h2>
          <ul data-testid="continuity-issue-queue">
            {issues.length === 0 ? (
              <li>No open continuity issues.</li>
            ) : (
              issues.map((iss) => (
                <li key={iss.id} data-testid={`continuity-issue-${iss.id}`}>
                  <strong>{iss.severity}</strong> — {iss.title}
                  <div className="muted">{iss.issueType}</div>
                </li>
              ))
            )}
          </ul>
          <button type="button" onClick={() => onGo?.("timeline")}>
            Open Timeline
          </button>
          <button type="button" onClick={() => onGo?.("identityregistry")}>
            Open Character Creator — Approved Look
          </button>
        </aside>

        <section data-testid="continuity-compare-viewer" className="glass-section">
          <h2>Compare / Packet</h2>
          <label>
            Output asset id
            <input
              value={assetId}
              onChange={(e) => setAssetId(e.target.value)}
              data-testid="continuity-asset-id"
              aria-label="Output asset id"
            />
          </label>
          <button type="button" data-testid="continuity-run-preflight" onClick={() => void runPreflight()}>
            Preflight + evaluate
          </button>
          {packetPreview ? (
            <div data-testid="continuity-packet-preview">
              <p>
                Preflight: <strong>{STATUS_LABELS[packetPreview.status] || packetPreview.status}</strong>
              </p>
              <p>Packet: {packetPreview.packetId || "none"} · Bindings: {packetPreview.bindingCount ?? 0}</p>
              {(packetPreview.warnings || []).length ? (
                <ul>
                  {packetPreview.warnings.map((w: any, i: number) => (
                    <li key={i}>{w.code}: {JSON.stringify(w.roles || w.message || w)}</li>
                  ))}
                </ul>
              ) : null}
              {(packetPreview.blockers || []).length ? (
                <ul data-testid="continuity-blockers">
                  {packetPreview.blockers.map((b: any, i: number) => (
                    <li key={i}>{b.code}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : (
            <p>Run preflight to compile a frozen multi-identity Continuity Packet.</p>
          )}
        </section>

        <aside data-testid="continuity-evaluation-panel">
          <h2>Evaluation</h2>
          {!evaluation ? (
            <p>No evaluation yet. Missing evidence is never shown as a false pass.</p>
          ) : (
            <>
              <p data-testid="continuity-overall-status">
                Status: {STATUS_LABELS[evaluation.overallStatus] || evaluation.overallStatus}
                {evaluation.overallScore == null ? " · no aggregate score" : ` · score ${evaluation.overallScore}`}
              </p>
              <p className="muted">
                Evaluator {evaluation.evaluatorKey} v{evaluation.evaluatorVersion}
              </p>
              <ul data-testid="continuity-dimensions">
                {(evaluation.dimensions || []).slice(0, 12).map((d: any, i: number) => (
                  <li key={i}>
                    <strong>{d.dimension}</strong>: {d.status}
                    {d.score == null ? " (no numeric score)" : ` (${d.score})`}
                    <div className="muted">{d.explanation}</div>
                  </li>
                ))}
              </ul>
              <div data-testid="continuity-human-review">
                <h3>Human review</h3>
                <button type="button" onClick={() => void review("approve")}>
                  Approve
                </button>
                <button type="button" onClick={() => void review("override_warning")}>
                  Approve with override
                </button>
                <button type="button" onClick={() => void review("request_correction")}>
                  Request correction
                </button>
                {(evaluation.reviews || []).length ? (
                  <ul>
                    {evaluation.reviews.map((r: any) => (
                      <li key={r.id}>
                        Automated result preserved. Human: {r.decision}
                        {r.previousDecision ? ` (prev ${r.previousDecision})` : ""}
                        {r.reason ? ` — ${r.reason}` : ""}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            </>
          )}
          <p className="muted">Project identities: {summary?.identityCount ?? 0}</p>
        </aside>
      </div>

      <footer data-testid="continuity-shot-strip" className="glass-section">
        <h2>Sequence strip</h2>
        <p>
          Timeline displays canonical continuity statuses only — Not evaluated, Review, Drift, Approved,
          Overridden, Blocked, Evaluation error. Never green without evaluation or human decision.
        </p>
      </footer>
    </div>
  );
}
