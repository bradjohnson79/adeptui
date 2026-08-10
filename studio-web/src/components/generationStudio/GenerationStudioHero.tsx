/**
 * Cinematic hero for Generation Studio landing.
 * Asset: /images/hero/Adept_UI_Hero_header.webp (source: hero/Adept_UI_Hero_header.png, 1983×793)
 * Logo overlay: /brand/adept-ui-logo.svg
 */
export function GenerationStudioHero() {
  return (
    <section
      className="gs-hero"
      aria-label="Adept UI Studio"
      data-testid="generation-studio-hero"
    >
      <picture className="gs-hero__picture">
        <source srcSet="/images/hero/Adept_UI_Hero_header.webp" type="image/webp" />
        <img
          className="gs-hero__media"
          src="/images/hero/Adept_UI_Hero_header.png"
          alt=""
          width={1983}
          height={793}
          decoding="async"
          fetchPriority="high"
          data-testid="generation-studio-hero-image"
        />
      </picture>
      <div className="gs-hero__overlay" aria-hidden="true" />
      <div className="gs-hero__vignette" aria-hidden="true" />
      <div className="gs-hero__brand" aria-hidden="true">
        <img
          className="gs-hero__logo"
          src="/brand/adept-ui-logo.svg"
          alt=""
          width={320}
          height={300}
          data-testid="generation-studio-hero-logo"
        />
      </div>
      <div className="gs-hero__copy" aria-hidden="true">
        <p>AI-Powered Film Production</p>
        <p className="gs-hero__tagline">From Story to Screen</p>
      </div>
    </section>
  );
}
