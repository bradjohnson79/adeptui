import { Dialog } from "../ui";
import type { ProviderSwitchPreview } from "../../modelRegistry/contracts";

export function ProviderSwitchConfirm({
  open,
  preview,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  preview: ProviderSwitchPreview | null;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  if (!open || !preview) return null;

  return (
    <Dialog
      open={open}
      title="Confirm provider switch"
      primaryLabel="Switch provider"
      secondaryLabel="Keep current"
      onClose={onCancel}
      onPrimary={onConfirm}
    >
      <p>{preview.impactSummary}</p>
      {preview.affectedModalities?.length ? (
        <p className="production-dock-muted">
          Affects: {preview.affectedModalities.join(", ")}
        </p>
      ) : null}
      <p className="production-dock-muted">
        Provider changes never happen silently after a job is already running.
      </p>
    </Dialog>
  );
}
