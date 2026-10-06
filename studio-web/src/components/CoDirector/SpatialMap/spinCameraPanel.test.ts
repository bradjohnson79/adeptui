import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";

const panel = readFileSync(new URL("./SpinCameraPanel.tsx", import.meta.url), "utf8");
const selector = readFileSync(new URL("./SpinProviderSelector.tsx", import.meta.url), "utf8");

describe("Spin Camera Panel UI contract", () => {
  it("shows a guidance chip when no spin camera exists", () => {
    expect(panel).toContain("Place the Spin Camera near the center of the scene before creating the ERS directional views.");
    expect(panel).toContain('data-testid="spin-camera-guidance"');
  });

  it("shows position and center status on the card", () => {
    expect(panel).toContain("data-testid=\"spin-camera-position\"");
    expect(panel).toContain("data-testid=\"spin-camera-status\"");
    expect(panel).toContain("Centered ✓");
    expect(panel).toContain("Move closer to scene center");
    expect(panel).toContain("data-testid=\"spin-camera-status-distance\"");
  });

  it("uses a live-discovered provider dropdown with executable gating", () => {
    expect(selector).toContain("data-testid=\"spin-provider-select\"");
    expect(selector).toContain("No image generators discovered");
    expect(selector).toContain("uses credits");
  });

  it("has one primary Create Spin Images action", () => {
    expect(panel).toContain("data-testid=\"spin-create-package\"");
    expect(panel).toContain("Create Spin Images");
  });

  it("renders per-view progress checklist for all five directions", () => {
    expect(panel).toContain("data-testid={`spin-progress-${direction}`}");
    expect(panel).toContain("data-testid={`spin-progress-state-${direction}`}");
    expect(panel).toContain("SPIN_VIEW_ORDER.map");
  });

  it("offers failed-view retry with paid confirmation", () => {
    expect(panel).toContain("data-testid={`spin-retry-${direction}`}");
    expect(panel).toContain("will use cloud credits. Continue?");
  });

  it("shows package version selector and ERS staleness rebuild", () => {
    expect(panel).toContain("data-testid=\"spin-package-version-select\"");
    expect(panel).toContain("Spin Package changed");
    expect(panel).toContain("data-testid=\"spin-rebuild-ers\"");
  });

  it("shows five view thumbnails with View / Open in Library / Regenerate after completion", () => {
    expect(panel).toContain("data-testid={`spin-thumb-${direction}`}");
    expect(panel).toContain("data-testid={`spin-view-${direction}`}");
    expect(panel).toContain("data-testid={`spin-open-library-${direction}`}");
    expect(panel).toContain("data-testid={`spin-regenerate-${direction}`}");
    expect(panel).toMatch(/>\s*View\s*</);
    expect(panel).toContain("Open in Library");
    expect(panel).toContain("Regenerate Direction");
  });
});

describe("Spin Camera grid marker contract", () => {
  const grid = readFileSync(new URL("./SpatialGrid.tsx", import.meta.url), "utf8");

  it("renders a distinct spin camera marker and compass overlay", () => {
    expect(grid).toContain('data-testid="spin-camera-marker"');
    expect(grid).toContain('data-testid="spin-camera-compass"');
    expect(grid).toContain('className="spatial-map__spin-compass"');
  });

  it("labels compass N/E/S/W oriented to map convention", () => {
    expect(grid).toMatch(/>\s*N\s*</);
    expect(grid).toMatch(/>\s*E\s*</);
    expect(grid).toMatch(/>\s*S\s*</);
    expect(grid).toMatch(/>\s*W\s*</);
  });
});

describe("Scene Creator Mini spin section order", () => {
  const mini = readFileSync(new URL("./SceneCreatorMini.tsx", import.meta.url), "utf8");

  it("places SPIN CAMERA REFERENCES above SCENE CAMERAS", () => {
    const spin = mini.indexOf("SPIN CAMERA REFERENCES");
    const cameras = mini.indexOf("SCENE CAMERAS");
    expect(spin).toBeGreaterThan(-1);
    expect(cameras).toBeGreaterThan(-1);
    expect(spin).toBeLessThan(cameras);
    expect(mini).toContain('data-testid="scene-creator-mini-spin-section"');
  });
});
