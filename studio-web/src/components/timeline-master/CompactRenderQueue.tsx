import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../api";
import { loadDismissedRenderJobIds, saveDismissedRenderJobIds } from "../../renderQueueDismiss";
import { formatElapsedClock } from "../../timelineMaster/sceneRenderProgress";
import { useProjectJobs } from "../../runtime/projectJobsStore";

const ACTIVE_STATUSES = new Set(["queued", "running", "pending", "in_progress", "processing", "cancelling", "canceling"]);
const TERMINAL_STATUSES = new Set(["done", "complete", "completed", "failed", "error", "cancelled", "canceled"]);

function isActive(status: string) {
  return ACTIVE_STATUSES.has(status.trim().toLowerCase());
}

function isTerminal(status: string) {
  return TERMINAL_STATUSES.has(status.trim().toLowerCase());
}

function lastActivityLabel(iso?: string | null): string {
  if (!iso) return "";
  const stamp = Date.parse(iso);
  if (!Number.isFinite(stamp)) return "";
  const sec = Math.max(0, (Date.now() - stamp) / 1000);
  if (sec < 60) return `${Math.max(1, Math.round(sec))} seconds ago`;
  return `${Math.max(1, Math.round(sec / 60))} minutes ago`;
}

export function CompactRenderQueue({
  projectId,
  sceneId,
  onChange,
}: {
  projectId: string;
  sceneId?: string;
  onChange: () => void | Promise<void>;
}) {
  const { t } = useTranslation("timeline");
  const { jobs: projectJobs } = useProjectJobs(projectId);
  const jobs = useMemo(
    () => (sceneId ? projectJobs.filter((job) => !job.scene_id || job.scene_id === sceneId) : projectJobs),
    [projectJobs, sceneId],
  );
  const [expanded, setExpanded] = useState(false);
  const [batchLabels, setBatchLabels] = useState<Record<string, string>>({});
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(() => loadDismissedRenderJobIds(projectId));

  useEffect(() => {
    setDismissedIds(loadDismissedRenderJobIds(projectId));
  }, [projectId]);

  useEffect(() => {
    let alive = true;
    if (!sceneId) return;
    void api
      .directorTimelineMaster(projectId, sceneId)
      .then((data) => {
        if (!alive) return;
        const map: Record<string, string> = {};
        for (const b of data.master.batchBlocks || []) map[b.id] = b.label;
        setBatchLabels(map);
      })
      .catch(() => {
        /* labels are a nicety; ids remain as fallback */
      });
    return () => {
      alive = false;
    };
  }, [projectId, sceneId, jobs.length]);

  const visibleJobs = useMemo(
    () =>
      jobs.filter((job) => {
        if (isActive(job.status)) return true;
        if (!isTerminal(job.status)) return true;
        return !dismissedIds.has(job.id);
      }),
    [dismissedIds, jobs],
  );
  const active = useMemo(() => visibleJobs.filter((job) => isActive(job.status)).length, [visibleJobs]);
  const complete = useMemo(() => visibleJobs.filter((job) => TERMINAL_STATUSES.has(job.status) && job.status !== "failed" && job.status !== "error").length, [visibleJobs]);
  const clearableCount = useMemo(
    () => jobs.filter((job) => isTerminal(job.status) && !isActive(job.status) && !dismissedIds.has(job.id)).length,
    [dismissedIds, jobs],
  );

  const clearFinished = () => {
    const next = new Set(dismissedIds);
    for (const job of jobs) {
      if (isTerminal(job.status) && !isActive(job.status)) next.add(job.id);
    }
    setDismissedIds(next);
    saveDismissedRenderJobIds(projectId, next);
  };

  return (
    <section className="timeline-render-queue panel" data-testid="timeline-render-queue">
      <div className="timeline-render-queue__header">
        <button
          type="button"
          className="timeline-render-queue__toggle"
          onClick={() => setExpanded((value) => !value)}
          aria-expanded={expanded}
        >
          <strong>Render Queue</strong>
          <span>
            {active} active · {complete} complete
          </span>
        </button>
        <button
          type="button"
          className="ghost"
          data-testid="timeline-render-queue-clear"
          disabled={clearableCount === 0}
          title={t("clearQueueTitle")}
          aria-label={t("clearQueueTitle")}
          onClick={(event) => {
            event.stopPropagation();
            clearFinished();
          }}
        >
          {t("clearQueue")}
        </button>
      </div>
      {expanded ? (
        <div className="timeline-render-queue__body">
          {visibleJobs.length === 0 ? (
            <p className="scene-meta">No render jobs yet.</p>
          ) : (
            visibleJobs.slice(0, 8).map((job) => {
              const busy = isActive(job.status);
              let batchBlockId: string | null = null;
              try {
                const p = job.params_json ? JSON.parse(job.params_json) : null;
                if (p && typeof p.batchBlockId === "string") batchBlockId = p.batchBlockId;
              } catch {
                /* ignore */
              }
              return (
                <div key={job.id} className="timeline-render-queue__job">
                  <div>
                    <strong>{job.kind}</strong>
                    {batchBlockId && (
                      <span className="scene-meta" title={`Batch ${batchBlockId}`}>
                        {" · "}
                        {batchLabels[batchBlockId] || `batch ${batchBlockId.slice(0, 10)}`}
                      </span>
                    )}
                    <div className="scene-meta" data-testid={`timeline-queue-job-status-${job.id}`}>
                      {job.generation_stalled
                        ? "Generation may be stalled"
                        : job.phase === "sampling"
                          ? "Generating — Sampling"
                          : job.phase_label || job.stage || job.status}
                      {job.progress_grounded && Number(job.progress) > 0
                        ? ` · ${Math.round((Number(job.progress) <= 1 ? Number(job.progress) * 100 : Number(job.progress)))}%`
                        : ""}
                      {job.elapsed_active_time != null && Number.isFinite(Number(job.elapsed_active_time))
                        ? ` · Elapsed ${formatElapsedClock(job.elapsed_active_time)}`
                        : ""}
                      {job.generation_stalled
                        ? job.last_runtime_event_at
                          ? ` · Last runtime event: ${lastActivityLabel(job.last_runtime_event_at)}`
                          : ""
                        : isActive(job.status)
                          ? ` · Runtime active${
                              job.last_runtime_event_at
                                ? ` · Last runtime event: ${lastActivityLabel(job.last_runtime_event_at)}`
                                : ""
                            }`
                          : job.message && !job.phase_label
                            ? ` · ${job.message}`
                            : ""}
                    </div>
                  </div>
                  {busy ? (
                    <button
                      type="button"
                      className="ghost"
                      onClick={() => {
                        void api.cancelJob(job.id).then(() => {
                          void onChange();
                        });
                      }}
                    >
                      Cancel
                    </button>
                  ) : null}
                </div>
              );
            })
          )}
        </div>
      ) : null}
    </section>
  );
}
