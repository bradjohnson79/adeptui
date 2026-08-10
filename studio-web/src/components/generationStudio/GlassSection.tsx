import type { ReactNode } from "react";

export function GlassSection({
  id,
  title,
  description,
  children,
  className = "",
  strong = false,
  headingLevel = 2,
  testId,
}: {
  id?: string;
  title?: string;
  description?: string;
  children: ReactNode;
  className?: string;
  strong?: boolean;
  headingLevel?: 2 | 3;
  testId?: string;
}) {
  const Heading = headingLevel === 3 ? "h3" : "h2";
  return (
    <section
      id={id}
      className={`glass-section ${strong ? "glass-section--strong" : ""} ${className}`.trim()}
      data-testid={testId}
      aria-labelledby={title && id ? `${id}-heading` : undefined}
    >
      {title ? (
        <Heading id={id ? `${id}-heading` : undefined} className="section-heading">
          {title}
        </Heading>
      ) : null}
      {description ? <p className="muted">{description}</p> : null}
      {children}
    </section>
  );
}
