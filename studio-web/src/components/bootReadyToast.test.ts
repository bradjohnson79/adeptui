import { describe, expect, it } from "vitest";
import { BOOT_READY_TOAST_MS, bootReadyToastVisible } from "./bootReadyToast";

describe("startup readiness notice", () => {
  const shownAt = 1_000;

  it("stays visible until the creator closes it", () => {
    expect(bootReadyToastVisible({
      gaugeVisible: false,
      verdict: "GO",
      dismissed: false,
      now: shownAt + 500,
      shownAt,
    })).toBe(true);
    expect(bootReadyToastVisible({
      gaugeVisible: false,
      verdict: "GO",
      dismissed: true,
      now: shownAt + 500,
      shownAt,
    })).toBe(false);
  });

  it("disappears on its own after about six seconds", () => {
    expect(bootReadyToastVisible({
      gaugeVisible: false,
      verdict: "GO",
      dismissed: false,
      now: shownAt + BOOT_READY_TOAST_MS - 1,
      shownAt,
    })).toBe(true);
    expect(bootReadyToastVisible({
      gaugeVisible: false,
      verdict: "GO",
      dismissed: false,
      now: shownAt + BOOT_READY_TOAST_MS,
      shownAt,
    })).toBe(false);
  });

  it("does not return after a later status poll or while the gauge is still open", () => {
    expect(bootReadyToastVisible({
      gaugeVisible: false,
      verdict: "GO",
      dismissed: true,
      now: shownAt + 30_000,
      shownAt,
    })).toBe(false);
    expect(bootReadyToastVisible({
      gaugeVisible: true,
      verdict: "GO",
      dismissed: false,
      now: shownAt + 500,
      shownAt,
    })).toBe(false);
    expect(bootReadyToastVisible({
      gaugeVisible: false,
      verdict: "NO-GO",
      dismissed: false,
      now: shownAt + 500,
      shownAt,
    })).toBe(false);
  });
});
