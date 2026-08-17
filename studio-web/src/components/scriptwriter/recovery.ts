/**
 * Scriptwriter conflict-recovery helpers (CDX-055).
 *
 * Pure decision logic shared by ScriptwriterStudio and ScriptwriterInlineEditor:
 * after a SCRIPT_CONFLICT the backend keeps the client's unsaved edit in the
 * document's recovery payload, and the fresh bundle carries it back. The editors
 * must offer a "Restore my unsaved changes" action instead of silently dropping
 * the in-progress edit. These helpers keep that logic unit-testable without a DOM.
 */
import type { SaveState } from "./types";

/** Shape of the scriptwriter studio/createDocument bundle relevant to recovery. */
export type ScriptwriterBundle = {
  document?: Record<string, unknown> | null;
  recovery?: Record<string, unknown> | null;
};

export type ConflictReloadState = {
  saveState: "recovery_available" | "save_failed";
  message: string;
};

/**
 * Decide the editor state after reloading the fresh bundle on a conflict.
 * When the bundle still carries the recovery payload, the unsaved edit was
 * preserved server-side and the editor must surface the restore action.
 */
export function conflictReloadState(bundle: ScriptwriterBundle): ConflictReloadState {
  if (bundle.recovery) {
    return {
      saveState: "recovery_available",
      message: "Document was updated elsewhere. Your recent edit was kept - restore it to reapply.",
    };
  }
  return {
    saveState: "save_failed",
    message:
      "Document was updated elsewhere. Reloaded latest version - your recent edit was not saved. Please reapply.",
  };
}

/** The restore affordance is offered only while a recovery payload is available. */
export function shouldOfferRecovery(saveState: SaveState): boolean {
  return saveState === "recovery_available";
}

export const RECOVERY_RESTORED_MESSAGE = "Your unsaved changes were restored.";
export const RECOVERY_RESTORE_FAILED_MESSAGE = "Failed to restore unsaved changes.";
