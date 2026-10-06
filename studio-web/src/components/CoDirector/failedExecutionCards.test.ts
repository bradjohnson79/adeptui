import { describe, expect, it, vi } from "vitest";

vi.mock("../../../api", () => ({
  api: {
    advanceExecution: vi.fn(),
    regenerateFrame: vi.fn(),
    cancelExecution: vi.fn(),
  },
}));
vi.mock("./CoDirectorSession", () => ({
  useCoDirectorSession: () => ({ uiContext: {}, activeExecution: null, setActiveExecution: vi.fn() }),
}));
vi.mock("./SceneCreator/persistThenOpenSceneCreator", () => ({
  persistThenOpenSceneCreator: vi.fn(),
}));

import {
  failedPackToChatMessage,
  mergeFailedExecutionCards,
  type ListedExecutionPack,
} from "./failedExecutionCards";
import type { CoDirectorMessage } from "./types";

const LEFTOVER_ID = "330d2ec9-f1c1-442e-9dce-d9562d400fd2";

function leftoverPack(overrides: Partial<ListedExecutionPack> = {}): ListedExecutionPack {
  return {
    execution_id: LEFTOVER_ID,
    capability: "character.generate_visual_sheet",
    status: "failed",
    progress: 0,
    completed: 0,
    total: 1,
    surface_type: "storyboard_generation",
    collection_id: null,
    result_asset_ids: [],
    error: null,
    child_jobs: [
      {
        job_id: "50468571-23dd-412b-a8f2-a3929612dde2",
        child_index: 0,
        label: "Output 1",
        status: "failed",
        asset_id: null,
        error: "JOB_NOT_FOUND",
        progress: 0,
        stage: "",
      },
    ],
    ...overrides,
  };
}

describe("failedExecutionCards leftover durable pin", () => {
  it("failedPackToChatMessage keeps pack.error null and child JOB_NOT_FOUND", () => {
    const card = failedPackToChatMessage(leftoverPack());
    expect(card).not.toBeNull();
    expect(card!.messageType).toBe("error");
    expect(card!.execution?.execution_id).toBe(LEFTOVER_ID);
    expect(card!.execution?.error).toBeNull();
    expect(card!.execution?.child_jobs?.[0]?.error).toBe("JOB_NOT_FOUND");
    expect(card!.content).toContain("no longer available");
  });

  it("merge adds one leftover card when execution_id is absent", () => {
    const prev: CoDirectorMessage[] = [
      {
        id: "welcome",
        role: "assistant",
        content: "Welcome",
        createdAt: "2026-01-01T00:00:00.000Z",
      },
    ];
    const merged = mergeFailedExecutionCards(prev, [leftoverPack()]);
    expect(merged).toHaveLength(2);
    const card = merged[1];
    expect(card.messageType).toBe("error");
    expect(card.execution?.execution_id).toBe(LEFTOVER_ID);
    expect(card.execution?.error).toBeNull();
    expect(card.content).toContain("no longer available");
  });

  it("does not remount a dismissed leftover pack", () => {
    const prev: CoDirectorMessage[] = [
      {
        id: "welcome",
        role: "assistant",
        content: "Welcome",
        createdAt: "2026-01-01T00:00:00.000Z",
      },
    ];
    const merged = mergeFailedExecutionCards(prev, [
      leftoverPack({ status: "cancelled", error: "DISMISSED" }),
    ]);
    expect(merged).toBe(prev);
  });

  it("skips merge when execution_id is already on a message", () => {
    const existing: CoDirectorMessage = {
      id: "already-" + LEFTOVER_ID,
      role: "assistant",
      content: "already present",
      createdAt: "2026-01-01T00:00:00.000Z",
      messageType: "error",
      execution: { execution_id: LEFTOVER_ID, error: null },
    };
    const prev = [existing];
    const merged = mergeFailedExecutionCards(prev, [leftoverPack()]);
    expect(merged).toBe(prev);
    expect(merged).toHaveLength(1);
  });

  it("does not remount ERS or Scene leftover cards onto the Character Creator rail", () => {
    const prev: CoDirectorMessage[] = [
      {
        id: "welcome",
        role: "assistant",
        content: "Welcome",
        createdAt: "2026-01-01T00:00:00.000Z",
      },
    ];
    const merged = mergeFailedExecutionCards(prev, [
      leftoverPack({
        execution_id: "ers-left",
        capability: "scene.generate_ers",
        surface_type: "ers_generation",
        total: 7,
        completed: 0,
      }),
    ]);
    expect(merged).toBe(prev);
  });
});

describe("ORDER 19 timeline.add_asset leftover card copy", () => {
  it("failedPackToChatMessage uses Add asset — failed…", () => {
    const card = failedPackToChatMessage(
      leftoverPack({
        capability: "timeline.add_asset",
        surface_type: "timeline",
        error: "placement failed",
        child_jobs: [
          {
            job_id: "j1",
            child_index: 0,
            label: "Place",
            status: "failed",
            asset_id: null,
            error: "missing sourceAssetId",
            progress: 0,
            stage: "",
          },
        ],
      }),
    );
    expect(card).not.toBeNull();
    expect(card!.content.startsWith("Add asset — failed. You can retry or adjust and try again.")).toBe(true);
    expect(card!.content).toContain("Missing sourceAssetId");
  });
});

  it("surfaces Missing batchBlockId when pack error names it", () => {
    const card = failedPackToChatMessage(
      leftoverPack({
        capability: "timeline.add_asset",
        surface_type: "timeline",
        error: "batchBlockId required",
        plan_data: {},
        child_jobs: [],
      }),
    );
    expect(card!.content).toContain("Missing batchBlockId");
    expect(card!.content).toContain("Missing sourceAssetId");
  });

