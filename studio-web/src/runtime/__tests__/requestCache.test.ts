import { describe, it, expect, vi, beforeEach } from "vitest";

describe("requestCache", () => {
  let cachedFetch: typeof import("../requestCache").cachedFetch;
  let clearAllCache: typeof import("../requestCache").clearAllCache;
  let clearCacheEntry: typeof import("../requestCache").clearCacheEntry;

  beforeEach(async () => {
    const mod = await import("../requestCache");
    cachedFetch = mod.cachedFetch;
    clearAllCache = mod.clearAllCache;
    clearCacheEntry = mod.clearCacheEntry;
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

  it("does not share cache across GET query strings (modality isolation)", async () => {
    const calls: string[] = [];
    const makeFetcher = (modality: string) =>
      vi.fn().mockImplementation(async () => {
        calls.push(modality);
        return { modality, models: [{ id: modality, modality }] };
      });
    const llmFetcher = makeFetcher("llm");
    const videoFetcher = makeFetcher("video");
    const imageFetcher = makeFetcher("image");
    const audioFetcher = makeFetcher("audio");

    const [llm, video, image, audio] = await Promise.all([
      cachedFetch("GET", "/api/production-control/models?modality=llm", llmFetcher, 30_000),
      cachedFetch("GET", "/api/production-control/models?modality=video", videoFetcher, 30_000),
      cachedFetch("GET", "/api/production-control/models?modality=image", imageFetcher, 30_000),
      cachedFetch("GET", "/api/production-control/models?modality=audio", audioFetcher, 30_000),
    ]);

    expect(llm).toEqual({ modality: "llm", models: [{ id: "llm", modality: "llm" }] });
    expect(video).toEqual({ modality: "video", models: [{ id: "video", modality: "video" }] });
    expect(image).toEqual({ modality: "image", models: [{ id: "image", modality: "image" }] });
    expect(audio).toEqual({ modality: "audio", models: [{ id: "audio", modality: "audio" }] });
    expect(calls.sort()).toEqual(["audio", "image", "llm", "video"]);
    expect(llmFetcher).toHaveBeenCalledTimes(1);
    expect(videoFetcher).toHaveBeenCalledTimes(1);
    expect(imageFetcher).toHaveBeenCalledTimes(1);
    expect(audioFetcher).toHaveBeenCalledTimes(1);
  });

  it("still deduplicates identical query strings", async () => {
    let callCount = 0;
    const fetcher = vi.fn().mockImplementation(async () => {
      callCount++;
      return { modality: "video" };
    });
    const [a, b] = await Promise.all([
      cachedFetch("GET", "/api/production-control/models?modality=video", fetcher, 30_000),
      cachedFetch("GET", "/api/production-control/models?modality=video", fetcher, 30_000),
    ]);
    expect(a).toEqual(b);
    expect(callCount).toBe(1);
  });

  it("uses default TTL map so models?modality= keys stay isolated without explicit ttlMs", async () => {
    const llmFetcher = vi.fn().mockResolvedValue({ modality: "llm", models: [{ id: "gemma", modality: "llm" }] });
    const videoFetcher = vi.fn().mockResolvedValue({ modality: "video", models: [{ id: "minimax-h3", modality: "video" }] });
    const [llm, video] = await Promise.all([
      cachedFetch("GET", "/api/production-control/models?modality=llm", llmFetcher),
      cachedFetch("GET", "/api/production-control/models?modality=video", videoFetcher),
    ]);
    expect(llm).toEqual({ modality: "llm", models: [{ id: "gemma", modality: "llm" }] });
    expect(video).toEqual({ modality: "video", models: [{ id: "minimax-h3", modality: "video" }] });
    expect(llmFetcher).toHaveBeenCalledTimes(1);
    expect(videoFetcher).toHaveBeenCalledTimes(1);

    const llmAgain = await cachedFetch(
      "GET",
      "/api/production-control/models?modality=llm",
      vi.fn().mockResolvedValue({ modality: "poison" }),
    );
    expect(llmAgain).toEqual(llm);
  });

  it("isolates TTL query endpoints /resolved /queue /status by projectId", async () => {
    const cases: Array<[string, string]> = [
      ["/api/production-control/resolved?projectId=alpha", "/api/production-control/resolved?projectId=beta"],
      ["/api/production-control/queue?projectId=alpha", "/api/production-control/queue?projectId=beta"],
      ["/api/production-control/status?projectId=alpha", "/api/production-control/status?projectId=beta"],
    ];
    for (const [aPath, bPath] of cases) {
      const aFetcher = vi.fn().mockResolvedValue({ id: "alpha" });
      const bFetcher = vi.fn().mockResolvedValue({ id: "beta" });
      const [a, b] = await Promise.all([
        cachedFetch("GET", aPath, aFetcher),
        cachedFetch("GET", bPath, bFetcher),
      ]);
      expect(a).toEqual({ id: "alpha" });
      expect(b).toEqual({ id: "beta" });
      expect(aFetcher).toHaveBeenCalledTimes(1);
      expect(bFetcher).toHaveBeenCalledTimes(1);
    }
  });

  it("does not cache POST or PUT even when the path has a query string", async () => {
    const post = vi.fn().mockResolvedValue({ ok: true });
    const put = vi.fn().mockResolvedValue({ ok: true });
    await cachedFetch("POST", "/api/production-control/models?modality=video", post, 30_000);
    await cachedFetch("POST", "/api/production-control/models?modality=video", post, 30_000);
    await cachedFetch("PUT", "/api/production-control/queue?projectId=alpha", put, 30_000);
    await cachedFetch("PUT", "/api/production-control/queue?projectId=alpha", put, 30_000);
    expect(post).toHaveBeenCalledTimes(2);
    expect(put).toHaveBeenCalledTimes(2);
  });

  it("clearCacheEntry without query invalidates all query variants of that GET path", async () => {
    const llmFetcher = vi.fn().mockResolvedValue({ modality: "llm" });
    const videoFetcher = vi.fn().mockResolvedValue({ modality: "video" });
    await cachedFetch("GET", "/api/production-control/models?modality=llm", llmFetcher);
    await cachedFetch("GET", "/api/production-control/models?modality=video", videoFetcher);
    clearCacheEntry("GET", "/api/production-control/models");
    const llmFetcher2 = vi.fn().mockResolvedValue({ modality: "llm-2" });
    const videoFetcher2 = vi.fn().mockResolvedValue({ modality: "video-2" });
    const [llm, video] = await Promise.all([
      cachedFetch("GET", "/api/production-control/models?modality=llm", llmFetcher2),
      cachedFetch("GET", "/api/production-control/models?modality=video", videoFetcher2),
    ]);
    expect(llm).toEqual({ modality: "llm-2" });
    expect(video).toEqual({ modality: "video-2" });
    expect(llmFetcher2).toHaveBeenCalledTimes(1);
    expect(videoFetcher2).toHaveBeenCalledTimes(1);
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
