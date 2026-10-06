import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { pollJob } from "./pollJob";

type TestJob = { id: string; status: string };

const waitForTimers = async (ms: number) => {
  await vi.advanceTimersByTimeAsync(ms);
  await vi.runAllTicks();
};

describe("pollJob", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    if (typeof globalThis.window === "undefined") {
      // @ts-expect-error - provide a browser-like global for tests
      globalThis.window = globalThis;
    }
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("fires an immediate request on start", async () => {
    const getJob = vi.fn().mockResolvedValue({ id: "j1", status: "running" });
    pollJob("j1", { getJob, intervalMs: 1500, onUpdate: () => {} });

    await vi.runAllTicks();
    expect(getJob).toHaveBeenCalledTimes(1);
  });

  it("polls once per interval while the job is non-terminal", async () => {
    const getJob = vi.fn().mockResolvedValue({ id: "j1", status: "running" });
    pollJob("j1", { getJob, intervalMs: 1500, onUpdate: () => {} });

    // Immediate tick fires once on start.
    await vi.runAllTicks();
    expect(getJob).toHaveBeenCalledTimes(1);
    expect(getJob).toHaveBeenLastCalledWith("j1");

    // First interval tick.
    await waitForTimers(1500);
    expect(getJob).toHaveBeenCalledTimes(2);

    // Second interval tick.
    await waitForTimers(1500);
    expect(getJob).toHaveBeenCalledTimes(3);
  });

  it.each([
    ["done"],
    ["failed"],
    ["cancelled"],
    ["canceled"],
    ["timed_out"],
  ])("stops polling when the job reaches %s", async (status) => {
    const getJob = vi
      .fn()
      .mockResolvedValueOnce({ id: "j1", status: "running" })
      .mockResolvedValue({ id: "j1", status });
    const onUpdate = vi.fn();
    const onTerminal = vi.fn();

    pollJob<TestJob>("j1", {
      getJob,
      intervalMs: 1500,
      onUpdate,
      onTerminal,
    });

    // Immediate tick returns "running".
    await vi.runAllTicks();
    expect(getJob).toHaveBeenCalledTimes(1);
    expect(onUpdate).toHaveBeenCalledWith(expect.objectContaining({ status: "running" }));
    expect(onTerminal).not.toHaveBeenCalled();

    // First interval tick returns the terminal status → stops.
    await waitForTimers(1500);
    expect(getJob).toHaveBeenCalledTimes(2);
    expect(onUpdate).toHaveBeenLastCalledWith(expect.objectContaining({ status }));
    expect(onTerminal).toHaveBeenCalledWith(expect.objectContaining({ status }), status);

    // No more polling after terminal.
    await waitForTimers(3000);
    expect(getJob).toHaveBeenCalledTimes(2);
    expect(onUpdate).toHaveBeenCalledTimes(2);
  });

  it("stops polling when the returned cleanup function is called", async () => {
    const getJob = vi.fn().mockResolvedValue({ id: "j1", status: "running" });
    const stop = pollJob("j1", {
      getJob,
      intervalMs: 1500,
      onUpdate: () => {},
    });

    // Immediate tick.
    await vi.runAllTicks();
    expect(getJob).toHaveBeenCalledTimes(1);

    stop();
    await waitForTimers(3000);
    expect(getJob).toHaveBeenCalledTimes(1);
  });

  it("keeps polling after a failed getJob request", async () => {
    const getJob = vi
      .fn()
      .mockRejectedValueOnce(new Error("network"))
      .mockResolvedValue({ id: "j1", status: "running" });
    const onUpdate = vi.fn();

    pollJob("j1", { getJob, intervalMs: 1500, onUpdate });

    // Immediate tick fails.
    await vi.runAllTicks();
    expect(getJob).toHaveBeenCalledTimes(1);
    expect(onUpdate).not.toHaveBeenCalled();

    // First interval succeeds.
    await waitForTimers(1500);
    expect(getJob).toHaveBeenCalledTimes(2);
    expect(onUpdate).toHaveBeenCalledWith(expect.objectContaining({ status: "running" }));
  });

  it("does not call onUpdate for a stale response after cleanup", async () => {
    let resolveJob: ((job: TestJob) => void) | null = null;
    const getJob = vi.fn().mockImplementation(() => {
      return new Promise<TestJob>((resolve) => {
        resolveJob = resolve;
      });
    });
    const onUpdate = vi.fn();

    const stop = pollJob("j1", { getJob, intervalMs: 1500, onUpdate });

    // Immediate tick is pending (not resolved yet).
    await vi.runAllTicks();
    expect(getJob).toHaveBeenCalledTimes(1);
    stop();

    resolveJob?.({ id: "j1", status: "done" });
    await vi.runAllTicks();
    expect(onUpdate).not.toHaveBeenCalled();
  });
});
