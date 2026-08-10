import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  classifyStudioApiTransportFailure,
  getStudioApiConnection,
  isStudioApiConnectivityFailure,
  markStudioApiFailure,
  markStudioApiHealthy,
  nextStudioApiRetryMs,
  shouldSuspendDependentPolling,
} from "./studioApiConnection";

describe("studioApiConnection", () => {
  beforeEach(() => {
    markStudioApiHealthy();
    // Reset recovered → connected settlement noise
    markStudioApiHealthy();
  });

  it("classifies connection refused as STUDIO_API_OFFLINE", () => {
    expect(classifyStudioApiTransportFailure(new TypeError("Failed to fetch"))).toBe(
      "STUDIO_API_OFFLINE",
    );
    expect(
      classifyStudioApiTransportFailure(new Error("net::ERR_CONNECTION_REFUSED")),
    ).toBe("STUDIO_API_OFFLINE");
  });

  it("classifies connection reset distinctly", () => {
    expect(
      classifyStudioApiTransportFailure(new Error("net::ERR_CONNECTION_RESET")),
    ).toBe("STUDIO_API_CONNECTION_RESET");
  });

  it("suspends polling after confirmed failure and recovers", () => {
    markStudioApiFailure("STUDIO_API_OFFLINE", "refused");
    expect(getStudioApiConnection().state).toBe("RECONNECTING");
    expect(shouldSuspendDependentPolling()).toBe(true);
    markStudioApiFailure("STUDIO_API_OFFLINE", "refused again");
    expect(getStudioApiConnection().state).toBe("OFFLINE");
    markStudioApiHealthy();
    expect(getStudioApiConnection().state).toBe("RECOVERED");
    expect(shouldSuspendDependentPolling()).toBe(false);
  });

  it("uses bounded exponential backoff", () => {
    expect(nextStudioApiRetryMs(0)).toBeLessThanOrEqual(2000);
    expect(nextStudioApiRetryMs(1)).toBeLessThan(nextStudioApiRetryMs(4));
    expect(nextStudioApiRetryMs(20)).toBe(30_000);
  });

  it("detects ApiError-shaped connectivity failures", () => {
    expect(isStudioApiConnectivityFailure({ code: "STUDIO_API_OFFLINE" })).toBe(true);
    expect(isStudioApiConnectivityFailure({ code: "OLLAMA_EMPTY_RESPONSE" })).toBe(false);
  });
});
