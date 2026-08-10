import { useEffect, useMemo, useState } from "react";
import { Button } from "../ui";
import { shouldShowActivity } from "./activity";
import { useCoDirectorSession } from "./CoDirectorSession";
import { intelligenceStageLabel } from "./types";

const STAGE_ICON: Record<string, string> = {
  pending: "○",
  active: "◔",
  completed: "●",
  failed: "✕",
};

export function CoDirectorActivityPanel() {
  const {
    activity,
    activityPreference,
    intelligenceProgress,
    retryActivityPersistence,
  } = useCoDirectorSession();
  const [view, setView] = useState<"stages" | "summary" | null>("stages");
  const [continuedAfterFailure, setContinuedAfterFailure] = useState(false);

  useEffect(() => {
    setView(activity?.status === "running" ? "stages" : null);
    setContinuedAfterFailure(false);
  }, [activity?.requestId, activity?.status]);

  const visible = shouldShowActivity(activity, activityPreference);
  const failedPersistence = Boolean(activity?.persistenceError);
  const showFailureActions = failedPersistence && !continuedAfterFailure;
  const summaryFacts = useMemo(() => activity?.summaryFacts || [], [activity?.summaryFacts]);
  const progressLabel =
    activity?.status === "running" && intelligenceProgress
      ? intelligenceStageLabel(intelligenceProgress.stage) || intelligenceProgress.message
      : null;

  if (!visible || !activity) return null;

  return (
    <section
      className="codirector-activity-card"
      data-testid="codirector-activity-panel"
      aria-label="Co-Director activity"
    >
      <div className="codirector-activity-header">
        <div>
          <p className="eyebrow" aria-live="polite">
            {activity.status === "running" ? "Co-Director is working…" : "Co-Director activity"}
          </p>
          {progressLabel ? (
            <p className="muted codirector-activity-caption" data-testid="codirector-activity-progress">
              {progressLabel}
            </p>
          ) : null}
          {activity.status !== "running" && summaryFacts.length > 0 ? (
            <p className="muted codirector-activity-caption">
              {activity.persistenceError
                ? "The response finished, but saving this conversation did not."
                : "Here’s what Co-Director was doing for this reply."}
            </p>
          ) : null}
        </div>
        {activity.status !== "running" ? (
          <div className="row">
            <Button variant="ghost" compact onClick={() => setView(view === "stages" ? null : "stages")}>
              View activity
            </Button>
            <Button
              variant="ghost"
              compact
              onClick={() => setView(view === "summary" ? null : "summary")}
            >
              What Co-Director considered
            </Button>
          </div>
        ) : null}
      </div>

      {(activity.cognitiveMode || activity.activeGoal || activity.creativePosture) && (
        <div
          className="codirector-activity-focus"
          data-testid="codirector-activity-focus"
          style={{ marginBottom: "0.75rem" }}
        >
          {activity.cognitiveMode ? (
            <p className="muted" data-testid="codirector-activity-mode">
              Mode: <strong>{activity.cognitiveMode}</strong>
              {activity.workflowHold ? " · Holding production steps" : ""}
            </p>
          ) : null}
          {activity.activeGoal ? (
            <p className="muted" data-testid="codirector-activity-goal">
              Current goal: {activity.activeGoal}
            </p>
          ) : null}
          {activity.creativePosture ? (
            <p className="muted" data-testid="codirector-activity-posture">
              Support posture: {activity.creativePosture}
            </p>
          ) : null}
          {activity.changeStatus ? (
            <p className="muted" data-testid="codirector-activity-change-status">
              Change status: {activity.changeStatus}
              {activity.advisoryStrength ? ` · Advisory: ${activity.advisoryStrength}` : ""}
            </p>
          ) : null}
          {activity.waitingForConfirmation ? (
            <p className="muted" data-testid="codirector-activity-waiting-confirm">
              Waiting for confirmation before changing project records.
            </p>
          ) : null}
          {activity.roleEmphasis ? (
            <p className="muted" data-testid="codirector-activity-role">
              Role emphasis: {activity.roleEmphasis}
            </p>
          ) : null}
          {activity.creativeStage ? (
            <p className="muted" data-testid="codirector-activity-creative-stage">
              Creative posture: {activity.creativeStage}
              {typeof activity.wikiCandidates === "number" ? ` · Wiki candidates: ${activity.wikiCandidates}` : ""}
              {typeof activity.confirmedWrites === "number" ? ` · Confirmed writes: ${activity.confirmedWrites}` : ""}
            </p>
          ) : null}
          {typeof activity.discoveryQuestionCount === "number" ? (
            <p className="muted" data-testid="codirector-activity-discovery-q">
              Discovery questions: {activity.discoveryQuestionCount}
              {activity.researchStatus ? ` · Research: ${activity.researchStatus}` : ""}
            </p>
          ) : null}
          <p className="muted" data-testid="codirector-activity-tools">
            Tools: {activity.toolsSummary || (activity.toolLabels.length ? activity.toolLabels.join(", ") : "None this turn")}
            {activity.canonUpdated ? " · Canon updated" : " · Canon updated: No"}
          </p>
          {activity.memorySummary ? (
            <p className="muted" data-testid="codirector-activity-memory">
              Memory: {activity.memorySummary}
            </p>
          ) : null}
        </div>
      )}

      {(activity.status === "running" || view === "stages") && (
        <ol className="codirector-activity-list">
          {activity.stages.map((stageItem) => (
            <li
              key={stageItem.id}
              className={`codirector-activity-stage is-${stageItem.status}`}
              data-status={stageItem.status}
            >
              <span className="codirector-activity-indicator" aria-hidden>
                {STAGE_ICON[stageItem.status]}
              </span>
              <span className="codirector-activity-copy">
                <strong>{stageItem.label}</strong>
                {stageItem.detail ? <span className="muted"> {stageItem.detail}</span> : null}
              </span>
            </li>
          ))}
        </ol>
      )}

      {activity.status !== "running" && view === "summary" && (
        <div className="codirector-activity-summary" data-testid="codirector-activity-summary">
          <p className="eyebrow">What Co-Director considered</p>
          {summaryFacts.length ? (
            <ul>
              {summaryFacts.map((fact) => (
                <li key={fact}>{fact}</li>
              ))}
            </ul>
          ) : (
            <p className="muted">
              Co-Director responded from the current conversation without changing project records.
            </p>
          )}
          {activity.actualModel ? (
            <p className="muted" data-testid="codirector-activity-model">
              Model: {activity.actualModel}
              {activity.fallbackUsed ? " · Used a safe fallback reply" : ""}
            </p>
          ) : null}
        </div>
      )}

      {showFailureActions && (
        <div className="codirector-activity-failure" role="alert" aria-live="polite">
          <p>{activity.persistenceError}</p>
          <div className="row">
            <Button variant="primary" compact onClick={() => void retryActivityPersistence()}>
              Retry
            </Button>
            <Button variant="ghost" compact onClick={() => setContinuedAfterFailure(true)}>
              Continue
            </Button>
          </div>
        </div>
      )}
    </section>
  );
}
