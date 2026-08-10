import type { ReactNode } from "react";
import "./empty-state.css";

export type EmptyStateKind =
  | "first-use"
  | "no-results"
  | "filtered"
  | "unavailable"
  | "install-required"
  | "blocked"
  | "failed";

export type EmptyStateProps = {
  kind: EmptyStateKind;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  /** Local artwork under /images/ui/empty-states/ */
  artworkSrc?: string;
  artworkAlt?: string;
  className?: string;
};

export function EmptyState({
  kind,
  title,
  description,
  actions,
  artworkSrc,
  artworkAlt = "",
  className = "",
}: EmptyStateProps) {
  return (
    <div
      className={["ds-empty-state", `ds-empty-state--${kind}`, className].filter(Boolean).join(" ")}
      role="status"
      data-testid="ds-empty-state"
    >
      {artworkSrc ? (
        <div className="ds-empty-state__art">
          <img src={artworkSrc} alt={artworkAlt} />
        </div>
      ) : null}
      <h2>{title}</h2>
      {description ? <p>{description}</p> : null}
      {actions ? <div className="ds-empty-state__actions">{actions}</div> : null}
    </div>
  );
}

export function ErrorState(
  props: Omit<EmptyStateProps, "kind"> & { kind?: "failed" | "unavailable" | "blocked" }
) {
  return <EmptyState {...props} kind={props.kind ?? "failed"} />;
}
