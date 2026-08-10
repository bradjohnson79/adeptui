import type { ReactNode } from "react";
import { Button } from "./Button";
import "./dialog.css";

export function Dialog({
  open,
  title,
  children,
  onClose,
  primaryLabel = "Confirm",
  secondaryLabel = "Cancel",
  onPrimary,
  danger,
  closeOnPrimary = true,
  primaryDisabled = false,
  primaryLoading = false,
  testId,
}: {
  open: boolean;
  title: string;
  children?: ReactNode;
  onClose: () => void;
  primaryLabel?: string;
  secondaryLabel?: string;
  onPrimary?: () => void;
  danger?: boolean;
  /** When false, caller must close the dialog after primary action (useful for async work). */
  closeOnPrimary?: boolean;
  primaryDisabled?: boolean;
  primaryLoading?: boolean;
  testId?: string;
}) {
  if (!open) return null;
  return (
    <div
      className="ds-dialog-backdrop"
      role="presentation"
      data-testid={testId ? `${testId}-backdrop` : undefined}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && !primaryLoading) onClose();
      }}
    >
      <div
        className="ds-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-label={title}
        data-testid={testId}
        onKeyDown={(e) => {
          if (e.key === "Escape" && !primaryLoading) onClose();
        }}
      >
        <h2 className="ds-dialog__title">{title}</h2>
        <div className="ds-dialog__body">{children}</div>
        <div className="ds-dialog__actions">
          <Button
            variant="secondary"
            disabled={primaryLoading}
            data-testid={testId ? `${testId}-cancel` : undefined}
            onClick={onClose}
          >
            {secondaryLabel}
          </Button>
          <Button
            variant={danger ? "danger" : "primary"}
            loading={primaryLoading}
            disabled={primaryDisabled || primaryLoading}
            data-testid={testId ? `${testId}-confirm` : undefined}
            onClick={() => {
              onPrimary?.();
              if (closeOnPrimary) onClose();
            }}
          >
            {primaryLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
