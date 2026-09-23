import { useState } from "react";
import { dashboardImages } from "../../dashboardImages";
import { Button } from "../ui/Button";
import { useCoDirectorSession, useOpenCoDirector } from "../CoDirector";

const BENEFITS = [
  "Understands your project, scenes, and production context",
  "Helps plan, write, direct, and finish your work",
  "Works across Timeline, MAGI, creators, and Library",
  "Analyzes, proposes, and carries out supported production tasks",
] as const;

export function CoDirectorLaunchCard({ activeProjectName }: { activeProjectName?: string | null } = {}) {
  const openCoDirector = useOpenCoDirector();
  const { busy } = useCoDirectorSession();
  const image = dashboardImages.codirector;
  const [imageFailed, setImageFailed] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const enterFullscreen = () => {
    try {
      setError(null);
      openCoDirector(undefined, { fullscreen: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not open Co-Director.");
    }
  };

  return (
    <section
      className="glass-section gs-codirector-card"
      aria-labelledby="gs-codirector-heading"
      data-testid="codirector-launch-card"
      id="codirector"
    >
      <div className={`gs-codirector-card__media ${imageFailed ? image.motif : ""}`}>
        {imageFailed ? <div className="cinematic-media-fallback" aria-hidden="true" /> : null}
        {imageFailed ? null : (
          <img
            src={image.src}
            alt={image.alt}
            data-testid="codirector-launch-image"
            onError={() => setImageFailed(true)}
          />
        )}
        <div className="gs-codirector-card__scrim" aria-hidden="true" />
      </div>
      <div className="gs-codirector-card__content">
        <h2 id="gs-codirector-heading">Co-Director</h2>
        <p className="gs-codirector-card__tagline">Your intelligent production partner across Adept UI.</p>
        <ul className="gs-codirector-card__benefits">
          {BENEFITS.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
        <div className="gs-codirector-card__footer">
          <p className="gs-codirector-card__context" data-testid="codirector-project-context">
            {activeProjectName ? (
              <>
                Active project: <strong>{activeProjectName}</strong>
              </>
            ) : (
              "Open Co-Director to choose or continue a project."
            )}
          </p>
          <Button
            type="button"
            variant="primary"
            data-testid="enter-codirector"
            disabled={busy}
            onClick={enterFullscreen}
          >
            Enter Co-Director
          </Button>
        </div>
        {error ? (
          <p className="gs-codirector-card__error" role="alert">
            {error}
          </p>
        ) : null}
      </div>
    </section>
  );
}
