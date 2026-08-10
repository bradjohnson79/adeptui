import { describe, it, expect, vi, beforeEach } from "vitest";

describe("requestCache", () => {
  let cachedFetch: typeof import("../requestCache").cachedFetch;
  let clearAllCache: typeof import("../requestCache").clearAllCache;

  beforeEach(async () => {
    const mod = await import("../requestCache");
    cachedFetch = mod.cachedFetch;
    clearAllCache = mod.clearAllCache;
    clearAllCache();
    vi.useFakeTimers();
  });

  it("deduplicates concurrent requests (single flight)", async () => {
    let callCount = 0;
    const fetcher = vi.fn().mockImplementation(async () => {
      callCount++;
      return { data: "ok" };
    });
    const [r1, r2, r3] = await Promise.all([
      cachedFetch("GET", "/api/health", fetcher, 10_000),
      cachedFetch("GET", "/api/health", fetcher, 10_000),
      cachedFetch("GET", "/api/health", fetcher, 10_000),
    ]);
    expect(r1).toEqual({ data: "ok" });
    expect(r2).toEqual({ data: "ok" });
    expect(r3).toEqual({ data: "ok" });
    expect(callCount).toBe(1);
  });

  it("reuses cached result within TTL", async () => {
    let callCount = 0;
    const fetcher = vi.fn().mockImplementation(async () => {
      callCount++;
      return { value: Date.now() };
    });
    const r1 = await cachedFetch("GET", "/api/health", fetcher, 10_000);
    const r2 = await cachedFetch("GET", "/api/health", fetcher, 10_000);
    expect(r1).toEqual(r2);
    expect(callCount).toBe(1);
  });

  it("fetches again after TTL expires", async () => {
    let callCount = 0;
    const fetcher = vi.fn().mockImplementation(async () => {
      callCount++;
      return { value: callCount };
    });
    await cachedFetch("GET", "/api/health", fetcher, 10_000);
    expect(callCount).toBe(1);
    vi.advanceTimersByTime(10_001);
    const r2 = await cachedFetch("GET", "/api/health", fetcher, 10_000);
    expect(callCount).toBe(2);
    expect(r2).toEqual({ value: 2 });
  });

  it("does not cache failed requests", async () => {
    let callCount = 0;
    const fetcher = vi.fn().mockImplementation(async () => {
      callCount++;
      if (callCount === 1) throw new Error("API failure");
      return { data: "recovered" };
    });
    await expect(cachedFetch("GET", "/api/test", fetcher, 10_000)).rejects.toThrow("API failure");
    const r2 = await cachedFetch("GET", "/api/test", fetcher, 10_000);
    expect(r2).toEqual({ data: "recovered" });
    expect(callCount).toBe(2);
  });

  it("does not cache non-GET methods", async () => {
    let callCount = 0;
    const fetcher = vi.fn().mockImplementation(async () => {
      callCount++;
      return { data: "ok" };
    });
    await cachedFetch("POST", "/api/test", fetcher, 10_000);
    await cachedFetch("POST", "/api/test", fetcher, 10_000);
    expect(callCount).toBe(2);
  });

  it("bypasses cache when TTL is 0", async () => {
    let callCount = 0;
    const fetcher = vi.fn().mockImplementation(async () => {
      callCount++;
      return { data: "ok" };
    });
    await cachedFetch("GET", "/api/test", fetcher, 0);
    await cachedFetch("GET", "/api/test", fetcher, 0);
    expect(callCount).toBe(2);
  });
});

describe("studioApiConnection", () => {
  beforeEach(async () => {
    vi.resetModules();
  });

  it("transitions CONNECTED->OFFLINE->RECOVERED", async () => {
    const mod = await import("../studioApiConnection");
    expect(mod.getStudioApiConnection().state).toBe("CONNECTED");
    for (let i = 0; i < 5; i++) {
      mod.markStudioApiFailure("STUDIO_API_OFFLINE", `failure ${i + 1}`);
    }
    expect(mod.getStudioApiConnection().state).toBe("OFFLINE");
    expect(mod.getStudioApiConnection().pollingSuspended).toBe(true);
    mod.markStudioApiHealthy();
    expect(mod.getStudioApiConnection().state).toBe("RECOVERED");
    expect(mod.getStudioApiConnection().pollingSuspended).toBe(false);
  });

  it("suspends dependent polling after 2 failures", async () => {
    const mod = await import("../studioApiConnection");
    expect(mod.shouldSuspendDependentPolling()).toBe(false);
    mod.markStudioApiFailure("STUDIO_API_OFFLINE", "fail 1");
    mod.markStudioApiFailure("STUDIO_API_OFFLINE", "fail 2");
    expect(mod.shouldSuspendDependentPolling()).toBe(true);
    mod.markStudioApiHealthy();
    expect(mod.shouldSuspendDependentPolling()).toBe(false);
  });

  it("does not emit on repeated markStudioApiHealthy while CONNECTED", async () => {
    const mod = await import("../studioApiConnection");
    const listener = vi.fn();
    const unsub = mod.subscribeStudioApiConnection(listener);
    listener.mockClear();
    mod.markStudioApiHealthy();
    const callsAfterFirst = listener.mock.calls.length;
    mod.markStudioApiHealthy();
    expect(listener.mock.calls.length).toBe(callsAfterFirst);
    unsub();
  });

  it("emits when state transitions to RECOVERED", async () => {
    const mod = await import("../studioApiConnection");
    const listener = vi.fn();
    const unsub = mod.subscribeStudioApiConnection(listener);
    listener.mockClear();
    mod.markStudioApiFailure("STUDIO_API_OFFLINE", "fail");
    listener.mockClear();
    mod.markStudioApiHealthy();
    expect(listener).toHaveBeenCalledTimes(1);
    expect(listener.mock.calls[0][0].state).toBe("RECOVERED");
    unsub();
  });

  it("retryStudioApiConnection sets RECONNECTING", async () => {
    const mod = await import("../studioApiConnection");
    const promise = mod.retryStudioApiConnection();
    expect(mod.getStudioApiConnection().state).toBe("RECONNECTING");
    expect(mod.getStudioApiConnection().pollingSuspended).toBe(true);
    await promise.catch(() => {});
  });
});
