import { describe, expect, it } from "vitest";
import { authoredScenePromptFromTimedPrompts } from "./authoredScenePrompt";

describe("authoredScenePromptFromTimedPrompts", () => {
  it("uses written Timed Prompt text and skips continuation stubs", () => {
    const text = authoredScenePromptFromTimedPrompts({
      batchBlocks: [
        {
          order: 0,
          promptSegments: [{ start: 0, text: "Korri walks into the coffee house." }],
        },
        {
          order: 1,
          promptSegments: [
            { start: 0, text: "[CONTINUATION window 2 | scene time 15s-30s] Continue from the prior window." },
          ],
        },
      ],
    });
    expect(text).toBe("Korri walks into the coffee house.");
  });

  it("joins later written prompts in window order", () => {
    const text = authoredScenePromptFromTimedPrompts({
      batchBlocks: [
        { order: 1, promptSegments: [{ start: 0, text: "Second beat." }] },
        { order: 0, promptSegments: [{ start: 0, text: "Opening beat." }] },
      ],
    });
    expect(text).toBe("Opening beat.\n\nSecond beat.");
  });

  it("is empty when every Timed Prompt is blank or a continuation", () => {
    expect(authoredScenePromptFromTimedPrompts(null)).toBe("");
    expect(
      authoredScenePromptFromTimedPrompts({
        batchBlocks: [{ order: 0, promptSegments: [{ start: 0, text: "  " }] }],
      }),
    ).toBe("");
  });
});
