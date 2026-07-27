import type { ReactNode } from "react";

/** Circular (?) help tip — shows a short description on hover (≤30 words). */
export function HelpTip({ text }: { text: string }) {
  return (
    <button
      type="button"
      className="help-tip"
      aria-label={text}
      onClick={(e) => e.stopPropagation()}
      onMouseDown={(e) => e.stopPropagation()}
    >
      <span className="help-tip-icon" aria-hidden="true">
        ?
      </span>
      <span className="help-tip-bubble" role="tooltip">
        {text}
      </span>
    </button>
  );
}

/** Panel title row with optional trailing actions and a help tip. */
export function PanelHeading({
  title,
  tip,
  children,
  as = "h2",
}: {
  title: string;
  tip: string;
  children?: ReactNode;
  as?: "h2" | "h3" | "strong";
}) {
  const Tag = as;
  return (
    <div className="panel-heading">
      <div className="panel-heading-title">
        <Tag>{title}</Tag>
        <HelpTip text={tip} />
      </div>
      {children ? <div className="panel-heading-actions">{children}</div> : null}
    </div>
  );
}
