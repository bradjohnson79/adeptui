import { useCoDirectorSession } from "./CoDirectorSession";

function asText(value: unknown, fallback = ""): string {
  if (value == null) return fallback;
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return fallback;
}

function asNumber(value: unknown, fallback = 0): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

/** Compact project-awareness strip — creator-safe, no emotion meters. */
export function CoDirectorProjectPulse() {
  const { activity } = useCoDirectorSession();
  const pulse = (activity?.projectPulse || {}) as Record<string, unknown>;
  if (!activity?.projectPulse && !activity?.creativeStage && activity?.wikiCandidates == null) return null;

  const confirmed = asNumber(pulse.confirmed_facts ?? pulse.confirmedFacts ?? activity?.confirmedWrites, 0);
  const emerging = asNumber(pulse.emerging_ideas ?? pulse.emergingIdeas, 0);
  const open = asNumber(pulse.open_decisions ?? pulse.openDecisions ?? activity?.discoveryQuestionCount, 0);
  const phase = asText(pulse.current_phase ?? pulse.currentPhase ?? activity?.creativeStage, "Discovery");
  const momentum = asText(pulse.creative_momentum ?? pulse.creativeMomentum, "Building");
  const next = asText(pulse.next_useful_step ?? pulse.nextUsefulStep, "");

  return (
    <section
      className="codirector-content-card"
      data-testid="codirector-project-pulse"
      aria-label="Project pulse"
      style={{ marginTop: "0.5rem" }}
    >
      <p className="eyebrow">Project pulse</p>
      <p className="muted" data-testid="codirector-pulse-phase">
        Current phase: {phase}
      </p>
      <p className="muted">Creative momentum: {momentum}</p>
      <p className="muted">
        Confirmed facts: {confirmed} · Emerging ideas: {emerging} · Open decisions: {open}
      </p>
      {next ? (
        <p className="muted" data-testid="codirector-pulse-next">
          Next useful step: {next}
        </p>
      ) : null}
    </section>
  );
}
