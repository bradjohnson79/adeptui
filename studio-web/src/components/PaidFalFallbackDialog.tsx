/** Explicit paid fal.ai Text-to-Video approval — never silent. */

export type PaidFalFallbackAction = "cancel" | "approve_paid_fal";

export function PaidFalFallbackDialog({
  open,
  title = "Approve paid Text-to-Video",
  message,
  onAction,
}: {
  open: boolean;
  title?: string;
  message: string;
  onAction: (action: PaidFalFallbackAction) => void;
}) {
  if (!open) return null;
  return (
    <div
      className="codirector-modal-backdrop"
      role="presentation"
      data-testid="paid-fal-fallback-dialog"
      onClick={() => onAction("cancel")}
    >
      <div
        className="codirector-modal card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="paid-fal-fallback-title"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="paid-fal-fallback-title">{title}</h2>
        <p>{message}</p>
        <p className="muted">
          fal.ai bills your account and is never submitted without approval.
        </p>
        <div className="row" style={{ flexWrap: "wrap", gap: "0.5rem", marginTop: "1rem" }}>
          <button
            type="button"
            data-testid="approve-paid-fal"
            onClick={() => onAction("approve_paid_fal")}
          >
            Approve paid fal.ai submission
          </button>
          <button type="button" data-testid="cancel-fal-fallback" onClick={() => onAction("cancel")}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
