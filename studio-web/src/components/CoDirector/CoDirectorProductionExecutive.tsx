import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../../api";

type TabId = "queue" | "running" | "blocked" | "history" | "notifications" | "providers" | "statistics";

type Job = {
  id: string;
  type: string;
  status: string;
  priority: number;
  sceneId?: string | null;
  provider?: string | null;
  blockedReason?: string | null;
  attemptsCount?: number;
  errorMessage?: string | null;
  createdAt?: string;
  updatedAt?: string;
};

type Notification = {
  id: string;
  level: string;
  title: string;
  body: string;
  read: boolean;
  createdAt: string;
  jobId?: string | null;
};

type SceneProgress = {
  sceneId: string;
  totalJobs: number;
  completed: number;
  failed: number;
  blocked: number;
  running: number;
  queued: number;
  needsReview: number;
  percentComplete: number;
  derivedFromJobs: boolean;
};

const TABS: { id: TabId; label: string }[] = [
  { id: "queue", label: "Queue" },
  { id: "running", label: "Running" },
  { id: "blocked", label: "Blocked" },
  { id: "history", label: "History" },
  { id: "notifications", label: "Notifications" },
  { id: "providers", label: "Providers" },
  { id: "statistics", label: "Statistics" },
];

function statusBucket(tab: TabId, status: string): boolean {
  if (tab === "queue") return ["Queued", "Waiting", "Retrying", "Paused", "NeedsReview"].includes(status);
  if (tab === "running") return status === "Running";
  if (tab === "blocked") return status === "Blocked";
  if (tab === "history") return ["Completed", "Failed", "Cancelled"].includes(status);
  return true;
}

export function CoDirectorProductionExecutive({
  projectId,
  enabled,
  sceneId,
}: {
  projectId: string;
  enabled: boolean;
  sceneId?: string;
}) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<TabId>("queue");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [stats, setStats] = useState<Record<string, unknown> | null>(null);
  const [progress, setProgress] = useState<SceneProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    if (!enabled || !projectId) return;
    setError(null);
    try {
      const [jobRes, noteRes, statRes] = await Promise.all([
        api.productionJobsList(projectId),
        api.productionNotifications(projectId),
        api.productionStatistics(projectId),
      ]);
      setJobs((jobRes.jobs || []) as Job[]);
      setNotifications((noteRes.notifications || []) as Notification[]);
      setStats(statRes);
      if (sceneId) {
        setProgress((await api.productionSceneProgress(projectId, sceneId)) as SceneProgress);
      } else {
        setProgress(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Production Executive");
    }
  }, [enabled, projectId, sceneId]);

  useEffect(() => {
    if (!enabled || !open) return;
    void refresh();
    const id = window.setInterval(() => void refresh(), 4000);
    return () => window.clearInterval(id);
  }, [enabled, open, refresh]);

  const visibleJobs = useMemo(
    () => jobs.filter((j) => statusBucket(tab, j.status)),
    [jobs, tab],
  );

  const act = async (action: "pause" | "resume" | "retry" | "cancel", jobId: string) => {
    setBusy(true);
    setError(null);
    try {
      if (action === "pause") await api.productionJobPause(jobId);
      if (action === "resume") await api.productionJobResume(jobId);
      if (action === "retry") await api.productionJobRetry(jobId);
      if (action === "cancel") await api.productionJobCancel(jobId);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusy(false);
    }
  };

  const startClosedLoop = async () => {
    if (!sceneId) {
      setError("Select a scene to start the closed-loop orchestration.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.productionClosedLoop({
        projectId,
        sceneId,
        provider: "mock",
        idempotencyKey: `ui-loop-${sceneId}`,
      });
      await api.productionWorkerDrain(80);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Closed loop failed");
    } finally {
      setBusy(false);
    }
  };

  if (!enabled) return null;

  return (
    <div className="codirector-executive" data-testid="codirector-production-executive">
      <div className="codirector-executive-header">
        <div>
          <p className="scene-meta">Production Executive</p>
          <p className="muted">Orchestrates jobs — never auto-approves canon.</p>
        </div>
        <button
          type="button"
          className="ghost"
          data-testid="toggle-production-executive"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? "Hide" : "Open"} dashboard
        </button>
      </div>

      {open && (
        <div className="codirector-executive-body" data-testid="production-executive-dashboard">
          {progress && (
            <div className="codirector-executive-progress" data-testid="scene-progress-derived">
              <p className="scene-meta">Scene progress (derived from jobs)</p>
              <p>
                {progress.percentComplete}% · {progress.completed}/{progress.totalJobs} completed
                {progress.needsReview ? ` · ${progress.needsReview} needs review` : ""}
                {progress.blocked ? ` · ${progress.blocked} blocked` : ""}
              </p>
              <div className="codirector-executive-bar">
                <span style={{ width: `${Math.min(100, progress.percentComplete)}%` }} />
              </div>
            </div>
          )}

          <div className="codirector-executive-tabs" role="tablist">
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                role="tab"
                aria-selected={tab === t.id}
                className={tab === t.id ? "active" : ""}
                data-testid={`executive-tab-${t.id}`}
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>

          <div className="row-actions">
            <button type="button" className="ghost" disabled={busy} onClick={() => void refresh()}>
              Refresh
            </button>
            <button
              type="button"
              className="primary"
              data-testid="executive-start-closed-loop"
              disabled={busy || !sceneId}
              onClick={() => void startClosedLoop()}
            >
              Queue closed loop (mock)
            </button>
          </div>

          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}

          {tab === "notifications" && (
            <ul className="codirector-executive-list" data-testid="executive-notifications">
              {notifications.length === 0 && <li className="muted">No notifications</li>}
              {notifications.map((n) => (
                <li key={n.id}>
                  <strong>{n.title}</strong>
                  <span className="muted"> · {n.level}</span>
                  <p>{n.body}</p>
                </li>
              ))}
            </ul>
          )}

          {tab === "statistics" && (
            <pre className="codirector-executive-stats" data-testid="executive-statistics">
              {JSON.stringify(stats, null, 2)}
            </pre>
          )}

          {tab === "providers" && (
            <div data-testid="executive-providers">
              <p className="muted">
                Providers are scheduled via Capability Bridge. Unavailable capabilities block jobs honestly —
                they are never silently skipped.
              </p>
              <ul className="codirector-executive-list">
                {jobs
                  .filter((j) => j.provider || j.blockedReason)
                  .slice(0, 20)
                  .map((j) => (
                    <li key={j.id}>
                      <code>{j.type}</code> · {j.provider || "—"} · {j.status}
                      {j.blockedReason ? <p className="muted">{j.blockedReason}</p> : null}
                    </li>
                  ))}
              </ul>
            </div>
          )}

          {!["notifications", "statistics", "providers"].includes(tab) && (
            <ul className="codirector-executive-list" data-testid={`executive-jobs-${tab}`}>
              {visibleJobs.length === 0 && <li className="muted">No jobs in this view</li>}
              {visibleJobs.map((j) => (
                <li key={j.id} data-testid={`executive-job-${j.id}`}>
                  <div className="codirector-executive-job-row">
                    <div>
                      <strong>{j.type}</strong>
                      <span className="muted"> · {j.status} · p{j.priority}</span>
                      {j.errorMessage && <p className="muted">{j.errorMessage}</p>}
                      {j.blockedReason && <p className="muted">{j.blockedReason}</p>}
                    </div>
                    <div className="row-actions">
                      {["Queued", "Waiting", "Running", "Retrying"].includes(j.status) && (
                        <button type="button" className="ghost" disabled={busy} onClick={() => void act("pause", j.id)}>
                          Pause
                        </button>
                      )}
                      {j.status === "Paused" && (
                        <button type="button" className="ghost" disabled={busy} onClick={() => void act("resume", j.id)}>
                          Resume
                        </button>
                      )}
                      {["Failed", "Blocked", "Cancelled"].includes(j.status) && (
                        <button type="button" className="ghost" disabled={busy} onClick={() => void act("retry", j.id)}>
                          Retry
                        </button>
                      )}
                      {!["Completed", "Cancelled"].includes(j.status) && (
                        <button type="button" className="ghost" disabled={busy} onClick={() => void act("cancel", j.id)}>
                          Cancel
                        </button>
                      )}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}