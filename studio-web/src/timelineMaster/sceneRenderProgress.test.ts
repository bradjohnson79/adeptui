import { describe, expect, it } from "vitest";
import type { BatchBlock, SceneTimelineMaster } from "./contracts";
import {
  batchChipStatus,
  batchJobProgressPercent,
  completedGeneratedBatches,
  appendComfyPercentLine,
  comfyProgressPercentFromJob,
  comfyProgressPercentFromText,
  formatSceneRenderStatus,
  isSceneGenerationOverlayActive,
  sceneGenerationCompleteNotice,
  isSceneRenderActive,
  PREVIEW_GENERATION_STANDBY,
  previewGenerationNotice,
  shouldShowSceneRenderStatus,
} from "./sceneRenderProgress";

function batch(partial: Partial<BatchBlock> & { id: string; order: number; status: string }): BatchBlock {
  return {
    sceneId: "s1",
    label: partial.id,
    generatorOverride: false,
    duration: { plannedDuration: 5 },
    sourceAnchors: [],
    promptSegments: [],
    visualClips: [],
    audioClips: [],
    sfxClips: [],
    cameraInstructions: [],
    generationJobs: [],
    candidateVersions: [],
    repairRanges: [],
    references: [],
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    legacyImageClipIds: [],
    ...partial,
  } as BatchBlock;
}

function master(blocks: BatchBlock[], generationProgress?: Record<string, unknown>): SceneTimelineMaster {
  return {
    version: 1,
    mode: "video_finishing",
    orchestratorMode: "sequential_continuity",
    repairOverlapPolicy: "block",
    preflightMode: "warnings_only",
    batchBlocks: blocks,
    executionSnapshots: {},
    migratedFromDirectorJson: false,
    ...(generationProgress ? { generationProgress } : {}),
  } as SceneTimelineMaster;
}

describe("batchChipStatus", () => {
  it("maps Chief chip labels", () => {
    expect(batchChipStatus("Queued")).toBe("Queued");
    expect(batchChipStatus("Generating")).toBe("Rendering");
    expect(batchChipStatus("Waiting")).toBe("Rendering");
    expect(batchChipStatus("Approved")).toBe("Complete");
    expect(batchChipStatus("CandidateReady")).toBe("Complete");
    expect(batchChipStatus("Failed")).toBe("Failed");
    expect(batchChipStatus("Cancelled")).toBe("Cancelled");
    expect(batchChipStatus("Draft")).toBe("Draft");
  });
});

describe("isSceneRenderActive", () => {
  it("is true for Generating or Waiting, not leftover Queued", () => {
    expect(isSceneRenderActive(master([batch({ id: "b1", order: 0, status: "Queued" })]))).toBe(false);
    expect(
      isSceneRenderActive(
        master([
          batch({
            id: "b1",
            order: 0,
            status: "Queued",
            generationJobs: [
              {
                id: "j1",
                executionSnapshotId: "e1",
                status: "running",
                locality: "local",
                hostedCancelSupport: "unknown",
                createdAt: "2026-01-01T00:00:00Z",
              },
            ],
          }),
        ]),
      ),
    ).toBe(true);
    expect(isSceneRenderActive(master([batch({ id: "b1", order: 0, status: "Generating" })]))).toBe(true);
    expect(isSceneRenderActive(master([batch({ id: "b1", order: 0, status: "Waiting" })]))).toBe(true);
    expect(isSceneRenderActive(master([batch({ id: "b1", order: 0, status: "Approved" })]))).toBe(false);
  });
});

describe("batchJobProgressPercent", () => {
  it("scales 0..1 to percent and omits when missing", () => {
    expect(batchJobProgressPercent(batch({ id: "b1", order: 0, status: "Generating" }))).toBeNull();
    expect(
      batchJobProgressPercent(
        batch({
          id: "b1",
          order: 0,
          status: "Generating",
          generationJobs: [
            {
              id: "j1",
              executionSnapshotId: "e1",
              status: "running",
              locality: "local",
              hostedCancelSupport: "unknown",
              progress: 0.42,
              createdAt: "2026-01-01T00:00:00Z",
            },
          ],
        }),
      ),
    ).toBe(42);
  });
});

describe("formatSceneRenderStatus", () => {
  it("prefers master.generationProgress when present", () => {
    const m = master(
      [
        batch({ id: "b1", order: 0, status: "Approved" }),
        batch({ id: "b2", order: 1, status: "Generating" }),
      ],
      {
        currentBatchIndex: 2,
        totalBatches: 2,
        batchStatus: "Generating",
        batchProgress: 0.25,
        sceneStatus: "generating",
        currentBatchId: "b2",
        statusLines: [
          "Render Batch 2/2 — In Progress — 25%",
          "1/2 batches complete",
        ],
      },
    );
    expect(formatSceneRenderStatus(m)).toBe(
      "Render Batch 2/2 — In Progress — 25%\n1/2 batches complete",
    );
  });

  it("derives both current batch and overall counter without statusLines", () => {
    const m = master([
      batch({
        id: "b1",
        order: 0,
        status: "Approved",
        approvedClip: { assetId: "a1", executionSnapshotId: "e", approvedAt: "t", playable: true },
      }),
      batch({ id: "b2", order: 1, status: "Generating" }),
    ]);
    expect(formatSceneRenderStatus(m)).toBe(
      "Render Batch 2/2 — In Progress\n1/2 batches complete",
    );
    expect(shouldShowSceneRenderStatus(m)).toBe(true);
  });

  it("hides idle N/N chrome (does not invent Scene Finished; overlay off when idle)", () => {
    const m = master([
      batch({
        id: "b1",
        order: 0,
        status: "CandidateReady",
        candidateVersions: [
          {
            id: "c1",
            executionSnapshotId: "e",
            assetId: "a1",
            label: "Take 1",
            createdAt: "2026-01-01T00:00:00Z",
            approved: false,
          },
        ],
      }),
      batch({
        id: "b2",
        order: 1,
        status: "CandidateReady",
        candidateVersions: [
          {
            id: "c2",
            executionSnapshotId: "e",
            assetId: "a2",
            label: "Take 2",
            createdAt: "2026-01-01T00:00:00Z",
            approved: false,
          },
        ],
      }),
    ]);
    expect(formatSceneRenderStatus(m)).toBeNull();
    expect(shouldShowSceneRenderStatus(m)).toBe(false);
    expect(isSceneGenerationOverlayActive(m)).toBe(false);
  });

  it("hides leftover Queued with no provider job", () => {
    const m = master([
      batch({ id: "b1", order: 0, status: "Approved", approvedClip: { assetId: "a1", executionSnapshotId: "e", approvedAt: "t", playable: true } }),
      batch({ id: "b2", order: 1, status: "Queued" }),
    ]);
    expect(formatSceneRenderStatus(m)).toBeNull();
    expect(isSceneGenerationOverlayActive(m)).toBe(false);
  });

  it("keeps the monitor up when a later window was closed by an older job", () => {
    const m = master([
      batch({
        id: "b1",
        order: 0,
        status: "QC_Pending",
        candidateVersions: [
          {
            id: "c1",
            executionSnapshotId: "snap-1",
            assetId: "a1",
            label: "Take D",
            createdAt: "2026-01-01T00:00:00Z",
            approved: false,
          },
        ],
      }),
      batch({
        id: "b2",
        order: 1,
        status: "QC_Pending",
        pendingSnapshotId: "snap-2",
        generationJobs: [
          {
            id: "j-old",
            executionSnapshotId: "snap-old",
            queueJobId: "job-old",
            status: "completed",
            locality: "local",
            hostedCancelSupport: "unknown",
            createdAt: "2026-01-01T00:00:00Z",
          },
        ],
      }),
      batch({
        id: "b3",
        order: 2,
        status: "QC_Pending",
        pendingSnapshotId: "snap-3",
        generationJobs: [
          {
            id: "j-old-3",
            executionSnapshotId: "snap-old-3",
            queueJobId: "job-old-3",
            status: "completed",
            locality: "local",
            hostedCancelSupport: "unknown",
            createdAt: "2026-01-01T00:00:00Z",
          },
        ],
      }),
    ]);
    expect(isSceneRenderActive(m)).toBe(true);
    expect(shouldShowSceneRenderStatus(m)).toBe(true);
    const text = formatSceneRenderStatus(m) || "";
    expect(text).toContain("Render Batch 2/3 — Preparing");
    expect(text).toContain("1/3 batches complete");
    expect(sceneGenerationCompleteNotice(m)).toBeNull();
  });

  it("shows Preparing while a later batch is staged for the next sequential slot", () => {
    const m = master([
      batch({
        id: "b1",
        order: 0,
        status: "Approved",
        approvedClip: { assetId: "a1", executionSnapshotId: "e", approvedAt: "t", playable: true },
      }),
      batch({ id: "b2", order: 1, status: "Queued", pendingSnapshotId: "snap-2" }),
      batch({ id: "b3", order: 2, status: "Queued", pendingSnapshotId: "snap-3" }),
    ]);
    expect(isSceneRenderActive(m)).toBe(true);
    expect(isSceneGenerationOverlayActive(m)).toBe(true);
    expect(shouldShowSceneRenderStatus(m)).toBe(true);
    const text = formatSceneRenderStatus(m) || "";
    expect(text).toContain("Render Batch 2/3 — Preparing");
    expect(text).toContain("The next parts of this scene are being prepared.");
    expect(text).toContain("1/3 batches complete");
  });

  it("shows sequential Queued while an earlier batch is Generating", () => {
    const m = master([
      batch({ id: "b1", order: 0, status: "Generating" }),
      batch({ id: "b2", order: 1, status: "Queued" }),
    ]);
    expect(isSceneRenderActive(m)).toBe(true);
    expect(formatSceneRenderStatus(m)).toContain("Render Batch 1/2");
  });

  it("does not show 0% while generating without grounded progress", () => {
    const m = master(
      [batch({ id: "b1", order: 0, status: "Generating" })],
      {
        currentBatchIndex: 1,
        totalBatches: 1,
        batchStatus: "Generating",
        batchProgress: 0,
        sceneStatus: "generating",
        progressGrounded: false,
        phaseLabel: "Preparing model",
        statusLines: ["Render Batch 1/1 — Preparing model"],
      },
    );
    const text = formatSceneRenderStatus(m) || "";
    expect(text).toContain("Preparing model");
    expect(text).not.toMatch(/0%/);
  });

  it("surfaces stall chrome when the backend marks the job stalled", () => {
    const m = master(
      [batch({ id: "b1", order: 0, status: "Generating" })],
      {
        currentBatchIndex: 1,
        totalBatches: 1,
        batchStatus: "Generating",
        batchProgress: 0,
        sceneStatus: "generating",
        progressGrounded: false,
        stalled: true,
        lastRuntimeEventAt: "2020-01-01T00:00:00Z",
        phaseLabel: "Generating",
        statusLines: ["Render Batch 1/1 — Generating"],
      },
    );
    const text = formatSceneRenderStatus(m) || "";
    expect(text).toContain("Generation may be stalled");
    expect(text).toMatch(/Last runtime event:/);
    expect(text).not.toMatch(/0%/);
  });

  it("shows phase, elapsed clock, and heartbeat without inventing a percent", () => {
    const m = master(
      [batch({ id: "b1", order: 0, status: "Generating" }), batch({ id: "b2", order: 1, status: "Queued" })],
      {
        currentBatchIndex: 1,
        totalBatches: 2,
        batchStatus: "Generating",
        batchProgress: 0,
        sceneStatus: "generating",
        progressGrounded: false,
        phase: "sampling",
        phaseLabel: "Generating",
        elapsedActiveTime: 522,
        lastRuntimeEventAt: new Date().toISOString(),
        statusLines: ["Render Batch 1/2 — Generating", "0/2 batches complete"],
      },
    );
    const text = formatSceneRenderStatus(m) || "";
    expect(text).toContain("Generating — Sampling");
    expect(text).toContain("Elapsed: 08:42");
    expect(text).toContain("Runtime active");
    expect(text).toMatch(/Last runtime event:/);
    expect(text).not.toMatch(/%/);
    expect(text).toContain("0/2 batches complete");
  });

  it("raises the live counter when a deposited window is still in QC", () => {
    const m = master(
      [
        batch({
          id: "b1",
          order: 0,
          status: "QC_RetryRequired",
          candidateVersions: [
            {
              id: "c1",
              executionSnapshotId: "snap-1",
              assetId: "a1",
              label: "Take A",
              createdAt: "2026-01-01T00:00:00Z",
              approved: false,
            },
          ],
        }),
        batch({
          id: "b2",
          order: 1,
          status: "QC_Pending",
          candidateVersions: [
            {
              id: "c2",
              executionSnapshotId: "snap-2",
              assetId: "a2",
              label: "Take A",
              createdAt: "2026-01-01T00:00:00Z",
              approved: false,
            },
          ],
        }),
        batch({ id: "b3", order: 2, status: "Queued", pendingSnapshotId: "snap-3" }),
        batch({ id: "b4", order: 3, status: "Queued", pendingSnapshotId: "snap-4" }),
      ],
      {
        currentBatchIndex: 3,
        totalBatches: 4,
        batchStatus: "Queued",
        sceneStatus: "waiting",
        phase: "preparing",
        phaseLabel: "Preparing",
        lastRuntimeEventAt: new Date().toISOString(),
        renderCompletedBatches: 0,
        statusLines: [
          "Preparing — Take A — Batch 3/4 — 100%",
          "Runtime active",
          "The next parts of this scene are being prepared.",
          "0/4 batches complete",
        ],
      },
    );
    const text = formatSceneRenderStatus(m) || "";
    expect(text).toContain("2/4 batches complete");
    expect(text).not.toContain("0/4 batches complete");
  });

  it("places Comfy sampling-step percent on the Live Preview headline", () => {
    const m = master(
      [batch({ id: "b1", order: 0, status: "Generating" })],
      {
        currentBatchIndex: 1,
        totalBatches: 1,
        batchStatus: "Generating",
        batchProgress: 0,
        sceneStatus: "generating",
        progressGrounded: false,
        phase: "sampling",
        phaseLabel: "Generating",
        comfyMessage: "Sampling step 9/20",
        statusLines: ["Render Batch 1/1 — Generating — Sampling"],
      },
    );
    const text = formatSceneRenderStatus(m) || "";
    expect(text).toContain("Generating — Sampling — 45%");
    expect(comfyProgressPercentFromText("Sampling step 9/20")).toBe(45);
    expect(comfyProgressPercentFromText("0/2 batches complete")).toBeNull();
    expect(comfyProgressPercentFromText("Node progress 1/1")).toBeNull();
    expect(comfyProgressPercentFromJob({ message: "Sampling step 4/20", progress: 0.05, progress_grounded: false })).toBe(20);
    expect(appendComfyPercentLine("Render Batch 1/1 — Generating — Sampling", 45)).toBe(
      "Render Batch 1/1 — Generating — Sampling — 45%",
    );
  });

  it("appends a grounded sampler percent only", () => {
    const m = master(
      [batch({ id: "b1", order: 0, status: "Generating" })],
      {
        currentBatchIndex: 1,
        totalBatches: 1,
        batchStatus: "Generating",
        batchProgress: 0.42,
        sceneStatus: "generating",
        progressGrounded: true,
        phase: "sampling",
        phaseLabel: "Generating",
        elapsedActiveTime: 90,
        lastRuntimeEventAt: new Date().toISOString(),
        statusLines: ["Render Batch 1/1 — Generating"],
      },
    );
    const text = formatSceneRenderStatus(m) || "";
    expect(text).toContain("Generating — Sampling — 42%");
    expect(text).toContain("Elapsed: 01:30");
    expect(text).not.toMatch(/0%/);
  });

  it("uses real job progress when deriving", () => {
    const m = master([
      batch({
        id: "b1",
        order: 0,
        status: "Generating",
        generationJobs: [
          {
            id: "j1",
            executionSnapshotId: "e1",
            status: "running",
            locality: "local",
            hostedCancelSupport: "unknown",
            progress: 0.5,
            createdAt: "2026-01-01T00:00:00Z",
          },
        ],
      }),
    ]);
    expect(formatSceneRenderStatus(m)).toBe("Render Batch 1/1 — In Progress — 50%");
  });

  it("hides overlay when all batches complete and idle", () => {
    const m = master([
      batch({
        id: "b1",
        order: 0,
        status: "Approved",
        approvedClip: { assetId: "a1", executionSnapshotId: "e", approvedAt: "t", playable: true },
      }),
      batch({
        id: "b2",
        order: 1,
        status: "CandidateReady",
        candidateVersions: [
          {
            id: "c1",
            executionSnapshotId: "e",
            assetId: "a2",
            label: "Take 1",
            createdAt: "2026-01-01T00:00:00Z",
            approved: false,
          },
        ],
      }),
    ]);
    expect(formatSceneRenderStatus(m)).toBeNull();
    expect(shouldShowSceneRenderStatus(m)).toBe(false);
  });

  it("stale-heals keep_current finished: ignores Repairing statusLines with 0 active jobs", () => {
    const m = master(
      [
        batch({
          id: "b1",
          order: 0,
          status: "Approved",
          approvedClip: { assetId: "a1", executionSnapshotId: "e", approvedAt: "t", playable: true },
          generationJobs: [
            {
              id: "j1",
              executionSnapshotId: "e1",
              status: "completed",
              locality: "local",
              hostedCancelSupport: "unknown",
              progress: 1,
              createdAt: "2026-01-01T00:00:00Z",
            },
          ],
        }),
        batch({
          id: "b2",
          order: 1,
          status: "Approved",
          approvedClip: { assetId: "a2", executionSnapshotId: "e", approvedAt: "t", playable: true },
        }),
      ],
      {
        currentBatchIndex: 2,
        totalBatches: 2,
        batchStatus: "Approved",
        batchProgress: 1,
        sceneStatus: "complete",
        lifecycleStatus: "SCENE_FINISHED_WITH_ACCEPTED_ISSUES",
        sceneFinished: true,
        statusLines: [
          "2/2 batches complete",
          "Dialogue QC — Failed",
          "Scene Not Finished",
          "Repairing Batch 1…",
        ],
      },
    );
    (m as { sceneFinalCheck?: { lifecycleStatus: string } }).sceneFinalCheck = {
      lifecycleStatus: "SCENE_FINISHED_WITH_ACCEPTED_ISSUES",
    };
    expect(isSceneGenerationOverlayActive(m)).toBe(false);
    expect(formatSceneRenderStatus(m)).toBeNull();
    expect(shouldShowSceneRenderStatus(m)).toBe(false);
  });

  it("does not treat a leftover running job on a cancelled window as a live repair", () => {
    const m = master(
      [
        batch({
          id: "b1",
          order: 0,
          status: "Cancelled",
          references: [
            {
              kind: "dialogueQcDiagnostics",
              verdict: "UNCERTAIN",
              sceneFinishedEligible: false,
            },
          ],
          generationJobs: [
            {
              id: "j-stale",
              executionSnapshotId: "snap-stale",
              status: "running",
              locality: "hosted",
              hostedCancelSupport: "unsupported",
              apiUsed: true,
              progress: 0,
              createdAt: "2026-01-01T00:00:00Z",
            },
          ],
        }),
        batch({ id: "b2", order: 1, status: "Cancelled" }),
      ],
      {
        currentBatchIndex: 1,
        totalBatches: 2,
        completedBatches: 0,
        renderCompletedBatches: 0,
        batchStatus: "Cancelled",
        sceneStatus: "cancelled",
        lifecycleStatus: "SCENE_NOT_FINISHED",
        overallBatchesLabel: "0/2 batches complete",
      },
    );
    expect(isSceneGenerationOverlayActive(m)).toBe(false);
    expect(formatSceneRenderStatus(m)).toBeNull();
  });

  it("hides Final Check / Re-verifying / Repairing from Preview Monitor (Advanced-only)", () => {
    const baseBlocks = [
      batch({
        id: "b1",
        order: 0,
        status: "Approved",
        approvedClip: { assetId: "a1", executionSnapshotId: "e", approvedAt: "t", playable: true },
      }),
    ];
    const fc = master(baseBlocks, {
      currentBatchIndex: 1,
      totalBatches: 1,
      batchStatus: "Approved",
      batchProgress: 1,
      sceneStatus: "complete",
      lifecycleStatus: "FINAL_CHECK",
      statusLines: ["2/2 batches complete", "Dialogue QC — Failed", "Repairing Batch 1…"],
    });

    expect(isSceneGenerationOverlayActive(fc)).toBe(false);
    expect(shouldShowSceneRenderStatus(fc)).toBe(false);
    expect(formatSceneRenderStatus(fc)).toBeNull();

    const rv = master(baseBlocks, {
      currentBatchIndex: 1,
      totalBatches: 1,
      batchStatus: "Approved",
      batchProgress: 1,
      sceneStatus: "complete",
      lifecycleStatus: "REVERIFYING",
    });
    expect(isSceneGenerationOverlayActive(rv)).toBe(false);
    expect(formatSceneRenderStatus(rv)).toBeNull();

    const rp = master(
      [
        batch({ id: "b1", order: 0, status: "NeedsDialogueRetake" }),
        batch({
          id: "b2",
          order: 1,
          status: "Approved",
          approvedClip: { assetId: "a2", executionSnapshotId: "e", approvedAt: "t", playable: true },
        }),
      ],
      {
        currentBatchIndex: 1,
        totalBatches: 2,
        batchStatus: "NeedsDialogueRetake",
        batchProgress: 0,
        sceneStatus: "idle",
        lifecycleStatus: "REPAIRING",
      },
    );
    expect(isSceneGenerationOverlayActive(rp)).toBe(false);
    expect(formatSceneRenderStatus(rp)).toBeNull();
    expect(shouldShowSceneRenderStatus(rp)).toBe(false);
  });

  it("shows Generation Complete notice after Final Check lifecycle (monitor dismissible)", () => {
    const m = master(
      [
        batch({
          id: "b1",
          order: 0,
          status: "Approved",
          approvedClip: { assetId: "a1", executionSnapshotId: "e", approvedAt: "t", playable: true },
        }),
      ],
      {
        currentBatchIndex: 1,
        totalBatches: 1,
        batchStatus: "Approved",
        batchProgress: 1,
        sceneStatus: "complete",
        lifecycleStatus: "FINAL_CHECK",
      },
    );
    expect(isSceneGenerationOverlayActive(m)).toBe(false);
    expect(formatSceneRenderStatus(m)).toBeNull();
    const notice = sceneGenerationCompleteNotice(m);
    expect(notice?.percent).toBe(100);
    expect(notice?.fingerprint).toContain("FINAL_CHECK");
  });

  it("does not call Generation Complete when the open take still owes a window", () => {
    const m = master(
      [
        batch({ id: "b1", order: 0, status: "CandidateReady" }),
        batch({ id: "b2", order: 1, status: "QC_Pending" }),
        batch({ id: "b3", order: 2, status: "QC_Pending" }),
      ],
      {
        currentBatchIndex: 1,
        totalBatches: 3,
        batchStatus: "CandidateReady",
        batchProgress: 1,
        sceneStatus: "idle",
        lifecycleStatus: "SCENE_NOT_FINISHED",
      },
    );
    const open = m as SceneTimelineMaster & {
      currentSceneTakeId?: string;
      sceneTakes?: Array<{ id: string; status: string; batches: Array<{ batchId: string; order: number; assetId?: string }> }>;
    };
    open.currentSceneTakeId = "stk_l";
    open.sceneTakes = [
      {
        id: "stk_l",
        status: "incomplete",
        batches: [
          { batchId: "b1", order: 0, assetId: "win1" },
          { batchId: "b2", order: 1 },
          { batchId: "b3", order: 2 },
        ],
      },
    ];
    expect(sceneGenerationCompleteNotice(m)).toBeNull();
  });


  it("Draft batch idle: shouldShow false, format null (no Generating chrome)", () => {
    const m = master(
      [batch({ id: "b1", order: 0, status: "Draft" })],
      {
        currentBatchIndex: 1,
        totalBatches: 1,
        batchStatus: "Draft",
        batchProgress: 0,
        sceneStatus: "idle",
        message: "",
        statusLines: [],
        lifecycleStatus: "SCENE_NOT_FINISHED",
      },
    );
    expect(isSceneGenerationOverlayActive(m)).toBe(false);
    expect(formatSceneRenderStatus(m)).toBeNull();
    expect(shouldShowSceneRenderStatus(m)).toBe(false);
    expect(sceneGenerationCompleteNotice(m)).toBeNull();
  });

  it("does not show Generation Complete when no window has a rendered asset", () => {
    const m = master(
      [
        batch({ id: "b1", order: 0, status: "Draft" }),
        batch({ id: "b2", order: 1, status: "Draft" }),
        batch({ id: "b3", order: 2, status: "Draft" }),
      ],
      {
        currentBatchIndex: 0,
        totalBatches: 3,
        batchStatus: "Draft",
        batchProgress: 0,
        sceneStatus: "idle",
        lifecycleStatus: "SCENE_NOT_FINISHED",
      },
    );
    expect(sceneGenerationCompleteNotice(m)).toBeNull();
  });

  it("ignores leaked idle statusLines even if lifecycle falsely RENDERING", () => {
    const m = master(
      [batch({ id: "b1", order: 0, status: "Draft" })],
      {
        currentBatchIndex: 1,
        totalBatches: 1,
        batchStatus: "Draft",
        batchProgress: 0,
        sceneStatus: "idle",
        statusLines: ["Render Batch 1/1 — idle"],
        lifecycleStatus: "RENDERING",
      },
    );
    expect(isSceneGenerationOverlayActive(m)).toBe(false);
    expect(formatSceneRenderStatus(m)).toBeNull();
    expect(shouldShowSceneRenderStatus(m)).toBe(false);
  });

  it("shows standby on the Preview notice until a live batch status exists", () => {
    expect(previewGenerationNotice(null, true)).toBe("Stand By... Generation Processing.");
    expect(previewGenerationNotice(null, false)).toBeNull();
    const live = master([
      batch({
        id: "b1",
        order: 0,
        status: "Generating",
        generationJobs: [
          {
            id: "j1",
            executionSnapshotId: "e1",
            status: "running",
            locality: "local",
            hostedCancelSupport: "unknown",
            progress: 0.5,
            createdAt: "2026-01-01T00:00:00Z",
          },
        ],
      }),
    ]);
    expect(previewGenerationNotice(live, true)).toBe("Render Batch 1/1 — In Progress — 50%");
    expect(PREVIEW_GENERATION_STANDBY).toBe("Stand By... Generation Processing.");
  });
});

describe("completedGeneratedBatches", () => {
  it("requires playable take + completed status", () => {
    const m = master([
      batch({
        id: "b1",
        order: 0,
        status: "Approved",
        approvedClip: { assetId: "a1", executionSnapshotId: "e", approvedAt: "t", playable: true },
      }),
      batch({ id: "b2", order: 1, status: "Approved" }),
      batch({
        id: "b3",
        order: 2,
        status: "CandidateReady",
        candidateVersions: [
          {
            id: "c1",
            executionSnapshotId: "e",
            assetId: "a3",
            label: "Take",
            createdAt: "t",
            approved: false,
          },
        ],
      }),
    ]);
    expect(completedGeneratedBatches(m).map((b) => b.id)).toEqual(["b1", "b3"]);
  });
});
