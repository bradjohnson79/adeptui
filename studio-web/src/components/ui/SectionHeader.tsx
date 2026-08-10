import type { ReactNode } from "react";
import "./section-header.css";

export function SectionHeader({ eyebrow, title, description, actions, className = "" }: { eyebrow?: ReactNode; title: ReactNode; description?: ReactNode; actions?: ReactNode; className?: string }) {
  return <header className={["ds-section-header", className].filter(Boolean).join(" ")}>{eyebrow ? <div className="ds-section-header__eyebrow">{eyebrow}</div> : null}<div className="ds-section-header__row"><div><h2>{title}</h2>{description ? <p>{description}</p> : null}</div>{actions ? <div className="ds-section-header__actions">{actions}</div> : null}</div></header>;
}
