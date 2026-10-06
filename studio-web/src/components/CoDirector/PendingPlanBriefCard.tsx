import type { PendingPlanBriefView } from "./pendingPlanBrief";
import { isPendingBriefFresh, summarizePendingRoute } from "./pendingPlanBrief";

/**
 * Ready / pending production plan brief — consumes deliberation_decision.pendingBrief.
 * Say Go binds only when fresh; stale pending must not bind Go.
 */
export function PendingPlanBriefCard({
  brief,
  busy,
  onSayGo,
  onEdit,
  onCancel,
}: {
  brief: PendingPlanBriefView;
  busy: boolean;
  onSayGo: () => void;
  onEdit: () => void;
  onCancel: () => void;
}) {
  const fresh = isPendingBriefFresh(brief);
  const route = summarizePendingRoute(brief);
  const steps = brief.productionPlan?.steps || [];
  const firstStep = steps[0];
  const goal = brief.productionPlan?.goal || brief.summary || "Production plan ready";
  const stepLabel =
    firstStep?.title ||
    firstStep?.goal ||
    firstStep?.capabilityId ||
    brief.stepId ||
    "Step 1";
  const preflight = brief.selectivePreflight;
  const showPreflight = Boolean(
    preflight && (preflight.required || preflight.strict || preflight.multiStep || preflight.expensive),
  );

  return (
    <div
      className={`codirector-cta-card codirector-pending-plan-brief${fresh ? "" : " is-stale"}`}
      role="group"
      aria-label={fresh ? "Plan ready for confirmation" : "Expired plan brief"}
      data-testid="codirector-pending-plan-brief"
      data-fresh={fresh ? "true" : "false"}
      data-plan-id={brief.planId || ""}
      data-brief-id={brief.briefId || ""}
    >
      <div className="codirector-pending-plan-brief__header">
        <strong>{fresh ? "Ready" : "Expired"}</strong>
        <span className="codirector-pending-plan-brief__badge">
          {brief.responsePurpose === "plan" ? "Plan" : "Pending"}
        </span>
      </div>
      <div className="codirector-pending-plan-brief__goal" data-testid="pending-plan-goal">
        {goal}
      </div>
      <div className="codirector-pending-plan-brief__meta">
        <div data-testid="pending-plan-step">
          <span className="muted">Step</span> {stepLabel}
        </div>
        {route ? (
          <div data-testid="pending-plan-route">
            <span className="muted">Route</span> {route}
          </div>
        ) : null}
        {steps.length > 1 ? (
          <div data-testid="pending-plan-steps-count">
            <span className="muted">Steps</span> {steps.length}
          </div>
        ) : null}
      </div>
      {showPreflight ? (
        <div
          className="codirector-pending-plan-brief__preflight"
          data-testid="pending-plan-selective-preflight"
        >
          <strong>Preflight</strong>
          <ul>
            {(preflight?.checks || []).map((c) => (
              <li key={c}>{c}</li>
            ))}
            {(preflight?.runtimeNeeds || []).map((r) => (
              <li key={`rt-${r}`}>runtime: {r}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {!fresh ? (
        <p className="codirector-pending-plan-brief__stale" data-testid="pending-plan-stale">
          This confirmation expired. Say Go will not run it — ask to rebuild the plan.
        </p>
      ) : null}
      <div className="codirector-pending-plan-brief__actions">
        <button
          type="button"
          className="primary"
          data-testid="pending-plan-say-go"
          disabled={busy || !fresh}
          onClick={onSayGo}
          title={fresh ? "Confirm and run the plan" : "Expired — Go is disabled"}
        >
          Say Go
        </button>
        <button
          type="button"
          className="ghost"
          data-testid="pending-plan-edit"
          disabled={busy}
          onClick={onEdit}
        >
          Edit
        </button>
        <button
          type="button"
          className="ghost"
          data-testid="pending-plan-cancel"
          disabled={busy}
          onClick={onCancel}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
