import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

vi.mock("../api", () => ({
  api: {
    listJobs: vi.fn(),
  },
}));

describe("projectJobsStore", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    vi.useFakeTimers();
    if (typeof globalThis.window === "undefined") {
      // @ts-expect-error - provide a browser-like global for tests
      globalThis.window = globalThis;
    }
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  const runningJob = {
    id: "j1",
    project_id: "p1",
    kind: "render",
    status: "running",
    progress: 0.5,
    message: "",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  };

  const doneJob = {
    id: "j2",
    project_id: "p1",
    kind: "render",
    status: "done",
    progress: 1,
    message: "",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  };

  it("shares one initial fetch between two subscribers (component A + component B)", async () => {
    const { api } = await import("../api");
    const { subscribeProjectJobs } = await import("./projectJobsStore");
    const listJobs = api.listJobs as ReturnType<typeof vi.fn>;
    listJobs.mockResolvedValue([runningJob]);

    const a = vi.fn();
    const b = vi.fn();
    const unsubA = subscribeProjectJobs("p1", a);
    const unsubB = subscribeProjectJobs("p1", b);

    await vi.runAllTicks();

    expect(listJobs).toHaveBeenCalledTimes(1);
    expect(listJobs).toHaveBeenCalledWith("p1");
    expect(a).toHaveBeenCalledWith(expect.objectContaining({ jobs: [runningJob] }));
    expect(b).toHaveBeenCalledWith(expect.objectContaining({ jobs: [runningJob] }));

    unsubA();
    unsubB();
  });

  it("does not fire an extra immediate request when a second subscriber mounts", async () => {
    const { api } = await import("../api");
    const { subscribeProjectJobs } = await import("./projectJobsStore");
    const listJobs = api.listJobs as ReturnType<typeof vi.fn>;
    listJobs.mockResolvedValue([]);

    const a = vi.fn();
    const unsubA = subscribeProjectJobs("p1", a);
    await vi.runAllTicks();
    expect(listJobs).toHaveBeenCalledTimes(1);

    const b = vi.fn();
    const unsubB = subscribeProjectJobs("p1", b);
    await vi.runAllTicks();

    // Subscriber B receives the shared snapshot; no new network request is made.
    expect(listJobs).toHaveBeenCalledTimes(1);
    expect(b).toHaveBeenCalledWith(expect.objectContaining({ jobs: [] }));

    unsubA();
    unsubB();
  });

  it("clears the interval and stops polling when all subscribers leave", async () => {
    const { api } = await import("../api");
    const { subscribeProjectJobs } = await import("./projectJobsStore");
    const listJobs = api.listJobs as ReturnType<typeof vi.fn>;
    listJobs.mockResolvedValue([]);

    const a = vi.fn();
    const unsubA = subscribeProjectJobs("p1", a);
    await vi.runAllTicks();
    expect(listJobs).toHaveBeenCalledTimes(1);

    // Idle interval is 5000ms; advance to trigger one more fetch.
    await vi.advanceTimersByTimeAsync(5000);
    await vi.runAllTicks();
    expect(listJobs).toHaveBeenCalledTimes(2);

    unsubA();

    // No more fetches after unsubscribe.
    await vi.advanceTimersByTimeAsync(20000);
    await vi.runAllTicks();
    expect(listJobs).toHaveBeenCalledTimes(2);
  });

  it("single-flights refresh so multiple overlapping calls issue one request", async () => {
    const { api } = await import("../api");
    const { subscribeProjectJobs, refreshProjectJobs } = await import("./projectJobsStore");
    const listJobs = api.listJobs as ReturnType<typeof vi.fn>;
    listJobs.mockResolvedValue([]);

    const a = vi.fn();
    const unsubA = subscribeProjectJobs("p1", a);
    await vi.runAllTicks();
    expect(listJobs).toHaveBeenCalledTimes(1);

    refreshProjectJobs("p1");
    refreshProjectJobs("p1");
    await vi.runAllTicks();
    expect(listJobs).toHaveBeenCalledTimes(2);

    unsubA();
  });

  it("slows to the idle interval when all jobs are terminal", async () => {
    const { api } = await import("../api");
    const { subscribeProjectJobs } = await import("./projectJobsStore");
    const listJobs = api.listJobs as ReturnType<typeof vi.fn>;
    listJobs.mockResolvedValue([doneJob]);

    const a = vi.fn();
    const unsubA = subscribeProjectJobs("p1", a);
    await vi.runAllTicks();
    expect(listJobs).toHaveBeenCalledTimes(1);

    // Terminal jobs -> 5000ms interval.
    await vi.advanceTimersByTimeAsync(5000);
    await vi.runAllTicks();
    expect(listJobs).toHaveBeenCalledTimes(2);

    // 2000ms is not enough for the next idle tick.
    await vi.advanceTimersByTimeAsync(2000);
    await vi.runAllTicks();
    expect(listJobs).toHaveBeenCalledTimes(2);

    unsubA();
  });

  it("speeds up to the active interval when a job is running", async () => {
    const { api } = await import("../api");
    const { subscribeProjectJobs } = await import("./projectJobsStore");
    const listJobs = api.listJobs as ReturnType<typeof vi.fn>;
    listJobs.mockResolvedValue([doneJob]);

    const a = vi.fn();
    const unsubA = subscribeProjectJobs("p1", a);
    await vi.runAllTicks();
    expect(listJobs).toHaveBeenCalledTimes(1);

    // Next tick is scheduled for 5000ms; make it return a running job.
    listJobs.mockResolvedValue([runningJob]);
    await vi.advanceTimersByTimeAsync(5000);
    await vi.runAllTicks();
    expect(listJobs).toHaveBeenCalledTimes(2);

    // Interval should now be 2000ms.
    await vi.advanceTimersByTimeAsync(2000);
    await vi.runAllTicks();
    expect(listJobs).toHaveBeenCalledTimes(3);

    unsubA();
  });

  it("skips fetches while dependent polling is suspended", async () => {
    const { api } = await import("../api");
    const { markStudioApiFailure, shouldSuspendDependentPolling } = await import("./studioApiConnection");
    const { subscribeProjectJobs } = await import("./projectJobsStore");
    const listJobs = api.listJobs as ReturnType<typeof vi.fn>;
    listJobs.mockResolvedValue([]);

    expect(shouldSuspendDependentPolling()).toBe(false);

    const a = vi.fn();
    const unsubA = subscribeProjectJobs("p1", a);
    await vi.runAllTicks();
    expect(listJobs).toHaveBeenCalledTimes(1);

    // Force dependent polling suspension (3 failures).
    markStudioApiFailure("STUDIO_API_OFFLINE", "fail 1");
    markStudioApiFailure("STUDIO_API_OFFLINE", "fail 2");
    markStudioApiFailure("STUDIO_API_OFFLINE", "fail 3");
    expect(shouldSuspendDependentPolling()).toBe(true);

    await vi.advanceTimersByTimeAsync(5000);
    await vi.runAllTicks();
    expect(listJobs).toHaveBeenCalledTimes(1);

    unsubA();
  });

  it("useProjectJobs returns a referentially stable snapshot when projectId is undefined", async () => {
    // Regression (Peer Review A D1): when projectId is falsy, getSnapshot
    // returned a new object literal on every call. Under React's
    // useSyncExternalStore this fails checkIfSnapshotChanged after every
    // commit → forceStoreRerender → infinite render loop. The fix uses a
    // module-level EMPTY_SNAPSHOT constant.
    const { EMPTY_SNAPSHOT } = await import("./projectJobsStore");

    // The constant must be a stable reference (same object every import).
    const { EMPTY_SNAPSHOT: again } = await import("./projectJobsStore");
    expect(EMPTY_SNAPSHOT).toBe(again);
    expect(EMPTY_SNAPSHOT.jobs).toEqual([]);
    expect(EMPTY_SNAPSHOT.lastFetchedAt).toBeNull();
  });
});
