import { useState, type ReactNode } from "react";
import { getAuroraCardImage, type AuroraCardKey } from "../../theme/auroraCardImagery";

export type ImageReadyCardProps = {
  imageKey: AuroraCardKey;
  title: string;
  meta?: string;
  children?: ReactNode;
  className?: string;
  onClick?: () => void;
  "data-testid"?: string;
};

export function ImageReadyCard({
  imageKey,
  title,
  meta,
  children,
  className = "",
  onClick,
  "data-testid": testId,
}: ImageReadyCardProps) {
  const img = getAuroraCardImage(imageKey);
  const [failed, setFailed] = useState(false);

  return (
    <article
      className={["image-ready-card", className].filter(Boolean).join(" ")}
      data-testid={testId}
      onClick={onClick}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={
        onClick
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onClick();
              }
            }
          : undefined
      }
    >
      <div className="image-ready-card__media" aria-hidden={failed || undefined}>
        {!failed ? (
          <img src={img.src} alt={img.alt} onError={() => setFailed(true)} loading="lazy" />
        ) : null}
        {failed ? <div className={img.plate} role="img" aria-label={img.alt} /> : null}
      </div>
      <div className="image-ready-card__body">
        <h3 className="image-ready-card__title">{title}</h3>
        {meta ? <p className="image-ready-card__meta">{meta}</p> : null}
        {children}
      </div>
    </article>
  );
}
