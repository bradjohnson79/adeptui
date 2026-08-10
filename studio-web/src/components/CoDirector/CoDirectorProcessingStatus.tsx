import { useEffect, useState } from "react";
import { Button } from "../ui";
import { api } from "../../api";
import { useCoDirectorSession } from "./CoDirectorSession";

const STAGE_LABELS: Record<string, string> = {
  RECEIVED: "Received your message",
  RECEIVING: "Request received",
  CLASSIFYING_INTENT: "Preferences and intent loaded…",
  UNDERSTANDING: "Understanding your idea…",
  READING_PROJECT_CACHE: "Relevant project context ready…",
  ASSEMBLING_PROMPT: "Gathering what I need…",
  LOADING_MODEL: "Loading the selected model…",
  WAITING_FOR_MODEL: "Waiting for selected model…",
  STREAMING_RESPONSE: "Responding…",
  PERSIST_CONVERSATION: "Saving conversation…",
  INTRIGUE_ANALYSIS: "Noticing what stands out…",
  FACT_EXTRACTION: "Identifying important project details…",
  WIKI_UPDATE: "Updating the Project Wiki…",
  UPDATING_WIKI: "Updating project notes in the background…",
  VISION_ANALYSIS: "Considering the larger vision…",
  ARTIFACT_READINESS: "Checking what we can prepare…",
  DRAFTING: "Preparing a draft…",
  RESEARCHING: "Researching creative references…",
  DISCOVERY_FORM: "Preparing discovery questions…",
  PITCH_BUILDING: "Drafting a pitch…",
  MARKETING_ANALYSIS: "Considering launch options…",
  RESPONSE_GENERATION: "Preparing a response…",
  GROUNDING: "Checking the reply…",
  COMPLETE: "Done",
};

/** Real processing stages from SSE — never fake percentages. Visible while busy. */
export function CoDirectorProcessingStatus() {
  const { activity, busy, cancelSend, uiContext } = useCoDirectorSession();
  const stages = activity?.processingStages || [];
  const wikiStatus = activity?.wikiBackgroundStatus;
  const coldLoad = Boolean(activity?.coldLoadActive) || stages.includes("LOADING_MODEL");
  const [elapsedSec, setElapsedSec] = useState(0);
  const [continueWaiting, setContinueWaiting] = useState(false);
  const [diagNote, setDiagNote] = useState<string | null>(null);

  useEffect(() => {
    if (!busy || !activity?.startedAt) {
      setElapsedSec(0);
      return;
    }
    const started = Date.parse(activity.startedAt);
    const tick = () => setElapsedSec(Math.max(0, Math.floor((Date.now() - started) / 1000)));
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, [busy, activity?.startedAt, activity?.requestId]);

  if (!busy && !stages.length && !wikiStatus) return null;
  const active = stages[stages.length - 1] || "RECEIVING";
  const hasTokens =
    stages.includes("STREAMING_RESPONSE") || stages.includes("GROUNDING") || stages.includes("COMPLETE");
  const label = busy
    ? coldLoad && !hasTokens
      ? STAGE_LABELS.LOADING_MODEL
      : STAGE_LABELS[active] || "Co-Director is thinking…"
    : "Ready";

  const delayHint =
    busy && !hasTokens && coldLoad
      ? "The first response after an idle period may take longer."
      : busy && !hasTokens && elapsedSec >= 20
        ? "This is taking longer than usual. You can keep waiting or cancel and try again."
        : busy && !hasTokens && elapsedSec >= 8
          ? "Still working on the first words…"
          : null;

  const runDiagnostic = async () => {
    const projectId = uiContext.projectId;
    if (!projectId) {
      setDiagNote("Select a project to run a diagnostic.");
      return;
    }
    try {
      await api.codirectorStatusCheck({ projectId });
      setDiagNote("Diagnostic started — chat stays available.");
    } catch {
      try {
        await api.codirectorStatusRegistry();
        setDiagNote("Status registry reachable — model was not changed.");
      } catch {
        setDiagNote("Could not start diagnostic right now.");
      }
    }
  };

  const wikiCopy =
    wikiStatus === "running" || wikiStatus === "processing"
      ? "Wiki update still processing…"
      : wikiStatus === "complete"
        ? activity?.wikiUiMessage || "Project notes updated"
        : wikiStatus === "failed"
          ? activity?.wikiUiMessage || "The Wiki update could not be saved."
          : null;

  return (
    <div
      className="codirector-processing"
      data-testid="codirector-processing"
      aria-live="polite"
      aria-busy={busy || undefined}
    >
      {busy ? (
        <span className="codirector-spinner codirector-spinner--lg" data-testid="codirector-processing-spinner" aria-hidden />
      ) : null}
      <div>
        <p className="codirector-processing-title" data-testid="codirector-processing-label">
          {busy ? `Processing… ${label}` : "Ready"}
        </p>
        {delayHint ? (
          <p className="muted" data-testid={coldLoad ? "codirector-cold-load-hint" : "codirector-delay-hint"}>
            {delayHint}
          </p>
        ) : null}
        {busy && !hasTokens && (coldLoad || elapsedSec >= 8) ? (
          <div className="row" style={{ gap: "0.35rem", flexWrap: "wrap", marginTop: "0.35rem" }}>
            <Button compact variant="ghost" data-testid="codirector-delay-cancel" onClick={() => cancelSend()}>
              Cancel
            </Button>
            <Button
              compact
              variant="ghost"
              data-testid="codirector-continue-waiting"
              onClick={() => setContinueWaiting(true)}
            >
              Continue waiting
            </Button>
            <Button compact variant="ghost" data-testid="codirector-run-diagnostic" onClick={() => void runDiagnostic()}>
              Run diagnostic
            </Button>
          </div>
        ) : null}
        {continueWaiting ? (
          <p className="muted" data-testid="codirector-continue-waiting-ack">
            Still waiting on the selected model…
          </p>
        ) : null}
        {diagNote ? (
          <p className="muted" data-testid="codirector-diagnostic-note">
            {diagNote}
          </p>
        ) : null}
        {wikiCopy ? (
          <p className="muted" data-testid="codirector-wiki-background">
            {wikiCopy}
          </p>
        ) : null}
        {stages.length > 0 ? (
          <ul className="codirector-processing-stages" data-testid="codirector-processing-stages">
            {stages.slice(-6).map((stage) => (
              <li key={stage} className="muted">
                {stage === active && busy ? "◌ " : "✓ "}
                {STAGE_LABELS[stage] || stage}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </div>
  );
}
