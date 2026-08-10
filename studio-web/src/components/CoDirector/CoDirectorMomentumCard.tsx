import { useCoDirectorSession } from "./CoDirectorSession";

/** Calm “where we left off” card — creator language, not engineer state. */
export function CoDirectorMomentumCard() {
  const { activity, expertiseMode } = useCoDirectorSession();
  const resume = activity?.momentumResume;
  const summary = activity?.momentumSummary;
  if (!resume && !summary) return null;
  // Always show resume greeting when present; Advanced shows denser summary.
  return (
    <div
      className="codirector-content-card"
      data-testid="codirector-momentum-card"
      style={{ marginTop: "0.5rem" }}
    >
      <p style={{ margin: 0 }} data-testid="codirector-momentum-resume">
        {resume || summary}
      </p>
      {expertiseMode === "expert" && activity?.lastTimings ? (
        <details style={{ marginTop: "0.5rem" }} data-testid="codirector-timing-diagnostics">
          <summary className="muted">Response timing (advanced)</summary>
          <pre className="codirector-retrieval-json" style={{ fontSize: "0.75rem" }}>
            {JSON.stringify(activity.lastTimings, null, 2)}
          </pre>
        </details>
      ) : null}
    </div>
  );
}
