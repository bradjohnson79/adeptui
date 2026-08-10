import type { ReactNode } from "react";
import { EmptyState, type EmptyStateKind } from "../../ui";

/** Compact quiet empty state for Co-Director progressive disclosure. */
export function CoDirectorEmptyState({
  title,
  description,
  action,
  kind = "first-use",
  testId = "codirector-empty-state",
}: {
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  kind?: EmptyStateKind;
  testId?: string;
}) {
  return (
    <div className="codirector-empty-state" data-testid={testId}>
      <EmptyState
        kind={kind}
        title={title}
        description={description}
        actions={action}
        className="codirector-empty-state-inner"
      />
    </div>
  );
}
