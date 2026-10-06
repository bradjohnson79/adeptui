/**
 * ERS Edit modal Submit — instant snapshot capture (no provider image gen).
 */
import { describe, expect, it } from "vitest";

import {
  ERS_SUBMIT_EMPTY_MSG,
  ERS_SUBMIT_SNAPSHOT_FEEDBACK,
  ersEditPendingStatusLabel,
  ersSubmitHasWork,
  planErsSubmit,
  planErsSubmitClose,
} from "./ersSubmitGate";

const base = {
  editPrompt: "",
  hasMask: false,
  hasDrawing: false,
  legendDirty: false,
};

describe("ersSubmitHasWork", () => {
  it("is false when empty", () => {
    expect(ersSubmitHasWork(base)).toBe(false);
  });
  it("is false for prompt/mask alone (no image-gen on Submit)", () => {
    expect(ersSubmitHasWork({ ...base, editPrompt: "fix window" })).toBe(false);
    expect(ersSubmitHasWork({ ...base, hasMask: true })).toBe(false);
  });
  it("is true for Legend / spatial annotation sources", () => {
    expect(ersSubmitHasWork({ ...base, hasDrawing: true })).toBe(true);
    expect(ersSubmitHasWork({ ...base, legendDirty: true })).toBe(true);
  });
});

describe("planErsSubmit", () => {
  it("A Legend-only -> snapshot_capture", () => {
    const plan = planErsSubmit({ ...base, legendDirty: true });
    expect(plan).toEqual({ kind: "snapshot_capture", feedback: ERS_SUBMIT_SNAPSHOT_FEEDBACK });
  });
  it("B Spatial markers only -> snapshot_capture", () => {
    const plan = planErsSubmit({ ...base, hasDrawing: true });
    expect(plan.kind).toBe("snapshot_capture");
  });
  it("C Legend + markers -> snapshot_capture", () => {
    const plan = planErsSubmit({ ...base, legendDirty: true, hasDrawing: true });
    expect(plan.kind).toBe("snapshot_capture");
  });
  it("D Prompt-only -> empty (no image gen on Submit)", () => {
    const plan = planErsSubmit({ ...base, editPrompt: "replace window with doorway" });
    expect(plan).toEqual({ kind: "empty", userMessage: ERS_SUBMIT_EMPTY_MSG });
  });
  it("E Mixed Legend+markers+prompt -> snapshot_capture (prompt ignored for gen)", () => {
    const plan = planErsSubmit({
      ...base,
      editPrompt: "remove chair",
      legendDirty: true,
      hasDrawing: true,
    });
    expect(plan.kind).toBe("snapshot_capture");
  });
  it("F Empty -> empty message", () => {
    const plan = planErsSubmit(base);
    expect(plan).toEqual({ kind: "empty", userMessage: ERS_SUBMIT_EMPTY_MSG });
  });
  it("mask without prompt -> empty (no image gen)", () => {
    const plan = planErsSubmit({ ...base, hasMask: true });
    expect(plan.kind).toBe("empty");
  });
  it("mask + prompt -> empty (Submit does not enqueue providers)", () => {
    expect(planErsSubmit({ ...base, hasMask: true, editPrompt: "fix door" }).kind).toBe("empty");
  });
});

describe("planErsSubmitClose", () => {
  it("Snapshot success -> close", () => {
    expect(
      planErsSubmitClose({
        outcome: "success",
        planKind: "snapshot_capture",
        snapshotAccepted: true,
      }),
    ).toEqual({ close: true, reason: "snapshot_captured" });
  });
  it("Snapshot success without acceptance -> stay open", () => {
    expect(
      planErsSubmitClose({
        outcome: "success",
        planKind: "snapshot_capture",
        snapshotAccepted: false,
      }),
    ).toEqual({ close: false, reason: "not_accepted" });
  });
  it("Forced failure -> stay open", () => {
    expect(
      planErsSubmitClose({ outcome: "failure", planKind: "snapshot_capture", snapshotAccepted: true }),
    ).toEqual({ close: false, reason: "failure" });
  });
  it("Legacy annotation_only success still closes", () => {
    expect(
      planErsSubmitClose({ outcome: "success", planKind: "annotation_only" }),
    ).toEqual({ close: true, reason: "annotation_persisted" });
  });
});

describe("ersEditPendingStatusLabel", () => {
  it("maps queued/accepted to pending and processing to running", () => {
    expect(ersEditPendingStatusLabel("queued")).toBe("pending");
    expect(ersEditPendingStatusLabel("accepted")).toBe("pending");
    expect(ersEditPendingStatusLabel("processing")).toBe("running");
    expect(ersEditPendingStatusLabel("succeeded")).toBe("completed");
    expect(ersEditPendingStatusLabel("failed")).toBe("failed");
  });
});
