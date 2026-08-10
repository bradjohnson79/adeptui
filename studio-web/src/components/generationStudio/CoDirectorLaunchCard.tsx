import { useId, useState, type FormEvent } from "react";
import { Button, IconButton } from "../ui/Button";
import { useCoDirectorSession, useOpenCoDirector } from "../CoDirector";

const PROMPT_STARTERS = [
  "Start a storyboard",
  "Generate a shot list",
  "Build a character",
  "Create a trailer",
  "Analyze a script",
] as const;

export function CoDirectorLaunchCard({ activeProjectName }: { activeProjectName?: string | null } = {}) {
  const openCoDirector = useOpenCoDirector();
  const { busy } = useCoDirectorSession();
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const inputId = useId();

  const launchFullscreen = (prompt?: string) => {
    setError(null);
    const preserved = draft;
    try {
      setSubmitting(true);
      openCoDirector(prompt, { fullscreen: true });
      if (prompt) setDraft("");
    } catch (e) {
      setDraft(preserved);
      setError(e instanceof Error ? e.message : "Could not open Co-Director.");
    } finally {
      window.setTimeout(() => setSubmitting(false), 400);
    }
  };

  const onSubmit = (e?: FormEvent) => {
    e?.preventDefault();
    const text = draft.trim();
    if (!text || submitting || busy) return;
    launchFullscreen(text);
  };

  return (
    <section
      className="glass-section gs-codirector-card"
      aria-labelledby="gs-codirector-heading"
      data-testid="codirector-launch-card"
      id="codirector"
    >
      <div className="gs-codirector-card__main">
        <div className="gs-codirector-card__title-row">
          <span className="gs-codirector-card__glyph" aria-hidden="true">
            ◆
          </span>
          <div>
            <h2 id="gs-codirector-heading">Co-Director</h2>
          </div>
        </div>
        <p className="gs-codirector-card__desc">
          Your AI production partner. Plan, create, and bring your vision to life.
        </p>
        <p className="gs-codirector-card__context" data-testid="codirector-project-context">
          {activeProjectName ? (
            <>
              Project context: <strong>{activeProjectName}</strong>
            </>
          ) : (
            "Project context follows the project you most recently opened or created."
          )}
        </p>
        <form className="gs-composer" onSubmit={onSubmit}>
          <label className="sr-only" htmlFor={inputId}>
            Ask Co-Director about your project
          </label>
          <textarea
            id={inputId}
            className="gs-composer__input"
            data-testid="codirector-launch-composer"
            rows={2}
            value={draft}
            disabled={submitting}
            placeholder="Ask anything about your project…"
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                onSubmit();
              }
            }}
          />
          <IconButton
            type="submit"
            variant="primary"
            aria-label="Send to Co-Director"
            data-testid="codirector-launch-submit"
            disabled={!draft.trim() || submitting || busy}
            loading={submitting}
          >
            →
          </IconButton>
        </form>
        <div className="gs-prompt-starters" role="group" aria-label="Prompt starters">
          {PROMPT_STARTERS.map((starter) => (
            <Button
              key={starter}
              type="button"
              variant="ghost"
              compact
              data-testid={`codirector-starter-${starter.toLowerCase().replace(/\s+/g, "-")}`}
              onClick={() => setDraft(starter)}
            >
              {starter}
            </Button>
          ))}
        </div>
        {error ? (
          <p className="gs-codirector-card__error" role="alert">
            {error}
          </p>
        ) : null}
      </div>
      <div className="gs-codirector-card__entry">
        <div className="gs-codirector-card__orb" aria-hidden="true">
          ◎
        </div>
        <Button
          type="button"
          variant="primary"
          data-testid="enter-codirector"
          onClick={() => launchFullscreen()}
        >
          Enter Co-Director →
        </Button>
      </div>
    </section>
  );
}
