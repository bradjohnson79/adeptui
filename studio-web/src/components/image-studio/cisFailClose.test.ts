import { describe, expect, it } from "vitest";
import { CIS_QUEUED_NO_HYDRATE_MS, staleCisQueuedNoHydrate } from "./cisFailClose";

describe("CIS queued-no-hydrate fail-close", () => {
  it("fails a queued 0% job after 30s", () => {
    const started = 1_000;
    expect(staleCisQueuedNoHydrate({ status: "queued", progress: 0 }, started, started + CIS_QUEUED_NO_HYDRATE_MS)).toBe(
      true,
    );
  });

  it("does not fail when progress hydrates", () => {
    const started = 1_000;
    expect(
      staleCisQueuedNoHydrate({ status: "queued", progress: 0.2 }, started, started + CIS_QUEUED_NO_HYDRATE_MS),
    ).toBe(false);
  });
});
