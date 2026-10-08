import { describe, expect, it } from "vitest";
import { buildSnapshot } from "./startupSnapshot";
import type { RuntimeManagerStatus } from "../api";

function makeStatus(opts: {
  comfyStatus?: string;
  comfyState?: string;
  studioApiHealth?: string;
  ollamaStatus?: string;
  tunnelStatus?: string;
  routeAStatus?: string;
  managerPid?: number | null;
  studioApiPid?: number;
}): RuntimeManagerStatus {
  const comfyStatus = opts.comfyStatus ?? "running";
  const ollamaStatus = opts.ollamaStatus ?? "running";
  const tunnelStatus = opts.tunnelStatus ?? "stopped";
  const routeAStatus = opts.routeAStatus ?? "stopped";
  return {
    comfyui: { status: comfyStatus as never, ownership: "owned" as never },
    studioApi: { status: "running" as never, ownership: "owned" as never },
    ollama: { status: ollamaStatus as never, ownership: "external" as never },
    tunnel: { status: tunnelStatus as never, ownership: "external" as never },
    gpu: { detected: true },
    routeA: { status: routeAStatus as never, ownership: "external" as never, port: 8192, adeptOwnedReady: false },
    gpuAdmission: { dualResident: false, comfyuiAllowed: true, routeAAllowed: true },
    preferences: { comfyuiBackgroundManagerEnabled: true, localhostBackgroundManagerEnabled: true, startWithWindows: true, remoteAccessEnabled: false },
    adeptRuntime: {
      configured: true,
      taskRegistered: true,
      startWithWindows: true,
      serviceState: opts.comfyState ? "starting" : "running",
      comfyState: opts.comfyState ?? "ready",
      worker: "qwen_ready",
      falConnected: true,
      creatorMessage: "ready",
      comfyPid: 19500,
      owned: true,
      managerPid: opts.managerPid === undefined ? 71956 : opts.managerPid,
      studioApiPid: opts.studioApiPid ?? 29940,
      studioApiOwned: true,
      studioApiHealth: opts.studioApiHealth ?? "healthy",
    },
  } as unknown as RuntimeManagerStatus;
}

describe("buildSnapshot", () => {
  it("warm — all required online → 100%, ALL REQUIRED SYSTEMS ONLINE", () => {
    const snap = buildSnapshot(makeStatus({}), true);
    expect(snap.allRequiredOnline).toBe(true);
    expect(snap.overallPct).toBe(100);
    expect(snap.message).toBe("ALL REQUIRED SYSTEMS ONLINE");
    expect(snap.rows.find((r) => r.id === "creator_engine")?.state).toBe("online");
  });

  it("cold — Studio API unreachable, no status → required STARTING, not online", () => {
    const snap = buildSnapshot(null, false);
    expect(snap.allRequiredOnline).toBe(false);
    expect(snap.overallPct).toBe(0);
    expect(snap.message).toBe("Bringing Adept UI Online");
    for (const r of snap.rows.filter((x) => x.required)) {
      expect(r.state).toBe("starting");
    }
  });

  it("partial — Comfy starting, Studio API up → Creator Engine STARTING, no fake ONLINE", () => {
    const snap = buildSnapshot(makeStatus({ comfyStatus: "starting", comfyState: "starting" }), true);
    expect(snap.rows.find((r) => r.id === "creator_engine")?.state).toBe("starting");
    expect(snap.rows.find((r) => r.id === "studio_api")?.state).toBe("online");
    expect(snap.allRequiredOnline).toBe(false);
  });

  it("failure — Comfy reports error → anyRequiredFailed, STARTUP FAILED, no fake ONLINE", () => {
    const snap = buildSnapshot(makeStatus({ comfyStatus: "error", comfyState: "offline" }), true);
    expect(snap.anyRequiredFailed).toBe(true);
    expect(snap.message).toBe("STARTUP FAILED");
    expect(snap.rows.find((r) => r.id === "creator_engine")?.state).toBe("failed");
  });

  it("optional services do not block readiness when Local AI is not installed", () => {
    const status = makeStatus({ ollamaStatus: "not_configured", tunnelStatus: "stopped", routeAStatus: "stopped" });
    status.ollama = { ...status.ollama, configured: false, status: "not_configured" as never };
    const snap = buildSnapshot(status, true);
    expect(snap.allRequiredOnline).toBe(true);
    expect(snap.rows.find((r) => r.id === "local_ai")?.state).toBe("on_demand");
    expect(snap.rows.find((r) => r.id === "local_ai")?.required).toBe(false);
    expect(snap.rows.find((r) => r.id === "video_runtime")?.state).toBe("on_demand");
  });

  it("Local AI Runtime STARTING blocks readiness while configured and offline", () => {
    const status = makeStatus({ ollamaStatus: "stopped" });
    status.ollama = { ...status.ollama, configured: true, status: "stopped" as never };
    const snap = buildSnapshot(status, true);
    expect(snap.rows.find((r) => r.id === "local_ai")?.state).toBe("starting");
    expect(snap.rows.find((r) => r.id === "local_ai")?.required).toBe(true);
    expect(snap.allRequiredOnline).toBe(false);
  });

  it("logicalServices override creator engine and video runtime without ports", () => {
    const status = makeStatus({ routeAStatus: "stopped" });
    status.logicalServices = {
      "runtime.comfy": { logicalId: "runtime.comfy", availability: "ONLINE", gpuResidency: "FREE" },
      "runtime.video": { logicalId: "runtime.video", availability: "ON_DEMAND", gpuResidency: "FREE" },
    };
    const snap = buildSnapshot(status, true);
    expect(snap.rows.find((r) => r.id === "creator_engine")?.state).toBe("online");
    expect(snap.rows.find((r) => r.id === "video_runtime")?.state).toBe("on_demand");
  });

  it("Local AI Runtime ONLINE when daemon is running", () => {
    const status = makeStatus({ ollamaStatus: "running" });
    status.ollama = { ...status.ollama, configured: true, daemonOnline: true, modelReady: true };
    const snap = buildSnapshot(status, true);
    expect(snap.rows.find((r) => r.id === "local_ai")?.state).toBe("online");
    expect(snap.allRequiredOnline).toBe(true);
  });
});
