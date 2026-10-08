import { audience, beta, control, faq, finale, footer, localApi, platform, site } from "../content";
import { ecosystemLinks, publicExternalUrl } from "../externalLinks";
import { Chapter, SectionHeading } from "./ui";

export function LocalApi() {
  return (
    <Chapter id="local-ai" labelledBy="local-ai-title">
      <SectionHeading id="local-ai-title" eyebrow={localApi.eyebrow} title={localApi.title} lede={localApi.lede} />
      <div className="dual">
        <article className="dual--local">
          <h3>{localApi.localTitle}</h3>
          <ul>
            {localApi.local.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>
        <article className="dual--api">
          <h3>{localApi.apiTitle}</h3>
          <ul>
            {localApi.api.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>
      </div>
      <ComfyNote />
    </Chapter>
  );
}

function ComfyNote() {
  const comfyUrl = publicExternalUrl("comfyui");
  return (
    <aside className="comfy-note">
      <h3>
        Built on{" "}
        {comfyUrl ? (
          <a href={comfyUrl} target="_blank" rel="noreferrer">
            ComfyUI
          </a>
        ) : (
          "ComfyUI"
        )}{" "}
        Workflows
      </h3>
      <p>{localApi.comfy.body}</p>
      <ul>
        {localApi.comfy.points.map((point) => (
          <li key={point}>{point}</li>
        ))}
      </ul>
      <a className="comfy-note__more" href={localApi.comfy.docsHref}>
        {localApi.comfy.docsLabel}
      </a>
    </aside>
  );
}

export function About() {
  return (
    <Chapter id="about" labelledBy="about-title">
      <SectionHeading id="about-title" eyebrow={control.eyebrow} title={control.title} lede={control.lede} />
      <ol className="principles">
        {control.points.map((point, index) => (
          <li key={point.title} className="principle">
            <span>{String(index + 1).padStart(2, "0")}</span>
            <div>
              <h3>{point.title}</h3>
              <p>{point.body}</p>
            </div>
          </li>
        ))}
      </ol>
      <p className="privacy">{control.privacy}</p>
    </Chapter>
  );
}

export function Audience() {
  return (
    <Chapter id="audience" labelledBy="audience-title">
      <SectionHeading id="audience-title" eyebrow={audience.eyebrow} title={audience.title} lede={audience.lede} />
      <ul className="roster">
        {audience.people.map((person) => (
          <li key={person}>{person}</li>
        ))}
      </ul>
    </Chapter>
  );
}

export function Platform() {
  return (
    <Chapter id="platform" labelledBy="platform-title" wide>
      <SectionHeading id="platform-title" eyebrow={platform.eyebrow} title={platform.title} />
      <div className="capgrid">
        {platform.columns.map((column) => (
          <article key={column.title}>
            <h3>{column.title}</h3>
            <ul>
              {column.items.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </article>
        ))}
      </div>
    </Chapter>
  );
}

export function Faq() {
  return (
    <Chapter id="faq" labelledBy="faq-title">
      <SectionHeading id="faq-title" eyebrow={faq.eyebrow} title={faq.title} />
      <div className="faq">
        {faq.items.map((item) => (
          <article key={item.q}>
            <h3>{item.q}</h3>
            <p>{item.a}</p>
          </article>
        ))}
      </div>
    </Chapter>
  );
}

export function FinalCta() {
  return (
    <section className="finale" id="cta" aria-labelledby="cta-title">
      <div className="finale__inner">
        <img className="finale__mark" src="/brand/adept-ui-emblem.webp" alt="" width={640} height={640} />
        <p className="eyebrow">{site.kicker}</p>
        <h2 id="cta-title">
          {finale.titleLead}
          <br />
          {finale.titleRest}
        </h2>
        <p className="lede">{finale.body}</p>
        <a className="btn btn--primary" href={finale.cta.href}>
          {finale.cta.label}
        </a>
        <p className="finale__note">{finale.note}</p>
      </div>
    </section>
  );
}

export function Footer() {
  const year = new Date().getFullYear();
  return (
    <footer className="footer">
      <div className="footer__inner">
        <div>
          <strong className="footer__brand">
            ADEPT UI <span className="beta-badge">{beta.label}</span>
          </strong>
          <p>Adept UI — Beta</p>
          <p>{site.kicker}</p>
          <p>© {year} - Adept UI/ANOINT Inc.</p>
        </div>
        <nav aria-label="Footer">
          {footer.links.map((link) => (
            <a key={link.href} href={link.href.startsWith("#") && window.location.pathname !== "/" ? `/${link.href}` : link.href}>
              {link.label}
            </a>
          ))}
        </nav>
        <nav className="footer__ecosystem" aria-label="Ecosystem">
          <p>Ecosystem</p>
          {ecosystemLinks().map((link) => (
            <a
              key={link.label}
              href={link.href.startsWith("#") && window.location.pathname !== "/" ? `/${link.href}` : link.href}
              {...(link.external ? { target: "_blank", rel: "noreferrer" } : {})}
            >
              {link.label}
            </a>
          ))}
        </nav>
      </div>
    </footer>
  );
}
