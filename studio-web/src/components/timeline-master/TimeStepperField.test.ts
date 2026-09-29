import { describe, expect, it } from "vitest";
import { commitTypedTime, formatTime } from "./TimeStepperField";

describe("commitTypedTime", () => {
  it("keeps a whole number the creator types instead of folding it into decimals", () => {
    expect(commitTypedTime("45", 44.99, 0.15, 0.01)).toBe(45);
    expect(commitTypedTime("15", 0.15, 0.15, 0.01)).toBe(15);
    expect(formatTime(45, 0.01)).toBe("45.00");
  });

  it("keeps a two-digit length such as 45 when the stored value is a single digit", () => {
    expect(commitTypedTime("45", 4, 0.1, 0.1)).toBe(45);
    expect(commitTypedTime("4", 15, 0.1, 0.1)).toBe(4);
    expect(commitTypedTime("1.5", 1, 0.1, 0.1, 2)).toBe(1.5);
  });

  it("does not snap an empty box to the minimum while the number is unfinished", () => {
    expect(commitTypedTime("", 12, 0.15, 0.01)).toBe(12);
    expect(commitTypedTime(".", 12, 0.15, 0.01)).toBe(12);
    expect(commitTypedTime("4.", 12, 0.15, 0.01)).toBe(4);
  });
});
