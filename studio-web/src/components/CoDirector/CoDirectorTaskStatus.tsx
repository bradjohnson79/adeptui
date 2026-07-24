import { getActionCost } from "./types";
import { useCoDirectorSession } from "./CoDirectorSession";

export function CoDirectorTaskStatus() {
  const { plan, selectedSteps, setSelectedStep, runSteps, busy, dismissPlan } = useCoDirectorSession();

  if (!plan) return null;

  const total = plan.steps.length;
  const done = plan.steps.filter((s) => s.status === "done").length;
  const running = plan.steps.some((s) => s.status === "running");

  return (
    <section className="codirector-task" aria-live="polite">
      <div className="codirector-task-head">
        <div>
          <strong>{plan.title}</strong>
          <p className="muted">
            {running ? "Working…" : done === total ? "Complete" : `${done} of ${total} complete`}
          </p>
        </div>
        <button type="button" className="ghost" onClick={() => dismissPlan()}>
          Dismiss
        </button>
      </div>
      <ul className="codirector-plan-steps">
        {plan.steps.map((s) => (
          <li key={s.id} className={s.status === "done" ? "done" : s.status === "checkpoint" ? "checkpoint" : ""}>
            <input
              type="checkbox"
              checked={!!selectedSteps[s.id]}
              onChange={(e) => setSelectedStep(s.id, e.target.checked)}
              aria-label={`Select ${s.label}`}
            />
            <div>
              <div>
                {s.label}{" "}
                <span className="scene-meta">
                  [{s.status}] {getActionCost(s.actionId)}
                </span>
              </div>
              {s.checkpointMessage && <p className="muted">{s.checkpointMessage}</p>}
              {s.error && <p className="muted">{s.error}</p>}
              {s.reuseAssets && s.reuseAssets.length > 0 && (
                <p className="scene-meta">Reuse: {s.reuseAssets.map((a) => a.tag).join(", ")}</p>
              )}
            </div>
          </li>
        ))}
      </ul>
      <div className="codirector-task-actions">
        <button
          type="button"
          className="primary"
          disabled={busy}
          onClick={() =>
            void runSteps(plan.steps.filter((s) => s.status === "pending" || s.status === "checkpoint"))
          }
        >
          Approve all
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() =>
            void runSteps(
              plan.steps.filter(
                (s) => selectedSteps[s.id] && (s.status === "pending" || s.status === "checkpoint"),
              ),
            )
          }
        >
          Run selected
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => {
            const next = plan.steps.find((s) => s.status === "pending" || s.status === "checkpoint");
            if (next) void runSteps([next]);
          }}
        >
          Run one
        </button>
      </div>
    </section>
  );
}
