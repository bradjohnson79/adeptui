import { useEffect, useRef } from "react";
import { StatusBadge } from "../ui";
import type { ProductionDockApi } from "./useProductionDock";
import { QueueDrawer } from "./QueueDrawer";

export function DiagnosticsDrawer({
  open,
  dock,
  onClose,
  onOpenQueue,
}: {
  open: boolean;
  dock: ProductionDockApi;
  onClose: () => void;
  onOpenQueue: () => void;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const rows = dock.status?.healthRows ?? [];
  const summary = dock.queue;

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

  return (
    <div
      ref={panelRef}
      className="production-dock-drawer"
      role="dialog"
      aria-modal="true"
      aria-label="System diagnostics"
      tabIndex={-1}
      data-testid="production-dock-diagnostics"
    >
      <div className="production-dock-drawer__header">
        <h3>Diagnostics</h3>
        <button type="button" className="production-dock-collapse-btn" aria-label="Close diagnostics" onClick={onClose}>
          ×
        </button>
      </div>
      <ul className="production-dock-health-list">
        {rows.length === 0 ? (
          <>
            <li className="production-dock-health-row">
              <span>GPU Queue</span>
              <StatusBadge kind={summary?.gpuQueued ? "NeedsAttention" : "Ready"} label={String(summary?.gpuQueued ?? 0)} compact />
            </li>
            <li className="production-dock-health-row">
              <span>Hosted Jobs</span>
              <StatusBadge kind={summary?.hostedQueued ? "NeedsAttention" : "Ready"} label={String(summary?.hostedQueued ?? 0)} compact />
            </li>
            <li className="production-dock-health-row">
              <span>Active</span>
              <StatusBadge kind={summary?.active ? "InProgress" : "Ready"} label={String(summary?.active ?? 0)} compact />
            </li>
          </>
        ) : (
          rows.map((row) => (
            <li key={row.id} className="production-dock-health-row">
              <span>{row.label}</span>
              <StatusBadge kind="Ready" label={String(row.status)} compact title={row.detail ?? undefined} />
            </li>
          ))
        )}
      </ul>
      <button
        type="button"
        className="production-dock-chip"
        aria-label="Open job queue"
        style={{ marginTop: "0.65rem" }}
        onClick={onOpenQueue}
      >
        Open Queue
      </button>
      {dock.openMenu === "queue" ? (
        <QueueDrawer open dock={dock} onClose={() => dock.setOpenMenu("diagnostics")} embedded />
      ) : null}
    </div>
  );
}
