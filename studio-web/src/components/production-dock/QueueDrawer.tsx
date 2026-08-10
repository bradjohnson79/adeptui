import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api";
import { Button, StatusBadge } from "../ui";
import type { ProductionDockApi } from "./useProductionDock";

export function QueueDrawer({
  open,
  dock,
  onClose,
  embedded = false,
}: {
  open: boolean;
  dock: ProductionDockApi;
  onClose: () => void;
  embedded?: boolean;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const jobs = dock.queue?.jobs ?? [];

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    panelRef.current?.focus();
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  const content = (
    <>
      {!embedded ? (
        <div className="production-dock-drawer__header">
          <h3>Queue</h3>
          <button type="button" className="production-dock-collapse-btn" aria-label="Close queue" onClick={onClose}>
            ×
          </button>
        </div>
      ) : null}
      {jobs.length === 0 ? (
        <p className="production-dock-muted">No active jobs in the queue.</p>
      ) : (
        <ul className="production-dock-queue-list">
          {jobs.map((job) => (
            <li key={job.id} className="production-dock-queue-row">
              <div>
                <strong>{job.label}</strong>
                <div className="production-dock-muted">{job.status}</div>
              </div>
              <div className="production-dock-queue-row__actions">
                <StatusBadge kind="InProgress" label={job.kind || "job"} compact />
                {job.cancellable !== false ? (
                  <Button
                    variant="compact"
                    aria-label={`Cancel job ${job.label}`}
                    onClick={() => void api.cancelJob(job.id).then(() => dock.refresh())}
                  >
                    Cancel
                  </Button>
                ) : null}
                {job.retryable ? (
                  <Button variant="compact" aria-label={`Retry job ${job.label}`} disabled title="Retry when available">
                    Retry
                  </Button>
                ) : null}
                {job.projectId ? (
                  <Button
                    variant="compact"
                    aria-label={`Open workspace for ${job.label}`}
                    onClick={() => {
                      navigate(job.workspaceRoute || `/project/${job.projectId}?workspace=home`);
                      onClose();
                    }}
                  >
                    Open
                  </Button>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      )}
    </>
  );

  if (embedded) {
    return (
      <div className="production-dock-drawer" style={{ position: "static", transform: "none", width: "100%", marginTop: "0.65rem" }}>
        {content}
      </div>
    );
  }

  return (
    <div
      ref={panelRef}
      className="production-dock-drawer"
      role="dialog"
      aria-modal="true"
      aria-label="Production queue"
      tabIndex={-1}
      data-testid="production-dock-queue"
    >
      {content}
    </div>
  );
}
