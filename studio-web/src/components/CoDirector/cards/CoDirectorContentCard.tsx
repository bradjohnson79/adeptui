import type { ReactNode } from "react";

export function CoDirectorContentCard({
  title,
  meta,
  children,
  footer,
  tone = "default",
  testId,
}: {
  title?: ReactNode;
  meta?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  tone?: "default" | "warning" | "approval" | "plan" | "job" | "entity" | "asset";
  testId?: string;
}) {
  return (
    <article
      className={`codirector-content-card tone-${tone}`}
      data-testid={testId || "codirector-content-card"}
    >
      {(title || meta) && (
        <header className="codirector-content-card-head">
          {title ? <h3>{title}</h3> : null}
          {meta ? <p className="codirector-content-card-meta">{meta}</p> : null}
        </header>
      )}
      {children ? <div className="codirector-content-card-body">{children}</div> : null}
      {footer ? <footer className="codirector-content-card-footer">{footer}</footer> : null}
    </article>
  );
}

export function CoDirectorEntityCard(props: Omit<Parameters<typeof CoDirectorContentCard>[0], "tone">) {
  return <CoDirectorContentCard {...props} tone="entity" />;
}

export function CoDirectorAssetCard(props: Omit<Parameters<typeof CoDirectorContentCard>[0], "tone">) {
  return <CoDirectorContentCard {...props} tone="asset" />;
}

export function CoDirectorPlanCard(props: Omit<Parameters<typeof CoDirectorContentCard>[0], "tone">) {
  return <CoDirectorContentCard {...props} tone="plan" />;
}

export function CoDirectorApprovalCard(props: Omit<Parameters<typeof CoDirectorContentCard>[0], "tone">) {
  return <CoDirectorContentCard {...props} tone="approval" />;
}

export function CoDirectorWarningCard(props: Omit<Parameters<typeof CoDirectorContentCard>[0], "tone">) {
  return <CoDirectorContentCard {...props} tone="warning" />;
}

export function CoDirectorJobCard(props: Omit<Parameters<typeof CoDirectorContentCard>[0], "tone">) {
  return <CoDirectorContentCard {...props} tone="job" />;
}
