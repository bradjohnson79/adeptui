import { describe, expect, it } from "vitest";
import { createSpinImagesDisabledReason, spinViewIsFailed, spinViewIsPending } from "./spinCameraGating";
import type { SpinCameraPlacement } from "./types";

function provider(id: string, executable = true) {
  return { id, label: id, executable };
}

function camera(): SpinCameraPlacement {
  return { id: "spin-1", x: 0.1, z: -0.2 };
}

describe("Create Spin Images gating", () => {
  it("requires a background atlas", () => {
    const reason = createSpinImagesDisabledReason(camera(), { centered: true }, "gpt-image-2", [provider("gpt-image-2")], false);
    expect(reason).toBe("Create or assign an Atlas Shot before generating spin views.");
  });

  it("requires the spin camera to be placed", () => {
    const reason = createSpinImagesDisabledReason(null, null, "gpt-image-2", [provider("gpt-image-2")], true);
    expect(reason).toBe("Place the Spin Camera on the map first.");
  });

  it("requires the spin camera to be centered", () => {
    const reason = createSpinImagesDisabledReason(camera(), { centered: false }, "gpt-image-2", [provider("gpt-image-2")], true);
    expect(reason).toBe("Move the Spin Camera closer to the scene center.");
  });

  it("requires a provider to be selected", () => {
    const reason = createSpinImagesDisabledReason(camera(), { centered: true }, "", [provider("gpt-image-2")], true);
    expect(reason).toBe("Choose a cloud image generator.");
  });

  it("requires the selected provider to be executable", () => {
    const reason = createSpinImagesDisabledReason(camera(), { centered: true }, "gpt-image-2", [provider("gpt-image-2", false)], true);
    expect(reason).toBe("gpt-image-2 is not available right now.");
  });

  it("returns null when all gates pass", () => {
    const reason = createSpinImagesDisabledReason(camera(), { centered: true }, "gpt-image-2", [provider("gpt-image-2")], true);
    expect(reason).toBeNull();
  });

  it("reports missing provider when the selected id is not in the list", () => {
    const reason = createSpinImagesDisabledReason(camera(), { centered: true }, "missing", [provider("gpt-image-2")], true);
    expect(reason).toBe("Choose a cloud image generator.");
  });
});

describe("Spin view status predicates", () => {
  it("treats queued and generating as pending", () => {
    expect(spinViewIsPending("queued")).toBe(true);
    expect(spinViewIsPending("generating")).toBe(true);
    expect(spinViewIsPending("done")).toBe(false);
  });

  it("treats failed, error, cancelled as failed", () => {
    expect(spinViewIsFailed("failed")).toBe(true);
    expect(spinViewIsFailed("error")).toBe(true);
    expect(spinViewIsFailed("canceled")).toBe(true);
    expect(spinViewIsFailed("done")).toBe(false);
  });
});
