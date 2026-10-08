import { hero, shots } from "../content";
import { DownloadAdeptUI } from "./DownloadAdeptUI";
import { ProductFrame } from "./ProductFrame";

export function Hero() {
  return (
    <section className="hero" id="ai-filmmaking" aria-labelledby="ai-filmmaking-title">
      <div className="hero__atmosphere" aria-hidden="true" />
      <div className="hero__inner">
        <div className="hero__grid">
          <div>
            <ul className="pillars" aria-label="Production pillars">
              {hero.pillars.map((pillar) => (
                <li key={pillar}>{pillar}</li>
              ))}
            </ul>
            <p className="eyebrow">
              <span className="eyebrow__free">Free</span>
              <span className="eyebrow__kind">
                <span aria-hidden="true"> · </span>
                {hero.eyebrow}
              </span>
            </p>
            <h1 id="ai-filmmaking-title">{hero.title}</h1>
            <p className="hero__support">{hero.support}</p>
            <p className="hero__body">{hero.body}</p>
            <p className="hero__beta">{hero.beta}</p>
            <DownloadAdeptUI variant="hero" />
            <ul className="pills" aria-label="Capabilities">
              {hero.pills.map((pill) => (
                <li key={pill}>{pill}</li>
              ))}
            </ul>
          </div>
          <div className="hero__stage">
            <img
              className="hero__emblem"
              src="/brand/adept-ui-emblem.webp"
              alt=""
              width={640}
              height={640}
            />
            <ProductFrame
              className="shot--hero"
              src={shots.home.src}
              alt={shots.home.alt}
              width={894}
              height={732}
              caption={shots.home.caption}
              eager
            />
          </div>
        </div>
        <div className="hero__rule" aria-hidden="true" />
      </div>
    </section>
  );
}
