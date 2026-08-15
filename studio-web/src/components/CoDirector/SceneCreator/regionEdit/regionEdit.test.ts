import { describe, expect, it } from "vitest";
import type { SceneShot } from "../types";
import {
  compileRegionEditFinalPrompt,
  formatInpaintCollapsedSummary,
  inferRegionEditStage,
  isMaskStale,
  listRegionEditSources,
  regionEditCapability,
  resolveRegionEditSource,
  approvedLookBlocksFinal,
  UNSUPPORTED_REGION_EDIT_MESSAGE,
} from "./regionEdit";

function shot(partial: Partial<SceneShot> = {}): SceneShot {
  return {
    id: "s1",
    project_id: "p",
    scene_id: "sc",
    sheet_id: "sheet",
    ers_package_id: "",
    ers_runtime: false,
    intent: "Two shot at the bar",
    prompt: "Two shot at the bar",
    character_ids: [],
    prop_entity_ids: [],
    camera: {
      camera_id: "cam-1",
      camera_slot: 0,
      label: "Camera 1",
      orientation: "N",
      fov_preset: "medium",
      cinematic: { shot_size: "medium_wide", motion: "static", framing: "two_shot" },
    },
    generator: { local_enabled: true, api_enabled: false, local_family: "zimage", api_provider: "", api_model: "" },
    candidates: [],
    take_memory: {
      originalTakeIntent: {},
      sceneErsState: {},
      characterIdentity: {},
      blocking: {},
      camera: {},
      takeState: {},
      userCorrection: {},
    },
    created_at: "",
    updated_at: "",
    ...partial,
  };
}

describe("regionEdit capability labels", () => {
  it("labels zimage as Native Inpaint", () => {
    expect(regionEditCapability("zimage").label).toBe("Native Inpaint");
    expect(regionEditCapability("zimage").supportsInpaint).toBe(true);
  });

  it("labels flux as Image Edit, not Native Inpaint", () => {
    expect(regionEditCapability("flux").label).toBe("Image Edit");
    expect(regionEditCapability("flux").supportsInpaint).toBe(false);
    expect(regionEditCapability("flux").supportsEditing).toBe(true);
  });

  it("labels qwen2512 and illustrious as Unsupported", () => {
    expect(regionEditCapability("qwen2512").label).toBe("Unsupported");
    expect(regionEditCapability("illustrious").label).toBe("Unsupported");
    expect(UNSUPPORTED_REGION_EDIT_MESSAGE).toContain("Choose Z-Image");
  });
});

describe("resolveRegionEditSource", () => {
  it("prefers the approved candidate asset", () => {
    const source = resolveRegionEditSource({
      shot: shot({
        approved_candidate_id: "c1",
        candidates: [
          {
            id: "c1",
            shot_id: "s1",
            index: 0,
            job_id: "j1",
            asset_id: "asset-approved",
            status: "complete",
            source: "local",
            family: "zimage",
            model: "zimage",
            provenance_label: "LOCAL",
            take_label: "Take A",
            camera_state_version: 2,
          },
        ],
      }),
    });
    expect(source?.sourceAssetId).toBe("asset-approved");
    expect(source?.cameraStateVersion).toBe(2);
  });

  it("falls back to a ready cinematographer preview", () => {
    const source = resolveRegionEditSource({
      shot: shot(),
      selectedCameraId: "cam-1",
      cinematographer: {
        scene_id: "sc",
        selected_camera_id: "cam-1",
        cameras: [
          {
            cameraId: "cam-1",
            cameraSlot: 0,
            label: "Camera 1",
            enabled: true,
            cameraStateVersion: 5,
            cameraStateHash: "h",
            lineage: { cameraId: "cam-1", cameraStateVersion: 5, cameraStateHash: "h", previewAssetId: "preview-9", previewStatus: "ready", locked: true },
            current: {} as never,
          },
        ],
      } as never,
    });
    expect(source?.sourceAssetId).toBe("preview-9");
    expect(source?.fromPreview).toBe(true);
  });
});

describe("mask stale vs source camera version", () => {
  it("marks the mask stale when the camera version changes", () => {
    expect(
      isMaskStale({
        maskSourceAssetId: "a1",
        currentSourceAssetId: "a1",
        maskCameraVersion: 2,
        currentCameraVersion: 3,
      }),
    ).toBe(true);
  });

  it("is not stale when the source and camera version match", () => {
    expect(
      isMaskStale({
        maskSourceAssetId: "a1",
        currentSourceAssetId: "a1",
        maskCameraVersion: 2,
        currentCameraVersion: 2,
      }),
    ).toBe(false);
  });
});

describe("Strategy B compile", () => {
  it("includes approved remove text for final prompt", () => {
    const compiled = compileRegionEditFinalPrompt(
      shot({
        approved_candidate_id: "e1",
        generator: { local_enabled: true, api_enabled: false, local_family: "zimage", api_provider: "", api_model: "" },
        candidates: [
          {
            id: "e1",
            shot_id: "s1",
            index: 0,
            job_id: "j",
            asset_id: "edited",
            status: "complete",
            source: "local",
            family: "zimage",
            model: "zimage",
            provenance_label: "LOCAL",
            take_label: "Region Edit A",
            kind: "region_edit",
          },
        ],
        take_memory: {
          originalTakeIntent: {},
          sceneErsState: {},
          characterIdentity: {},
          blocking: {},
          camera: {},
          takeState: {},
          userCorrection: {
            region_edits: [
              {
                operation: "remove",
                prompt: "the extra person on the left",
                maskAssetId: "mask-1",
                candidate_id: "e1",
                approved: true,
              },
            ],
          },
        },
      }),
      "Two shot at the bar",
    );
    expect(compiled.prompt).toContain("Do not include the removed extra");
    expect(compiled.prompt).toContain("the extra person on the left");
    expect(compiled.strategy).toBe("A");
    expect(compiled.sourceAssetId).toBe("edited");
  });

  it("returns Strategy C when the selected family cannot keep painted pixels", () => {
    const compiled = compileRegionEditFinalPrompt(
      shot({
        approved_candidate_id: "e1",
        generator: { local_enabled: true, api_enabled: false, local_family: "qwen2512", api_provider: "", api_model: "" },
        candidates: [
          {
            id: "e1",
            shot_id: "s1",
            index: 0,
            job_id: "j",
            asset_id: "edited",
            status: "complete",
            source: "local",
            family: "qwen2512",
            model: "qwen2512",
            provenance_label: "LOCAL",
            take_label: "Region Edit A",
            kind: "region_edit",
          },
        ],
        take_memory: {
          originalTakeIntent: {},
          sceneErsState: {},
          characterIdentity: {},
          blocking: {},
          camera: {},
          takeState: {},
          userCorrection: {
            region_edits: [
              {
                operation: "remove",
                prompt: "the extra person on the left",
                maskAssetId: "mask-1",
                candidate_id: "e1",
                approved: true,
              },
            ],
          },
        },
      }),
      "Two shot at the bar",
    );
    expect(compiled.strategy).toBe("C");
    expect(compiled.visualInheritanceBlocked).toBe(true);
    expect(compiled.sourceAssetId).toBeUndefined();
  });
});

describe("stage inference", () => {
  it("uses preview for draft / preview sources", () => {
    expect(inferRegionEditStage({ sourceAssetId: "p", fromPreview: true })).toBe("preview");
    expect(inferRegionEditStage({ sourceAssetId: "p" }, { quality_profile: "draft" } as never)).toBe("preview");
    expect(inferRegionEditStage({ sourceAssetId: "p" })).toBe("final");
  });
});

describe("approved look vs Final Quality Render", () => {
  it("does not block Final after an approved preview-stage region edit", () => {
    expect(
      approvedLookBlocksFinal(
        shot({
          approved_candidate_id: "e1",
          candidates: [
            {
              id: "e1",
              shot_id: "s1",
              index: 0,
              job_id: "j",
              asset_id: "edited",
              status: "complete",
              source: "local",
              family: "zimage",
              model: "zimage",
              provenance_label: "LOCAL",
              kind: "region_edit",
              quality_profile: "draft",
            },
          ],
        }),
      ),
    ).toBe(false);
  });

  it("blocks Final after an approved production take", () => {
    expect(
      approvedLookBlocksFinal(
        shot({
          approved_candidate_id: "t1",
          candidates: [
            {
              id: "t1",
              shot_id: "s1",
              index: 0,
              job_id: "j",
              asset_id: "final",
              status: "complete",
              source: "local",
              family: "zimage",
              model: "zimage",
              provenance_label: "LOCAL",
              quality_profile: "final",
            },
          ],
        }),
      ),
    ).toBe(true);
  });
});

describe("inpaint source list and collapsed summary", () => {
  it("lists the ready preview as Low-Res Preview", () => {
    const sources = listRegionEditSources({
      shot: shot(),
      selectedCameraId: "cam-1",
      cinematographer: {
        scene_id: "sc",
        selected_camera_id: "cam-1",
        cameras: [
          {
            cameraId: "cam-1",
            cameraSlot: 0,
            label: "Camera 1",
            enabled: true,
            cameraStateVersion: 5,
            cameraStateHash: "h",
            lineage: {
              cameraId: "cam-1",
              cameraStateVersion: 5,
              cameraStateHash: "h",
              previewAssetId: "preview-9",
              previewStatus: "ready",
              locked: true,
            },
            current: {} as never,
          },
        ],
      } as never,
    });
    expect(sources[0]?.label).toBe("Low-Res Preview");
    expect(sources[0]?.assetId).toBe("preview-9");
  });

  it("summarizes approved edits and mask-ready state", () => {
    expect(formatInpaintCollapsedSummary(shot(), true)).toBe("Mask Ready");
    expect(
      formatInpaintCollapsedSummary(
        shot({
          approved_candidate_id: "e1",
          candidates: [
            {
              id: "e1",
              shot_id: "s1",
              index: 0,
              job_id: "j",
              asset_id: "edited",
              status: "complete",
              source: "local",
              family: "zimage",
              model: "zimage",
              provenance_label: "LOCAL",
              take_label: "Inpaint A",
              kind: "region_edit",
            },
          ],
        }),
        false,
      ),
    ).toBe("1 approved edit");
  });
});
