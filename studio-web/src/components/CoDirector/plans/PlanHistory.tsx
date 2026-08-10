import type { PlanEventRow, PlanVersionRow } from "./types";

export function PlanHistory({
  events,
  versions,
}: {
  events: PlanEventRow[];
  versions: PlanVersionRow[];
}) {
  return (
    <div className="codirector-plan-history" data-testid="codirector-plan-history">
      <h4>Versions</h4>
      {versions.length ? (
        <ul>
          {versions.map((v) => (
            <li key={v.version}>
              v{v.version} · {v.state || "?"}
              {v.revisionReason ? ` — ${v.revisionReason}` : ""}
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">No versions yet.</p>
      )}
      <h4>Events</h4>
      {events.length ? (
        <ul>
          {events.map((e, i) => (
            <li key={e.eventId || i}>
              {e.eventType} (v{e.planVersion}) — {e.summary || ""}
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">No events yet.</p>
      )}
    </div>
  );
}
