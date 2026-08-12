import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useCoDirectorSession } from "./CoDirectorSession";
import type { RecoveryAction, StatusRun } from "../../codirector/status/types";

function statusTone(status: string): string {
  if (status === "Operational") return "is-healthy";
  if (status === "Blocked") return "is-blocked";
  if (status === "Degraded" || status === "Checking") return "is-warning";
  return "";
}

export function CoDirectorStatusPanel() {
  const navigate = useNavigate();
  const {
    uiContext,
    statusLatestRun,
    statusHistory,
    statusChecking,
    statusError,
    loadStatus,
    runStatusCheck,
    setOverflowPanel,
  } = useCoDirectorSession();
  const [copied, setCopied] = useState(false);

  const summary = statusLatestRun?.summary;
  const blockers = useMemo(
    () =>
      (statusLatestRun?.results || []).filter((result) =>
        ["blocked", "failed", "offline", "not_installed", "not_configured"].includes(result.status),
      ),
    [statusLatestRun],
  );
  const warnings = useMemo(
    () =>
      (statusLatestRun?.results || []).filter((result) =>
        ["degraded", "warning", "not_tested", "experimental", "unknown", "timed_out", "slow", "starting"].includes(
          result.status,
        ),
      ),
    [statusLatestRun],
  );
  const busyChecks = useMemo(
    () => (statusLatestRun?.results || []).filter((result) => result.status === "busy"),
    [statusLatestRun],
  );

  const allRecoveryActions = useMemo(() => {
    const seen = new Set<string>();
    const actions: (RecoveryAction & { checkId: string })[] = [];
    for (const result of statusLatestRun?.results || []) {
      for (const action of result.recoveryActions || []) {
        const key = `${result.checkId}:${action.id}`;
        if (seen.has(key)) continue;
        seen.add(key);
        actions.push({ ...action, checkId: result.checkId });
      }
    }
    return actions;
  }, [statusLatestRun]);

  const handleAction = (action: RecoveryAction) => {
    if (action.kind === "open_panel" && action.panel) {
      if (action.panel === "provider" || action.panel === "status" || action.panel === "audit") {
        setOverflowPanel(action.panel as any);
        return;
      }
      navigate(uiContext.projectId ? `/co-director?projectId=${encodeURIComponent(uiContext.projectId)}` : "/co-director");
      return;
    }
    if (action.kind === "open_logs") {
      navigate("/settings");
      return;
    }
    if (action.kind === "open_route" && action.path) {
      if (action.path.startsWith("?") && uiContext.projectId) {
        navigate(`/project/${encodeURIComponent(uiContext.projectId)}${action.path}`);
        return;
      }
      navigate(action.path);
    }
  };

  const copySummary = async (run: StatusRun | null) => {
    if (!run) return;
    const text = [
      `Co-Director Status: ${run.summary.statusIndicator}`,
      `Score: ${run.summary.score} (${run.summary.band})`,
      `Healthy: ${run.summary.healthyChecks}`,
      `Warnings: ${run.summary.warningChecks}`,
      `Blocked: ${run.summary.blockedChecks}`,
      ...(run.explainability.blockers.length ? ["", "Blockers:", ...run.explainability.blockers.map((line) => `- ${line}`)] : []),
      ...(run.explainability.warnings.length ? ["", "Warnings:", ...run.explainability.warnings.map((line) => `- ${line}`)] : []),
    ].join("\n");
    await navigator.clipboard.writeText(text);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  };

  return (
    <div className="codirector-overflow-body codirector-status-panel" data-testid="codirector-status-panel">
      <div className="codirector-status-hero">
        <div className={`codirector-status-gauge ${statusTone(summary?.statusIndicator || "Not Checked")}`}>
          <strong>{statusChecking ? "…" : summary?.score ?? "—"}</strong>
          <span>{statusChecking ? "Checking" : summary?.band || "Not Checked"}</span>
        </div>
        <div className="codirector-status-summary">
          <p className="eyebrow">Production Assurance</p>
          <h3>{statusChecking ? "Checking studio readiness…" : summary?.statusIndicator || "Not Checked"}</h3>
          <p className="muted" data-testid="codirector-status-not-checked-help">
            {statusChecking
              ? "Co-Director is checking project, model, persistence, and production-system readiness."
              : summary?.scoreExplanation ||
                "Co-Director will automatically check production readiness when opened."}
          </p>
          <div className="row-actions">
            <button type="button" disabled={statusChecking} onClick={() => void runStatusCheck()}>
              {statusChecking ? "Checking…" : "Re-check"}
            </button>
            <button type="button" disabled={statusChecking} onClick={() => void runStatusCheck()}>
              Retry Issues
            </button>
            <button type="button" disabled={!statusLatestRun} onClick={() => void copySummary(statusLatestRun)}>
              {copied ? "Copied" : "Copy Summary"}
            </button>
            <button
              type="button"
              disabled={statusChecking}
              onClick={() => {
                if (window.confirm("Run Deep Diagnostic? This gathers a wider technical review.")) {
                  void runStatusCheck({ deep: true });
                }
              }}
            >
              Deep Diagnostic
            </button>
          </div>
          {statusError ? <p className="codirector-status-error">{statusError}</p> : null}
        </div>
      </div>

      {summary ? (
        <div className="codirector-status-tallies">
          <div>
            <strong>{summary.healthyChecks}</strong>
            <span>Healthy</span>
          </div>
          <div>
            <strong>{summary.warningChecks}</strong>
            <span>Warnings</span>
          </div>
          <div>
            <strong>{summary.blockedChecks}</strong>
            <span>Blocked</span>
          </div>
        </div>
      ) : null}

      {(blockers.length || warnings.length || busyChecks.length) && (
        <div className="codirector-status-highlights">
          {!!blockers.length && (
            <section>
              <p className="eyebrow">Blockers</p>
              <ul className="activity-feed">
                {blockers.map((result) => (
                  <li key={result.checkId}>
                    <strong>{result.title}</strong>
                    <span>{result.summary}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {!!busyChecks.length && (
            <section>
              <p className="eyebrow">Busy</p>
              <ul className="activity-feed">
                {busyChecks.map((result) => (
                  <li key={result.checkId}>
                    <strong>{result.title}</strong>
                    <span>{result.summary}</span>
                    {result.lastHealthyAt ? (
                      <span className="muted">Last verified healthy: {new Date(result.lastHealthyAt).toLocaleString()}</span>
                    ) : null}
                  </li>
                ))}
              </ul>
            </section>
          )}
          {!!warnings.length && (
            <section>
              <p className="eyebrow">Warnings</p>
              <ul className="activity-feed">
                {warnings.map((result) => (
                  <li key={result.checkId}>
                    <strong>{result.title}</strong>
                    <span>{result.summary}</span>
                    {(result.timedOut || result.status === "timed_out") && (
                      <span className="muted">
                        Limit {result.timeoutMs ?? "?"}ms · awaited {result.awaitedDependency || "dependency"}
                        {result.lastHealthyAt
                          ? ` · last healthy ${new Date(result.lastHealthyAt).toLocaleString()}`
                          : ""}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}

      {!!allRecoveryActions.length && (
        <section>
          <p className="eyebrow">Recovery Options</p>
          <div className="row-actions codirector-status-actions">
            {allRecoveryActions.slice(0, 8).map((action) => (
              <button key={`${action.checkId}:${action.id}`} type="button" onClick={() => handleAction(action)}>
                {action.label}
              </button>
            ))}
          </div>
        </section>
      )}

      {!!statusLatestRun?.categories.length && (
        <section>
          <p className="eyebrow">Category Readiness</p>
          <div className="codirector-status-categories">
            {statusLatestRun.categories.map((category) => {
              // Domain-specific counter wording so unrelated concepts don't share one
              // denominator. Runtime checks use "healthy"; generator/model checks use
              // "ready"/"incomplete". Falls back to "healthy" for unknown categories.
              const catKey = String(category.category || "").toLowerCase();
              const isGenerators = catKey.includes("model") || catKey.includes("generator") || catKey.includes("video") || catKey.includes("image");
              const readyWord = isGenerators ? "ready" : "healthy";
              const incomplete = category.total - category.healthy;
              const counterLabel = isGenerators && incomplete > 0
                ? `${category.healthy}/${category.total} ready · ${incomplete} incomplete`
                : `${category.healthy}/${category.total} ${readyWord}`;
              return (
                <details key={category.category} className="codirector-status-category" open={category.blocked > 0}>
                  <summary>
                    <span>{category.label}</span>
                    <span className="muted">{counterLabel}</span>
                  </summary>
                  <ul className="activity-feed">
                    {statusLatestRun.results
                      .filter((result) => result.category === category.category)
                      .map((result) => (
                        <li key={result.checkId}>
                          <strong>{result.title}</strong>
                          <span>
                            {result.status.replace(/_/g, " ")} · {result.summary}
                          </span>
                          <details>
                            <summary>Technical Information</summary>
                            <pre className="explain-panel">{JSON.stringify(result.details, null, 2)}</pre>
                          </details>
                        </li>
                      ))}
                  </ul>
                </details>
              );
            })}
          </div>
        </section>
      )}

      {statusLatestRun?.explainability && (
        <section>
          <p className="eyebrow">Why this score?</p>
          <ul className="activity-feed">
            {statusLatestRun.explainability.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <div className="row-actions" style={{ justifyContent: "space-between" }}>
          <p className="eyebrow" style={{ marginBottom: 0 }}>
            Recent Checks
          </p>
          <button type="button" className="ghost" onClick={() => void loadStatus()}>
            Refresh
          </button>
        </div>
        <ul className="activity-feed">
          {!statusHistory.length && <li className="muted">No status checks yet.</li>}
          {statusHistory.slice(0, 6).map((run) => (
            <li key={run.runId}>
              <strong>{run.summary.statusIndicator}</strong>
              <span>
                {run.summary.score} · {new Date(run.completedAt).toLocaleString()}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
