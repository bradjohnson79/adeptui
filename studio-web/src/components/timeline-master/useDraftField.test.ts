import { describe, expect, it } from "vitest";
import { shouldAdoptExternalDraft } from "./useDraftField";

describe("shouldAdoptExternalDraft", () => {
  it("keeps a flushed prompt when the parent still has the previous text", () => {
    expect(
      shouldAdoptExternalDraft({
        focused: false,
        dirty: false,
        latest: "Korri holds the thermos.",
        persisted: "Korri holds the thermos.",
        externalSeen: "Old prompt.",
        externalValue: "Old prompt.",
      }),
    ).toBe(false);
  });

  it("accepts the parent once it echoes the saved prompt", () => {
    expect(
      shouldAdoptExternalDraft({
        focused: false,
        dirty: false,
        latest: "Korri holds the thermos.",
        persisted: "Korri holds the thermos.",
        externalSeen: "Old prompt.",
        externalValue: "Korri holds the thermos.",
      }),
    ).toBe(false);
  });

  it("accepts a real external change when the draft was not edited", () => {
    expect(
      shouldAdoptExternalDraft({
        focused: false,
        dirty: false,
        latest: "Old prompt.",
        persisted: "Old prompt.",
        externalSeen: "Old prompt.",
        externalValue: "Server prompt.",
      }),
    ).toBe(true);
  });
});
