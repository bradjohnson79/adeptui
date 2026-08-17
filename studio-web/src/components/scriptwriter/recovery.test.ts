import { describe, expect, it } from "vitest";
import {
  conflictReloadState,
  shouldOfferRecovery,
  RECOVERY_RESTORED_MESSAGE,
} from "./recovery";

/**
 * Conflict-recovery UI logic (CDX-055): when the fresh bundle carries the
 * stored recovery payload the editor must offer restore instead of silently
 * dropping the unsaved edit.
 */

describe("conflictReloadState", () => {
  it("offers recovery when the reloaded bundle carries a recovery payload", () => {
    const state = conflictReloadState({
      document: { id: "doc-1", revision: 2 },
      recovery: { html: "<p>Unsaved edit</p>", expectedRevision: 1, conflictServerRevision: 2 },
    });
    expect(state.saveState).toBe("recovery_available");
    expect(state.message).toContain("kept");
    expect(state.message).toContain("restore");
  });

  it("falls back to save_failed when the bundle has no recovery payload", () => {
    const state = conflictReloadState({ document: { id: "doc-1", revision: 2 }, recovery: null });
    expect(state.saveState).toBe("save_failed");
    expect(state.message).toContain("not saved");
  });

  it("treats a missing recovery key the same as null", () => {
    const state = conflictReloadState({ document: { id: "doc-1", revision: 2 } });
    expect(state.saveState).toBe("save_failed");
  });
});

describe("shouldOfferRecovery", () => {
  it("is true only for the recovery_available save state", () => {
    expect(shouldOfferRecovery("recovery_available")).toBe(true);
    expect(shouldOfferRecovery("save_failed")).toBe(false);
    expect(shouldOfferRecovery("saved")).toBe(false);
    expect(shouldOfferRecovery("unsaved")).toBe(false);
    expect(shouldOfferRecovery("saving")).toBe(false);
    expect(shouldOfferRecovery("conflict")).toBe(false);
  });
});

describe("recovery messaging", () => {
  it("confirms a successful restore", () => {
    expect(RECOVERY_RESTORED_MESSAGE).toContain("restored");
  });
});
