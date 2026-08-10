import { useEffect, useMemo, useState } from "react";
import { api } from "../../api";
import type { Job } from "../../types";

const ACTIVE_STATUSES = new Set(["queued", "running", "pending"]);
const COMPLETE_STATUSES = new Set(["done", "completed"]);

export function CompactRenderQueue({
  projectId,
  sceneId,
  onChange,
}: {
  projectId: string;
  sceneId?: string;
  onChange: () => void | Promise<void>;
}) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [expanded, setExpanded] = useState(false);
  const [batchLabels, setBatchLabels] = useState<Record<string, string>>({});

  useEffect(() => {
    let alive = true;
    const load = async () => {
      if (document.visibilityState === "hidden") return;
      const list = await api.listJobs(projectId);
      if (!alive) return;
      setJobs(sceneId ? list.filter((job) => !job.scene_id || job.scene_id === sceneId) : list);
    };
    void load();
    const timer = window.setInterval(() => void load(), 3000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, [projectId, sceneId]);

  // Batch id → label lookup so the queue shows creator-facing batch names
  // instead of truncated internal ids (Creator-First UI).
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

  const active = useMemo(() => jobs.filter((job) => ACTIVE_STATUSES.has(job.status)).length, [jobs]);
  const complete = useMemo(() => jobs.filter((job) => COMPLETE_STATUSES.has(job.status)).length, [jobs]);

  return (
    <section className="timeline-render-queue panel" data-testid="timeline-render-queue">
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
      {expanded ? (
        <div className="timeline-render-queue__body">
          {jobs.length === 0 ? (
            <p className="scene-meta">No render jobs yet.</p>
          ) : (
            jobs.slice(0, 8).map((job) => {
              const busy = ACTIVE_STATUSES.has(job.status);
              // RENDER_QUEUE_BATCH_LINKAGE: surface batchBlockId from job
              // params so creators can see which batch a render belongs to.
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
                    <div className="scene-meta">
                      {job.status} {job.message ? `· ${job.message}` : ""}
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
