import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("local generation attention", () => {
  it("uses creator language and mounts in chrome", () => {
    const store = readFileSync(new URL("./localGenerationAttention.ts", import.meta.url), "utf8");
    const app = readFileSync(new URL("../App.tsx", import.meta.url), "utf8");
    expect(store).toContain(
      "A local generation is in progress. Finish or cancel it before starting another.",
    );
    expect(store).toContain("getLocalGeneration");
    expect(store.toLowerCase()).not.toMatch(/comfy|mutex|uvicorn/);
    expect(app).toContain("LocalGenerationAttentionBanner");
    expect(app).toContain("ensureLocalGenerationMonitor");
  });
});
