/**
 * Compact Homepage header.
 * The wide cinematic raster stays on disk as a master and is not requested here.
 * Emblem: /brand/adept-ui-emblem.webp
 */
const CAPABILITIES = [
  ["Characters", "Image Generation", "Storyboarding", "AI Video"],
  ["Voice", "Scriptwriting", "Editing", "Production Management"],
  ["Local AI Models", "API Models"],
] as const;

export function GenerationStudioHero() {
  return (
    <section className="gs-hero" aria-label="Adept UI" data-testid="generation-studio-hero">
      <div className="gs-hero__atmosphere" aria-hidden="true" />
      <div className="gs-hero__layout">
        <img
          className="gs-hero__logo"
          src="/brand/adept-ui-emblem.webp?v=clear"
          alt="Anadriya emblem"
          width={640}
          height={640}
          decoding="async"
          data-testid="generation-studio-hero-logo"
        />
        <div className="gs-hero__copy">
          <h1 className="gs-hero__title">ADEPT UI</h1>
          <p className="gs-hero__kicker">AI-Powered Film Production</p>
          <p className="gs-hero__summary">
            A unified AI filmmaking environment for developing characters, worlds, storyboards, images, voices,
            scenes, video, and finished productions from one creative workspace.
          </p>
          <div className="gs-hero__caps" aria-label="Capabilities">
            {CAPABILITIES.map((row, index) => (
              <ul key={row[0]} className={index === 1 ? "gs-hero__cap-row gs-hero__cap-row--extra" : "gs-hero__cap-row"}>
                {row.map((label) => (
                  <li key={label}>{label}</li>
                ))}
              </ul>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
