import { describe, expect, it } from "vitest";
import {
  LOCAL_GENERATION_FAILED_FALLBACK,
  LOCAL_GENERATION_FAILED_TITLE,
  LOCAL_GENERATION_RUNTIME_UNAVAILABLE_TITLE,
  localGenerationFailureCopy,
  previewMonitorPhase,
} from "./livePreviewFailure";

const HTTPX_TRACE = `Traceback (most recent call last):
  File "queue_worker.py", line 12, in run
    resp = client.post(url)
  File "httpx/_client.py", line 1, in post
    raise ConnectError(msg)
httpx.ConnectError: [WinError 10061] No connection could be made because the target machine actively refused it`;

describe("previewMonitorPhase", () => {
  it("maps internal states onto Idle / Generating / Preview / Failed / Cancelled", () => {
    expect(previewMonitorPhase("idle")).toBe("idle");
    expect(previewMonitorPhase("preparing")).toBe("generating");
    expect(previewMonitorPhase("processing")).toBe("generating");
    expect(previewMonitorPhase("assembling")).toBe("generating");
    expect(previewMonitorPhase("post")).toBe("generating");
    expect(previewMonitorPhase("live_preview")).toBe("preview");
    expect(previewMonitorPhase("complete")).toBe("preview");
    expect(previewMonitorPhase("failed")).toBe("failed");
    expect(previewMonitorPhase("cancelled")).toBe("cancelled");
  });
});

describe("localGenerationFailureCopy", () => {
  it("uses Local generation failed unless reasonCode is runtime_unavailable", () => {
    expect(localGenerationFailureCopy({}).title).toBe(LOCAL_GENERATION_FAILED_TITLE);
    expect(localGenerationFailureCopy({ message: "Engine offline" }).title).toBe(
      LOCAL_GENERATION_FAILED_TITLE,
    );
    expect(localGenerationFailureCopy({ message: HTTPX_TRACE }).title).toBe(
      LOCAL_GENERATION_FAILED_TITLE,
    );
  });

  it("uses a structured short message as the concise reason and keeps Details empty", () => {
    const copy = localGenerationFailureCopy({ message: "ComfyUI is not reachable" });
    expect(copy.reason).toBe("ComfyUI is not reachable");
    expect(copy.details).toBeNull();
  });

  it("uses structured JSON errorMessage/message when the backend sent an object", () => {
    const copy = localGenerationFailureCopy({
      message: '{"code":"COMFY_UNREACHABLE","message":"ComfyUI is not reachable"}',
    });
    expect(copy.reason).toBe("ComfyUI is not reachable");
    expect(copy.details).toBeNull();
  });

  it("does not dump an httpx/Python traceback in the main reason", () => {
    const copy = localGenerationFailureCopy({ message: HTTPX_TRACE });
    expect(copy.reason).toBe(LOCAL_GENERATION_FAILED_FALLBACK);
    expect(copy.reason).not.toMatch(/Traceback|httpx\.|File "/);
    expect(copy.details).toBe(HTTPX_TRACE);
    expect(copy.details).toContain("Traceback");
    expect(copy.details).toContain("httpx.ConnectError");
  });

  it("uses a backend summary before --- details --- and parks the blob in Details", () => {
    const raw =
      'ComfyUI prompt failed\n\n--- details ---\nTraceback (most recent call last):\n  File "queue_worker.py", line 1';
    const copy = localGenerationFailureCopy({ message: raw });
    expect(copy.reason).toBe("ComfyUI prompt failed");
    expect(copy.reason).not.toContain("Traceback");
    expect(copy.details).toBe(raw);
  });

  it("falls back to stage when message is empty and stage is a short human string", () => {
    const copy = localGenerationFailureCopy({ message: "", stage: "engine offline" });
    expect(copy.reason).toBe("engine offline");
    expect(copy.details).toBeNull();
  });

  it("does not use the first traceback line as the reason", () => {
    const copy = localGenerationFailureCopy({
      message: "Traceback (most recent call last):\n  File \"x.py\", line 1",
    });
    expect(copy.reason).toBe(LOCAL_GENERATION_FAILED_FALLBACK);
    expect(copy.details).toContain("Traceback");
  });

  it("renders JobOut transport fail without parsing traces", () => {
    const copy = localGenerationFailureCopy({
      status: "failed",
      message: "Local generation runtime unavailable",
      reasonCode: "runtime_unavailable",
    });
    expect(copy.title).toBe(LOCAL_GENERATION_RUNTIME_UNAVAILABLE_TITLE);
    expect(copy.reason).toBe(LOCAL_GENERATION_RUNTIME_UNAVAILABLE_TITLE);
    expect(copy.details).toBeNull();
  });

  it("renders camelCase timeline generation JSON errorMessage + errorCode", () => {
    const copy = localGenerationFailureCopy({
      status: "failed",
      errorCode: "runtime_unavailable",
      errorMessage: "Local generation runtime unavailable",
    });
    expect(copy.title).toBe(LOCAL_GENERATION_RUNTIME_UNAVAILABLE_TITLE);
    expect(copy.reason).toBe(LOCAL_GENERATION_RUNTIME_UNAVAILABLE_TITLE);
    expect(copy.details).toBeNull();
  });
it("prefers jobId + reasonCode over history_json failureClass", () => {
    const copy = localGenerationFailureCopy({
      id: "studio-id",
      jobId: "job-out-id",
      status: "failed",
      message: "Local generation runtime unavailable",
      reasonCode: "runtime_unavailable",
      historyJson: JSON.stringify({
        videoRuntime: { failure: { failureClass: "comfy_unreachable" } },
      }),
    });
    expect(copy.title).toBe(LOCAL_GENERATION_RUNTIME_UNAVAILABLE_TITLE);
    expect(copy.reason).toBe(LOCAL_GENERATION_RUNTIME_UNAVAILABLE_TITLE);
  });

  it("falls back to id + status + message + history_json.videoRuntime.failure.failureClass", () => {
    const copy = localGenerationFailureCopy({
      id: "studio-id",
      status: "failed",
      message: "Local generation runtime unavailable",
      historyJson: JSON.stringify({
        videoRuntime: { failure: { failureClass: "runtime_unavailable" } },
      }),
    });
    expect(copy.title).toBe(LOCAL_GENERATION_RUNTIME_UNAVAILABLE_TITLE);
    expect(copy.reason).toBe(LOCAL_GENERATION_RUNTIME_UNAVAILABLE_TITLE);
    expect(copy.details).toBeNull();
  });

  it("uses Timeline errorCode / errorMessage / internalJobId without JobOut reasonCode", () => {
    const copy = localGenerationFailureCopy({
      id: "studio-id",
      internalJobId: "internal-1",
      status: "failed",
      errorCode: "runtime_unavailable",
      errorMessage: "Local generation runtime unavailable",
    });
    expect(copy.title).toBe(LOCAL_GENERATION_RUNTIME_UNAVAILABLE_TITLE);
    expect(copy.reason).toBe(LOCAL_GENERATION_RUNTIME_UNAVAILABLE_TITLE);
  });

  it("does not treat a traceback inside history_json as failureClass", () => {
    const copy = localGenerationFailureCopy({
      id: "studio-id",
      status: "failed",
      message: HTTPX_TRACE,
      historyJson: JSON.stringify({
        videoRuntime: { failure: { failureClass: HTTPX_TRACE } },
      }),
    });
    expect(copy.title).toBe(LOCAL_GENERATION_FAILED_TITLE);
    expect(copy.reason).toBe(LOCAL_GENERATION_FAILED_FALLBACK);
  });
});

