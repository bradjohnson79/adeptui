import { describe, expect, it } from "vitest";
import {
  FILM_TIMELINE_ACTIVE_STATUSES,
  filmTimelineCancelPresentation,
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

  it("keeps Cancel armed during API preparation and hides it once generation starts", () => {
    const preparing = filmTimelineCancelPresentation([
      { status: "generating", generationMetadata: { renderStatus: { apiPhase: "preparing" } } },
    ]);
    expect(preparing).toEqual({ visible: true, armed: true });

    const generating = filmTimelineCancelPresentation([
      { status: "generating", generationMetadata: { renderStatus: { apiPhase: "generating" } } },
    ]);
    expect(generating).toEqual({ visible: false, armed: false });
    expect(filmTimelineHasCancellableJob([
      { status: "generating", generationMetadata: { renderStatus: { apiPhase: "generating" } } },
    ])).toBe(false);

    const done = filmTimelineCancelPresentation([{ status: "completed" }]);
    expect(done).toEqual({ visible: true, armed: false });
  });
});
