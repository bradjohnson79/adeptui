import { describe, expect, it } from "vitest";
import { proposeFromCommand } from "./magiCommandParse";

describe("MAGI command parse post-production", () => {
  it("maps cinematic grade to color finishing", () => {
    const proposal = proposeFromCommand("Give this a cinematic grade");
    expect(proposal?.operation).toBe("magi.color.apply");
    expect(proposal?.requiresMask).toBe(false);
  });

  it("maps upscale speech to finishing upscale", () => {
    const proposal = proposeFromCommand("Upscale this to 2K");
    expect(proposal?.actionId).toBe("upscale");
    expect(proposal?.requiresMask).toBe(false);
  });

  it("refuses inpaint and re-take production commands", () => {
    expect(proposeFromCommand("inpaint the background")).toBeNull();
    expect(proposeFromCommand("Re-take this part because Korri said the wrong line")).toBeNull();
    expect(proposeFromCommand("mask repair this frame")).toBeNull();
  });

  it("does not default unknown speech to inpaint", () => {
    expect(proposeFromCommand("hello MAGI")).toBeNull();
  });

  it("maps professional finish and hard audio overrides", () => {
    expect(proposeFromCommand("Finish this scene professionally")?.operation).toBe("magi.propose_finish");
    expect(proposeFromCommand("No music")?.operation).toBe("magi.music.none");
    expect(proposeFromCommand("Keep original audio untouched")?.operation).toBe("magi.audio.keep_original");
  });
});
