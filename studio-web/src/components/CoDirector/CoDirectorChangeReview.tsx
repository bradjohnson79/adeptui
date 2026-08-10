import { useState } from "react";
import { useCoDirectorSession } from "./CoDirectorSession";

/**
 * Compact Change Review / What Changed — exploratory advisory OR documentation updates.
 * Creator-safe; no chain-of-thought.
 */
export function CoDirectorChangeReview() {
  const { activity } = useCoDirectorSession();
  const [dismissed, setDismissed] = useState(false);
  if (!activity || dismissed) return null;

  const whatChanged = activity.whatChanged || [];
  const substantial =
    whatChanged.length > 0 ||
    Boolean(activity.waitingForConfirmation) ||
    Number(activity.wikiCandidates || 0) > 0 ||
    Number(activity.confirmedWrites || 0) > 0 ||
    Boolean(activity.documentationReason) ||
    String(activity.changeStatus || "").toUpperCase().includes("EXPLOR") ||
    String(activity.advisoryStrength || "").includes("FOUNDATIONAL") ||
    String(activity.advisoryStrength || "").includes("STRONG");
  if (!substantial) return null;

  return (
    <section
      className="codirector-content-card"
      data-testid="codirector-change-review"
      aria-label="Project updated"
      style={{ marginTop: "0.75rem" }}
    >
      <p className="eyebrow">Project updated</p>
      {whatChanged.length ? (
        <ul data-testid="codirector-what-changed" style={{ margin: "0.35rem 0", paddingLeft: "1.1rem" }}>
          {whatChanged.map((line) => (
            <li key={line} className="muted">
              {line}
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted" data-testid="codirector-change-review-status">
          Status: {activity.changeStatus || "Under review"}
          {activity.advisoryStrength ? ` · ${activity.advisoryStrength}` : ""}
        </p>
      )}
      {activity.documentationReason && activity.documentationReason !== "OK" ? (
        <p className="muted" data-testid="codirector-documentation-reason">
          Documentation note: {activity.documentationReason}
        </p>
      ) : null}
      {activity.activeGoal ? (
        <p className="muted" data-testid="codirector-change-review-goal">
          Purpose in focus: {activity.activeGoal}
        </p>
      ) : null}
      <p className="muted">
        {activity.waitingForConfirmation
          ? "Co-Director is waiting for your confirmation before treating this as project canon."
          : "You can keep explaining, or review what was documented."}
      </p>
      <p className="muted" data-testid="codirector-change-review-canon">
        Canon updated: {activity.canonUpdated ? "Yes" : "No"}
      </p>
      <button
        type="button"
        className="button ghost"
        data-testid="codirector-what-changed-dismiss"
        onClick={() => setDismissed(true)}
      >
        Dismiss
      </button>
    </section>
  );
}
