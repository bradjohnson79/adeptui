import { describe, expect, it } from "vitest";
import { deriveProductionContextStatus } from "./productionContextStatus";

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
