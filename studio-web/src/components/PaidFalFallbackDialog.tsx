/** Explicit paid fal.ai fallback confirmation — never silent. */

export type PaidFalFallbackAction = "cancel" | "generate_local_start_frame" | "approve_paid_fal";

export function PaidFalFallbackDialog({
  open,
  title = "Local path needs a start frame",
  message,
  preferredLocalLabel = "Generate local start frame and continue",
  onAction,
}: {
  open: boolean;
  title?: string;
  message: string;
  preferredLocalLabel?: string;
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
          Local engines are tried first. fal.ai bills your account and is never submitted without
          approval.
        </p>
        <div className="row" style={{ flexWrap: "wrap", gap: "0.5rem", marginTop: "1rem" }}>
          <button
            type="button"
            className="primary"
            data-testid="generate-local-start-frame"
            onClick={() => onAction("generate_local_start_frame")}
          >
            {preferredLocalLabel}
          </button>
          <button
            type="button"
            data-testid="approve-paid-fal"
            onClick={() => onAction("approve_paid_fal")}
          >
            Approve paid fal.ai fallback
          </button>
          <button type="button" data-testid="cancel-fal-fallback" onClick={() => onAction("cancel")}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
