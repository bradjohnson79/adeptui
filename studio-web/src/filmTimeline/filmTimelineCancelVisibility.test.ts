import { describe, expect, it } from "vitest";
import {
  FILM_TIMELINE_ACTIVE_STATUSES,
  filmTimelineHasCancellableJob,
} from "./filmTimelineCancelVisibility";

describe("filmTimelineHasCancellableJob", () => {
  it("disarms Cancel when idle / empty / completed / failed / cancelled", () => {
    expect(filmTimelineHasCancellableJob(undefined)).toBe(false);
    expect(filmTimelineHasCancellableJob([])).toBe(false);
    expect(filmTimelineHasCancellableJob([{ status: "empty" }])).toBe(false);
    expect(filmTimelineHasCancellableJob([{ status: "completed" }])).toBe(false);
    expect(filmTimelineHasCancellableJob([{ status: "failed" }])).toBe(false);
    expect(filmTimelineHasCancellableJob([{ status: "cancelled" }])).toBe(false);
    expect(filmTimelineHasCancellableJob([{ status: "interrupted" }])).toBe(false);
    expect(filmTimelineHasCancellableJob([{ status: "draft" }])).toBe(false);
  });

  it("arms Cancel only for real active/queued FilmTimeline segment statuses", () => {
    for (const status of FILM_TIMELINE_ACTIVE_STATUSES) {
      expect(filmTimelineHasCancellableJob([{ status }])).toBe(true);
    }
    expect(
      filmTimelineHasCancellableJob([
        { status: "completed" },
        { status: "queued" },
      ]),
    ).toBe(true);
    expect(
      filmTimelineHasCancellableJob([
        { status: "failed" },
        { status: "cancelled" },
      ]),
    ).toBe(false);
  });
});
