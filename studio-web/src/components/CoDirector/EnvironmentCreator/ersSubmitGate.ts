/**
 * ERS Edit modal Submit readiness — instant local snapshot capture.
 * Submit = save overlay to master + bake composite + SS-N + close.
 * NEVER invokes fal / GPT / Kie / imagegen / ERS generation pipeline.
 * Legend panel Save is a different action (persist, stay in editor).
 */

export type ErsSubmitSources = {
  editPrompt: string;
  hasMask: boolean;
  /** Drawing vectors, numbered/spatial markers, or text labels on the sheet. */
  hasDrawing: boolean;
  /** Live Legend labels/colors/position differ from last Save commit. */
  legendDirty: boolean;
};

export type ErsSubmitPlan =
  | { kind: "empty"; userMessage: string }
  | { kind: "snapshot_capture"; feedback: string };

export const ERS_SUBMIT_EMPTY_MSG = "There's nothing to submit yet.";
export const ERS_SUBMIT_SNAPSHOT_FEEDBACK = "Snapshot captured.";
/** @deprecated retained for tests/compat — Submit no longer requires a prompt. */
export const ERS_SUBMIT_PROMPT_REQUIRED_MSG = "Add a short description of what you want changed.";
/** @deprecated retained for tests/compat — annotation-only path folded into snapshot capture. */
export const ERS_SUBMIT_ANNOTATION_FEEDBACK = "Legend and spatial annotations saved.";
/** @deprecated retained for tests/compat — image-edit path removed from Submit. */
export const ERS_SUBMIT_EDIT_FEEDBACK = "The edit has been submitted.";

/** True when Submit has annotation/overlay work to capture as a snapshot. */
export function ersSubmitHasWork(sources: ErsSubmitSources): boolean {
  return Boolean(sources.hasDrawing || sources.legendDirty);
}

/**
 * Decide Submit path.
 * Instant snapshot capture only — prompt/mask alone do not enqueue image generation.
 */
export function planErsSubmit(sources: ErsSubmitSources): ErsSubmitPlan {
  const hasAnnotation = sources.legendDirty || sources.hasDrawing;
  if (!hasAnnotation) {
    return { kind: "empty", userMessage: ERS_SUBMIT_EMPTY_MSG };
  }
  return { kind: "snapshot_capture", feedback: ERS_SUBMIT_SNAPSHOT_FEEDBACK };
}

/**
 * After Submit outcome: close Edit/Inpaint only on verified snapshot success.
 * Failures keep the modal open so unsaved work can be retried.
 * Legend panel Save is a different action and never uses this.
 */
export type ErsSubmitCloseInput = {
  outcome: "success" | "failure";
  planKind: "snapshot_capture" | "annotation_only" | "image_edit";
  /** Snapshot capture accepted (baked asset + SS-N record). */
  snapshotAccepted?: boolean;
  /** @deprecated image-edit acceptance — Submit no longer enqueues jobs. */
  jobAccepted?: boolean;
};

export type ErsSubmitCloseDecision =
  | { close: true; reason: "snapshot_captured" | "annotation_persisted" | "image_edit_accepted" }
  | { close: false; reason: "failure" | "not_accepted" };

export function planErsSubmitClose(input: ErsSubmitCloseInput): ErsSubmitCloseDecision {
  if (input.outcome === "failure") {
    return { close: false, reason: "failure" };
  }
  if (input.planKind === "snapshot_capture") {
    if (input.snapshotAccepted) {
      return { close: true, reason: "snapshot_captured" };
    }
    return { close: false, reason: "not_accepted" };
  }
  // Legacy kinds kept for unit-compat; FE Submit no longer uses them.
  if (input.planKind === "annotation_only") {
    return { close: true, reason: "annotation_persisted" };
  }
  if (input.jobAccepted) {
    return { close: true, reason: "image_edit_accepted" };
  }
  return { close: false, reason: "not_accepted" };
}

/** Normalize provider/job status for EC pending banner (legacy image-edit). */
export function ersEditPendingStatusLabel(status: string | null | undefined): string {
  const st = String(status || "").trim().toLowerCase();
  if (!st || st === "queued" || st === "pending" || st === "accepted") return "pending";
  if (st === "running" || st === "processing" || st === "in_progress" || st === "started") {
    return "running";
  }
  if (st === "completed" || st === "succeeded" || st === "success" || st === "done") {
    return "completed";
  }
  if (st === "failed" || st === "error" || st === "cancelled" || st === "canceled") {
    return st === "canceled" ? "cancelled" : st;
  }
  return st;
}
