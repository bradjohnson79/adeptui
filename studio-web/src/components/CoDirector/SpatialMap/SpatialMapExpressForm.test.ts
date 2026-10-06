import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("Co-Director Spatial Map Express form", () => {
  const src = readFileSync(new URL("./SpatialMapExpressForm.tsx", import.meta.url), "utf8");

  it("is an API-only GPT Image 2 form with one Generate action", () => {
    expect(src).toContain("Create Spatial Map with Co-Director");
    expect(src).toContain("Atlas Engine: GPT Image 2");
    expect(src).toContain("Environment Description");
    expect(src).toContain("Select from Library");
    expect(src).toContain("Upload Reference Image");
    expect(src).toContain("Upload Spatial Map");
    expect(src).toContain("spatial-map-reference-file");
    expect(src).toContain("spatial-map-atlas-file");
    expect(src).toContain("Generate Spatial Map");
    expect(src).toContain("Use Spatial Map");
    expect(src).toContain("spatial-map-use-as-atlas");
    expect(src).toContain("Use this image as the Spatial Map");
    expect(src).toContain("HelpTip");
    expect(src).toContain("spatial-map-generate");
    expect(src).toContain("spatial-map-atlas-engine");
    expect(src).toContain("spatial-map-open-settings");
    expect(src).toContain("Open API Settings");
    expect(src).toContain('modelLine="GPT Image 2"');
    expect(src).not.toContain("spatial-map-generation-method");
    expect(src).not.toContain("spatial-map-environment-type");
    expect(src).not.toContain("Generation Method");
    expect(src).not.toContain("Environment Type");
    expect(src).not.toContain("Interior");
    expect(src).not.toContain("Exterior");
    expect(src).not.toContain('generationMethod === "local"');
    expect(src).not.toContain("LOCAL_PIPELINE_HELP");
    expect(src).not.toContain("Create Environment with Co-Director");
    expect(src).not.toContain("Reconstruct from Location Image");
    expect(src).not.toContain("Use Existing Atlas");
    expect(src).not.toContain("Create Atlas");
    expect(src).not.toMatch(/MoGe|VGGT|Qwen|FLUX|Z-Image|ControlNet|Reconstruct/);
    expect(src).not.toMatch(/>Express<|>Standard</);
  });
});
