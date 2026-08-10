import { useState, type ReactNode } from "react";
import "./workspace-card.css";

export function WorkspaceCard({
  title,
  description,
  badges = [],
  imageSrc,
  imageAlt,
  plateClass,
  onOpen,
  href,
  footer,
  testId = "ds-workspace-card",
}: {
  title: string;
  description: string;
  badges?: readonly string[];
  imageSrc?: string;
  imageAlt?: string;
  plateClass?: string;
  onOpen?: () => void;
  href?: string;
  footer?: ReactNode;
  testId?: string;
}) {
  const [imgFailed, setImgFailed] = useState(false);
  const showImg = Boolean(imageSrc) && !imgFailed;

  const inner = (
    <>
      <div className="ds-workspace-card__media">
        {plateClass ? <div className={["ds-workspace-card__plate", plateClass].join(" ")} aria-hidden /> : null}
        {showImg ? (
          <img src={imageSrc} alt={imageAlt || title} onError={() => setImgFailed(true)} />
        ) : null}
      </div>
      <div className="ds-workspace-card__body">
        <h3 className="ds-workspace-card__title">{title}</h3>
        <p className="ds-workspace-card__desc">{description}</p>
        {badges.length ? (
          <div className="ds-workspace-card__badges">
            {badges.map((b) => (
              <span key={b} className="ds-workspace-card__badge">
                {b}
              </span>
            ))}
          </div>
        ) : null}
        {footer ?? <span className="ds-workspace-card__open">Open →</span>}
      </div>
    </>
  );

  if (href) {
    return (
      <a className="ds-workspace-card" href={href} data-testid={testId}>
        {inner}
      </a>
    );
  }

  return (
    <button type="button" className="ds-workspace-card" onClick={onOpen} data-testid={testId}>
      {inner}
    </button>
  );
}
