import { describe, expect, it, vi } from "vitest";

// The hook needs a DOM render harness, which this repo does not ship
// (no jsdom/RTL). These node-env tests cover the failure-honesty contract of
// the "Use Anyway" override that the hook's catch path actually uses.
vi.mock("../../../api", () => ({ api: {} }));

import {
  ERS_MAP_SCOPED_STATE_KEYS,
  emptyErsMapScopedState,
  useAnywayFailure,
} from "./useErsGeneration";

describe("FE-010 Use Anyway failure honesty", () => {
  it("maps an Error rejection to a creator-facing message plus raw detail", () => {
    const failure = useAnywayFailure(new Error("override rejected"));
    expect(failure.error).toBe("Use Anyway failed — override rejected");
    expect(failure.errorDetail).toBe("override rejected");
  });

  it("maps a non-Error rejection (string) without crashing", () => {
    const failure = useAnywayFailure("network reset");
    expect(failure.error).toContain("Use Anyway failed");
    expect(failure.errorDetail).toBe("network reset");
  });

  it("peels backend error prefixes through the shared ERS strip logic", () => {
    const failure = useAnywayFailure(new Error("HANDLER_ERROR: boom"));
    expect(failure.error).toBe("Use Anyway failed — boom");
    expect(failure.errorDetail).toBe("HANDLER_ERROR: boom");
  });
});

describe("CDX-022 ERS state scoped to the active Spatial Map", () => {
  it("declares composite, sheet, and phase as map-scoped keys", () => {
    expect(ERS_MAP_SCOPED_STATE_KEYS).toEqual(
      expect.arrayContaining(["compositeAssetId", "sheetId", "phase"]),
    );
  });

  it("clears every map-scoped key to its idle default so the previous map's ERS never shows as current", () => {
    const reset = emptyErsMapScopedState();
    expect(reset.phase).toBe("idle");
    expect(reset.busy).toBe(false);
    expect(reset.compositeAssetId).toBeNull();
    expect(reset.sheetId).toBeNull();
    expect(reset.executionId).toBeNull();
    expect(reset.jobId).toBeNull();
    expect(reset.error).toBeNull();
    expect(reset.errorDetail).toBeNull();
    expect(reset.zombie).toBe(false);
    expect(reset.elapsedSec).toBe(0);
    expect(reset.semanticGate).toBeNull();
    expect(reset.gateOverride).toBe(false);
    expect(reset.model).toEqual({ model: "", sourceKind: null });
    expect(reset.progress).toMatchObject({ status: "idle", finalAssetId: null });
  });

  it("keeps every key in the returned state covered by the reset slice", () => {
    const reset = emptyErsMapScopedState();
    for (const key of ERS_MAP_SCOPED_STATE_KEYS) {
      expect(reset).toHaveProperty(key);
    }
    // Generator choice is deliberately NOT map-scoped (survives remounts).
    expect(ERS_MAP_SCOPED_STATE_KEYS).not.toContain("selectedGenerator");
  });
});
