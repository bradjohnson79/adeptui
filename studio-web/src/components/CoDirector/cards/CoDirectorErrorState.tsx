import type { ReactNode } from "react";
import { ErrorState } from "../../ui";

export function CoDirectorErrorState({
  title,
  description,
  action,
  testId = "codirector-error-state",
}: {
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  testId?: string;
}) {
  return (
    <div className="codirector-error-state" data-testid={testId} role="alert">
      <ErrorState title={title} description={description} actions={action} className="codirector-error-state-inner" />
    </div>
  );
}
