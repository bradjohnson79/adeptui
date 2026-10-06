import { Dialog } from "../ui/Dialog";
import {
  type CreatorDeletePreview,
  type CreatorEntityType,
  buildDeleteCopy,
} from "./creatorProfileDelete";

export type CreatorProfileDeleteModalProps = {
  open: boolean;
  entityType: CreatorEntityType;
  preview: CreatorDeletePreview | null;
  deleting: boolean;
  onClose: () => void;
  onConfirm: () => void;
};

export function CreatorProfileDeleteModal({
  open,
  entityType,
  preview,
  deleting,
  onClose,
  onConfirm,
}: CreatorProfileDeleteModalProps) {
  const copy = preview ? buildDeleteCopy(entityType, preview) : null;
  const confirmDisabled =
    deleting || !preview || preview.canDelete === false || !!preview?.blockReason;

  return (
    <Dialog
      open={open}
      title={copy?.title || "Delete profile?"}
      testId="creator-delete-modal"
      primaryLabel={copy?.primaryLabel || "Delete"}
      secondaryLabel="Cancel"
      danger
      closeOnPrimary={false}
      primaryLoading={deleting}
      primaryDisabled={confirmDisabled}
      onClose={onClose}
      onPrimary={onConfirm}
    >
      {!preview ? (
        <p data-testid="creator-delete-modal-loading">Preparing delete preview…</p>
      ) : (
        <div data-testid="creator-delete-modal-body">
          {preview.blockReason && (
            <p
              className="creator-delete-modal__warning"
              data-testid="creator-delete-modal-block"
            >
              {preview.blockReason}
            </p>
          )}
          <p style={{ whiteSpace: "pre-line" }}>{copy?.body}</p>
          {preview.isGlobal && preview.libraryAssetsKept && (
            <p className="creator-delete-modal__note">
              Shared Library assets will be kept; only the creator profile will be
              removed.
            </p>
          )}
        </div>
      )}
    </Dialog>
  );
}
