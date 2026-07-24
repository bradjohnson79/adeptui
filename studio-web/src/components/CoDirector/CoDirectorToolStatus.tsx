import type { CoDirectorToolActivity } from "./types";

const PHASE_LABEL: Record<CoDirectorToolActivity["phase"], string> = {
  requested: "Looking something up",
  running: "Checking",
  completed: "Checked",
  failed: "Couldn't check",
  blocked: "Couldn't check",
};

/**
 * One compact line describing the read tool Co-Director used this turn.
 *
 * Read tools are server-side, immediate, and query-only, so this is status — not a task list and
 * not a control surface. There is deliberately nothing here to click: it must never become a way
 * to run, re-run, or approve anything (mutations are proposal cards, and nothing here routes
 * through the legacy local `runSteps` path).
 */
export function CoDirectorToolStatus({ activity }: { activity: CoDirectorToolActivity }) {
  const failed = activity.phase === "failed" || activity.phase === "blocked";
  const busy = activity.phase === "requested" || activity.phase === "running";

  return (
    <p
      className={`codirector-tool-status${failed ? " codirector-tool-status-failed" : ""}`}
      role="status"
      aria-live="polite"
    >
      <span className="codirector-tool-status-label">
        {PHASE_LABEL[activity.phase]}: {activity.title}
        {busy && "…"}
      </span>
      {activity.detail && <span className="muted"> — {activity.detail}</span>}
      {activity.truncated && <span className="muted"> — result shortened to fit</span>}
    </p>
  );
}
