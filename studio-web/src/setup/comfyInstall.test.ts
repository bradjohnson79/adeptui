import { describe, expect, it } from "vitest";
import { comfyInstallCommand, comfyInstallRequired } from "./comfyInstall";

describe("ComfyUI terminal install", () => {
  it("uses one pasteable command for each platform", () => {
    expect(comfyInstallCommand("windows")).toBe("pip install comfy-cli; comfy install");
    expect(comfyInstallCommand("linux")).toBe("pip install comfy-cli && comfy install");
    expect(comfyInstallCommand("mac")).toBe("pip install comfy-cli && comfy install");
  });

  it("asks for ComfyUI only when a local profile still needs it", () => {
    expect(comfyInstallRequired("local", [], false)).toBe(true);
    expect(comfyInstallRequired("local", [], true)).toBe(false);
    expect(comfyInstallRequired("hybrid", ["zimage_models"], false)).toBe(true);
    expect(comfyInstallRequired("hybrid", [], false)).toBe(false);
    expect(comfyInstallRequired("api", ["zimage_models"], false)).toBe(false);
  });
});
