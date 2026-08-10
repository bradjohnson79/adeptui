import type { ReactNode } from "react";

export function MagiAccordion({
  id,
  title,
  open,
  onToggle,
  children,
  badge,
}: {
  id: string;
  title: string;
  open: boolean;
  onToggle: (next: boolean) => void;
  children: ReactNode;
  badge?: ReactNode;
}) {
  return (
    <div className="magi-acc" data-accordion-id={id}>
      <button
        type="button"
        className="magi-acc__header"
        aria-expanded={open}
        aria-controls={`magi-acc-panel-${id}`}
        id={`magi-acc-btn-${id}`}
        onClick={() => onToggle(!open)}
      >
        <span className="magi-acc__chevron" aria-hidden="true">
          {open ? "▾" : "▸"}
        </span>
        <span className="magi-acc__title">{title}</span>
        {badge ? <span className="magi-acc__badge">{badge}</span> : null}
      </button>
      {open ? (
        <div
          className="magi-acc__panel"
          id={`magi-acc-panel-${id}`}
          role="region"
          aria-labelledby={`magi-acc-btn-${id}`}
        >
          {children}
        </div>
      ) : null}
    </div>
  );
}
