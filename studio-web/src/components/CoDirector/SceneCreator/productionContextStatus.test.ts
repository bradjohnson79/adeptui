import { describe, expect, it } from "vitest";
import { deriveIntegrityCaption, deriveProductionContextStatus } from "./productionContextStatus";

describe("deriveProductionContextStatus", () => {
  it("hides the caption when no profile is selected", () => {
    expect(
      deriveProductionContextStatus({
        selectedProfileId: "",
        requestedProfileId: "",
        fetchInFlight: false,
        productionContext: { loaded: true, handoffId: "h1" },
      }),
    ).toBe("idle");
  });

  it("stays loading until the live workspace GET finishes", () => {
    expect(
      deriveProductionContextStatus({
        selectedProfileId: "h1",
        requestedProfileId: "h1",
        fetchInFlight: true,
        productionContext: { loaded: true, handoffId: "h1" },
      }),
    ).toBe("loading");
  });

  it("shows success only after hydrate reports loaded for the requested profile", () => {
    expect(
      deriveProductionContextStatus({
        selectedProfileId: "h1",
        requestedProfileId: "h1",
        fetchInFlight: false,
        productionContext: { loaded: true, handoffId: "h1" },
      }),
    ).toBe("loaded");
  });

  it("never treats a selected id as success when hydrate failed", () => {
    expect(
      deriveProductionContextStatus({
        selectedProfileId: "h1",
        requestedProfileId: "h1",
        fetchInFlight: false,
        productionContext: { loaded: false, handoffId: "h1" },
      }),
    ).toBe("failed");
    expect(
      deriveProductionContextStatus({
        selectedProfileId: "h1",
        requestedProfileId: "h1",
        fetchInFlight: false,
        productionContext: null,
      }),
    ).toBe("failed");
  });
});

describe("deriveIntegrityCaption", () => {
  it("hides integrity when CD is idle", () => {
    expect(deriveIntegrityCaption({ cdStatus: "idle", readiness: { status: "pass" } })).toEqual({
      kind: "hidden",
    });
  });

  it("shows verified only after loaded + pass", () => {
    expect(deriveIntegrityCaption({ cdStatus: "loaded", readiness: { status: "pass" } })).toEqual({
      kind: "verified",
    });
  });

  it("never shows verified when blocked", () => {
    expect(deriveIntegrityCaption({ cdStatus: "loaded", readiness: { status: "blocked" } })).toEqual({
      kind: "blocked",
    });
  });

  it("shows advisory instead of verified when extra refs are semantic-only", () => {
    expect(
      deriveIntegrityCaption({
        cdStatus: "loaded",
        readiness: { status: "advisory", issues: [{ type: "advisory" }] },
      }),
    ).toEqual({ kind: "advisory", count: 1 });
  });

  it("never treats a dropdown-only pass as verified without loaded CD", () => {
    expect(
      deriveIntegrityCaption({
        cdStatus: "failed",
        readiness: { status: "pass" },
      }),
    ).toEqual({ kind: "hidden" });
  });

  it("uses connections copy when Layer A passed but the LLM is down", () => {
    expect(
      deriveIntegrityCaption({
        cdStatus: "loaded",
        readiness: { status: "llm_unavailable", llm: { available: false } },
      }),
    ).toEqual({ kind: "connections", llmUnavailable: true });
  });
});
