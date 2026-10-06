import { describe, expect, it } from "vitest";
import type { CoDirectorMessage, CoDirectorMessageExecution } from "./types";
import type { WorkSurfaceState } from "./AgentWorkSurface/types";
import {
  applyLiveExecutionToMessages,
  capabilityActionLabel,
  dedupeExecutionMessages,
  executionStatusText,
  mergeLiveExecution,
  messageKindForStatus,
  normalizeJobStatus,
} from "./liveExecutionSync";

const EXECUTION_ID = "exec-silver-corridor";

function frozenQueued(): CoDirectorMessageExecution {
  return {
    execution_id: EXECUTION_ID,
    capability: "image.generate",
    status: "preparing",
    progress: 0,
    completed: 0,
    total: 1,
    surface_type: "image_generation",
    result_asset_ids: [],
    child_jobs: [
      {
        job_id: "child-1",
        child_index: 0,
        label: "Generated Image",
        status: "ChildJobStatus.queued",
        asset_id: null,
        progress: 0,
        stage: "",
      },
    ],
    generationJob: {
      id: "job-1",
      executionId: EXECUTION_ID,
      status: "queued",
      stage: "",
      progressPercent: 0,
    },
  };
}

function liveComplete(): WorkSurfaceState {
  return {
    mode: "agent_work",
    execution_id: EXECUTION_ID,
    capability: "image.generate",
    surface_type: "image_generation",
    status: "completed",
    progress: 1,
    child_jobs: [
      {
        job_id: "child-1",
        label: "Generated Image",
        status: "completed",
        asset_id: "asset-corridor",
        error: null,
        progress: 1,
        stage: "Complete",
        child_index: 0,
        metadata: {},
      },
    ],
    result_asset_ids: ["asset-corridor"],
    collection_id: null,
    project_id: "proj-1",
  };
}

describe("normalizeJobStatus", () => {
  it("strips enum prefixes so chat never shows childjobstatus.queued", () => {
    expect(normalizeJobStatus("ChildJobStatus.queued")).toBe("queued");
    expect(normalizeJobStatus("childjobstatus.queued")).toBe("queued");
    expect(normalizeJobStatus("ExecutionStatus.completed")).toBe("completed");
    expect(normalizeJobStatus("done")).toBe("completed");
  });
});

describe("mergeLiveExecution", () => {
  it("overlays the live completed pack onto the frozen queued chat snapshot", () => {
    const merged = mergeLiveExecution(frozenQueued(), liveComplete());
    expect(merged.status).toBe("completed");
    expect(merged.completed).toBe(1);
    expect(merged.total).toBe(1);
    expect(merged.result_asset_ids).toEqual(["asset-corridor"]);
    expect(merged.child_jobs?.[0]?.status).toBe("completed");
    expect(merged.generationJob?.status).toBe("completed");
    expect(merged.generationJob?.stage).toBe("Complete");
    expect(executionStatusText(merged)).toBe("Generating — 1/1 complete. Done.");
    expect(messageKindForStatus(merged.status)).toBe("completion");
  });

  it("does not merge a different execution", () => {
    const merged = mergeLiveExecution(frozenQueued(), { ...liveComplete(), execution_id: "other" });
    expect(merged.status).toBe("preparing");
    expect(merged.child_jobs?.[0]?.status).toBe("queued");
  });
});

describe("applyLiveExecutionToMessages", () => {
  it("promotes the Working chat card to Done while keeping the stored text stable", () => {
    // Intelligence mission 2026-09-19 (RC3): the live poller updates the
    // execution payload + kind but NEVER rewrites message.content — live
    // progress text must never leak into conversational memory.
    const messages: CoDirectorMessage[] = [
      {
        id: "exec-req-1",
        role: "assistant",
        content: "Generating — 0/1 complete.",
        createdAt: new Date().toISOString(),
        messageType: "execution_status",
        execution: frozenQueued(),
      },
    ];
    const next = applyLiveExecutionToMessages(messages, liveComplete());
    expect(next).not.toBe(messages);
    expect(next[0].messageType).toBe("completion");
    expect(next[0].content).toBe("Generating — 0/1 complete.");
    expect(next[0].execution?.status).toBe("completed");
    expect(next[0].execution?.child_jobs?.[0]?.status).toBe("completed");
  });

  it("keeps the same array when the live pack already matches the chat card", () => {
    const completed = mergeLiveExecution(frozenQueued(), liveComplete());
    const messages: CoDirectorMessage[] = [
      {
        id: "exec-req-1",
        role: "assistant",
        content: executionStatusText(completed),
        createdAt: new Date().toISOString(),
        messageType: "completion",
        execution: completed,
      },
    ];
    expect(applyLiveExecutionToMessages(messages, liveComplete())).toBe(messages);
  });

  it("collapses duplicate execution cards for the same execution_id", () => {
    const frozen = frozenQueued();
    const messages: CoDirectorMessage[] = [
      {
        id: "exec-req-1",
        role: "assistant",
        content: "Generating — 0/1 complete.",
        createdAt: new Date().toISOString(),
        messageType: "execution_status",
        execution: frozen,
      },
      {
        id: "exec-req-2",
        role: "assistant",
        content: "Generating — 0/1 complete.",
        createdAt: new Date().toISOString(),
        messageType: "execution_status",
        execution: { ...frozen },
      },
    ];
    const next = dedupeExecutionMessages(messages);
    expect(next).toHaveLength(1);
    expect(next[0].id).toBe("exec-req-1");
  });
});

describe("ORDER 19 timeline.add_asset fail copy", () => {
  it("labels timeline.add_asset as Add asset", () => {
    expect(capabilityActionLabel("timeline.add_asset", "Execution")).toBe("Add asset");
  });

  it("builds Add asset — failed. You can retry…", () => {
    const text = executionStatusText({
      execution_id: "exec-1",
      capability: "timeline.add_asset",
      status: "failed",
      completed: 0,
      total: 1,
    });
    expect(text).toBe("Add asset — failed. You can retry or adjust and try again. (Missing sourceAssetId)");
  });
});

  it("omits Missing sourceAssetId when plan has sourceAssetId", () => {
    const text = executionStatusText({
      execution_id: "exec-2",
      capability: "timeline.add_asset",
      status: "failed",
      completed: 0,
      total: 1,
      plan_data: { sourceAssetId: "asset-cafe-1" },
      error: "placement failed",
    });
    expect(text).toBe("Add asset — failed. You can retry or adjust and try again.");
  });
