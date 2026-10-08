import { continuity, magi, models, shots, systems, timeline } from "../content";
import { ProductFrame } from "./ProductFrame";
import { Chapter, SectionHeading } from "./ui";

export function Systems() {
  return (
    <Chapter id="production" labelledBy="production-title" wide>
      <SectionHeading id="production-title" eyebrow={systems.eyebrow} title={systems.title} lede={systems.lede} />
      <div className="bento">
        {systems.cards.map((card) => (
          <article key={card.name} className={`system system--${card.span}`}>
            <h3>{card.name}</h3>
            <p>{card.body}</p>
            {card.note ? <p className="system__note">{card.note}</p> : null}
          </article>
        ))}
      </div>
    </Chapter>
  );
}

export function Continuity() {
  return (
    <Chapter id="continuity" labelledBy="continuity-title">
      <SectionHeading id="continuity-title" eyebrow={continuity.eyebrow} title={continuity.title} lede={continuity.lede} />
      <div className="pair">
        <ProductFrame
          src={shots.character.src}
          alt={shots.character.alt}
          width={894}
          height={843}
          caption={shots.character.caption}
        />
        <div id="ai-voice">
          <ProductFrame
            className="shot--overlap"
            src={shots.voice.src}
            alt={shots.voice.alt}
            width={894}
            height={843}
            caption={shots.voice.caption}
          />
        </div>
      </div>
      <p className="voice-note">{continuity.voice}</p>
      <ul className="memory">
        {continuity.points.map((point) => (
          <li key={point.title}>
            <h3>{point.title}</h3>
            <p>{point.body}</p>
          </li>
        ))}
      </ul>
    </Chapter>
  );
}

export function Models() {
  return (
    <Chapter id="models" labelledBy="models-title">
      <SectionHeading id="models-title" eyebrow={models.eyebrow} title={models.title} lede={models.lede} />
      <p className="qualifier">{models.qualifier}</p>
      <div className="model-board">
        <article className="model-col">
          <h3>{models.localTitle}</h3>
          <p className="model-label">Video</p>
          <ul className="badges" aria-label="Local video engines">
            {models.localVideo.map((name) => (
              <li key={name}>{name}</li>
            ))}
          </ul>
          <p className="model-label">Stills, when installed</p>
          <ul className="badges" aria-label="Local image families">
            {models.localImage.map((name) => (
              <li key={name}>{name}</li>
            ))}
          </ul>
        </article>
        <article className="model-col">
          <h3>{models.apiTitle}</h3>
          <p className="model-label">Video</p>
          <ul className="badges" aria-label="Hosted video engines">
            {models.apiVideo.map((name) => (
              <li key={name}>{name}</li>
            ))}
          </ul>
          <p>{models.apiNote}</p>
        </article>
      </div>
    </Chapter>
  );
}

export function Timeline() {
  return (
    <Chapter id="timeline" labelledBy="timeline-title">
      <SectionHeading id="timeline-title" eyebrow={timeline.eyebrow} title={timeline.title} lede={timeline.lede} />
      <div id="ai-video">
        <ProductFrame
          className="shot--stage"
          src={shots.timeline.src}
          alt={shots.timeline.alt}
          width={894}
          height={843}
          caption={shots.timeline.caption}
        />
      </div>
      <ol className="playhead">
        {timeline.points.map((point) => (
          <li key={point.title}>
            <h3>{point.title}</h3>
            <p>{point.body}</p>
          </li>
        ))}
      </ol>
      <p className="caveat">{timeline.caveat}</p>
    </Chapter>
  );
}

export function Magi() {
  return (
    <Chapter id="magi" labelledBy="magi-title">
      <SectionHeading id="magi-title" eyebrow={magi.eyebrow} title={magi.title} lede={magi.lede} />
      <ProductFrame
        className="shot--stage"
        src={shots.magi.src}
        alt={shots.magi.alt}
        width={894}
        height={843}
        caption={shots.magi.caption}
      />
      <ul className="finish-list finish-list--grid">
        {magi.points.map((point) => (
          <li key={point}>{point}</li>
        ))}
      </ul>
      <p className="caveat">{magi.caveat}</p>
    </Chapter>
  );
}
