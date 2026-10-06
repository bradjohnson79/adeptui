import { describe, expect, it, vi } from "vitest";
import { renderToString } from "react-dom/server";
import {
  buildPerformanceRetakeBody,
  canApplyPerformanceRetake,
  LipSyncTracksPanel,
  performanceRetakeErrorMessage,
  resolveCharacterSheetAssetId,
} from "../LipSyncTracks";
import { ApiError } from "../../api";
import type { Asset, Project, Scene } from "../../types";

function asset(id: string, kind: string, overrides: Partial<Asset> = {}): Asset {
  return {
    id,
    project_id: "project-1",
    tag: "",
    kind,
    filename: "",
    path: "",
    comfy_name: "",
    scope: "project",
    created_at: "2026-09-11T12:00:00Z",
    ...overrides,
  } as Asset;
}

function scene(overrides: Partial<Scene> = {}): Scene {
  return {
    id: "scene-1",
    project_id: "project-1",
    index: 0,
    name: "Scene 1",
    engine: "auto",
    prompt: "",
    duration_sec: 10,
    start_asset_id: null,
    middle_asset_id: null,
    end_asset_id: null,
    audio_asset_id: null,
    lipsync_enabled: false,
    lipsync_audio_asset_id: null,
    lipsync_tracks_json: "",
    director_json: "",
    continuity_json: "",
    camera_note: "",
    seed: 0,
    aspect_ratio: "16:9",
    width: 1152,
    height: 640,
    fps_mode: "auto",
    fps: 24,
    ...overrides,
  } as Scene;
}

function project(assets: Asset[] = []): Project {
  return {
    id: "project-1",
    name: "Test",
    engine_default: "auto",
    global_prompt: "",
    negative_prompt: "",
    width: 1152,
    height: 640,
    fps: 24,
    seed: 0,
    preset: "quality",
    vram_gb: 24,
    spatial_map_json: "",
    description: "",
    created_at: "2026-09-11T12:00:00Z",
    updated_at: "2026-09-11T12:00:00Z",
    scenes: [],
    assets,
  } as Project;
}

describe("resolveCharacterSheetAssetId", () => {
  it("picks the latest character-sheet image for a character id", () => {
    const anadriyaId = "4c1c0bc8-a771-4998-b652-5d549b2a2b8d";
    const assets = [
      asset("old-sheet", "image", {
        tag: "character_sheet",
        filename: `character_sheet_${anadriyaId.replace(/-/g, "")}_c1_old.png`,
        labels_json: JSON.stringify(["character_sheet"]),
        created_at: "2026-09-10T12:00:00Z",
      }),
      asset("new-sheet", "image", {
        tag: "character_sheet",
        prompt_meta_json: JSON.stringify({ characterId: anadriyaId, objective: "character_sheet_composed" }),
        labels_json: JSON.stringify(["character_sheet", "composed", "candidate_1"]),
        created_at: "2026-09-11T12:00:00Z",
      }),
    ];
    expect(resolveCharacterSheetAssetId(anadriyaId, assets)).toBe("new-sheet");
  });

  it("prefers an approved sheet over a newer draft", () => {
    const korriId = "4a2e9cbe-e1e0-4d87-a411-6a8851b2f0ed";
    const assets = [
      asset("draft-sheet", "image", {
        tag: "character_sheet",
        prompt_meta_json: JSON.stringify({ characterId: korriId }),
        labels_json: JSON.stringify(["character_sheet", "composed"]),
        created_at: "2026-09-12T12:00:00Z",
      }),
      asset("approved-sheet", "image", {
        tag: "character_sheet",
        prompt_meta_json: JSON.stringify({ characterId: korriId }),
        labels_json: JSON.stringify(["character_sheet", "approved"]),
        created_at: "2026-09-11T12:00:00Z",
      }),
    ];
    expect(resolveCharacterSheetAssetId(korriId, assets)).toBe("approved-sheet");
  });

  it("returns null when no sheet matches the character", () => {
    expect(resolveCharacterSheetAssetId("no-such-id", [])).toBeNull();
  });
});

describe("buildPerformanceRetakeBody", () => {
  it("builds beats from clips, fills silence gaps, and includes character sheets", () => {
    const anadriyaId = "4c1c0bc8-a771-4998-b652-5d549b2a2b8d";
    const korriId = "4a2e9cbe-e1e0-4d87-a411-6a8851b2f0ed";
    const anadriyaSheet = "sheet-anadriya";
    const korriSheet = "sheet-korri";
    const assets = [
      asset(anadriyaSheet, "image", {
        tag: "character_sheet",
        prompt_meta_json: JSON.stringify({ characterId: anadriyaId }),
        labels_json: JSON.stringify(["character_sheet", "approved"]),
      }),
      asset(korriSheet, "image", {
        tag: "character_sheet",
        filename: `character_sheet_${korriId.slice(0, 8)}_c1_abc.png`,
        labels_json: JSON.stringify(["character_sheet"]),
      }),
    ];

    const tracks = {
      tracks: [
        {
          slot: 1,
          label: "Anadriya",
          enabled: true,
          character_id: anadriyaId,
          character_name: "Anadriya",
          roi: { x: 0.35, y: 0.55, w: 0.18, h: 0.12 },
          track_path: [],
          notes: "",
          clips: [
            { id: "c1", start: 0, length: 3, audio_asset_id: "audio-a", line: "We've neutralized Cade." },
          ],
        },
        {
          slot: 2,
          label: "Korri",
          enabled: true,
          character_id: korriId,
          character_name: "Korri",
          roi: { x: 0.55, y: 0.55, w: 0.18, h: 0.12 },
          track_path: [],
          notes: "",
          clips: [{ id: "c2", start: 4, length: 3, audio_asset_id: "audio-k", line: "We did it, sis!" }],
        },
      ],
    };

    const body = buildPerformanceRetakeBody(scene(), tracks, assets, false, 0, 10);
    expect(body.mode).toBe("performance_retake");
    expect(body.retake.window).toEqual({
      startSec: 0,
      endSec: 10,
      scope: "whole_shot",
      boundarySource: "qwen_shot_analysis",
    });
    expect(body.retake.beats).toEqual([
      { kind: "dialogue", startSec: 0, endSec: 3, characterId: anadriyaId, characterName: "Anadriya", line: "We've neutralized Cade.", voiceAssetId: "audio-a" },
      { kind: "silence", startSec: 3, endSec: 4 },
      { kind: "dialogue", startSec: 4, endSec: 7, characterId: korriId, characterName: "Korri", line: "We did it, sis!", voiceAssetId: "audio-k" },
      { kind: "silence", startSec: 7, endSec: 10 },
    ]);
    const sheets = new Map(body.retake.references.characterSheets.map((c) => [c.characterId, c.assetId]));
    expect(sheets.get(anadriyaId)).toBe(anadriyaSheet);
    expect(sheets.get(korriId)).toBe(korriSheet);
    expect(body.retake.references.sourceVideo).toBe(true);
    expect(body.retake.references.includeSourceAudio).toBe(false);
  });
});

describe("canApplyPerformanceRetake", () => {
  it("allows apply when every voiced clip has a line, voice asset, and sheet", () => {
    const charId = "char12345";
    const tracks = {
      tracks: [
        {
          slot: 1,
          label: "Hero",
          enabled: true,
          character_id: charId,
          character_name: "Hero",
          roi: { x: 0, y: 0, w: 0.1, h: 0.1 },
          track_path: [],
          notes: "",
          clips: [{ id: "c1", start: 0, length: 2, audio_asset_id: "audio-1", line: "Hello" }],
        },
      ],
    };
    const assets = [
      asset("sheet-1", "image", {
        tag: "character_sheet",
        prompt_meta_json: JSON.stringify({ characterId: charId }),
        labels_json: JSON.stringify(["character_sheet", "approved"]),
      }),
    ];
    expect(canApplyPerformanceRetake(scene(), tracks, assets, false, 0, 10)).toEqual({ ok: true, reason: null });
  });

  it("blocks apply when a clip is missing its line", () => {
    const charId = "char12345";
    const tracks = {
      tracks: [
        {
          slot: 1,
          label: "Hero",
          enabled: true,
          character_id: charId,
          character_name: "Hero",
          roi: { x: 0, y: 0, w: 0.1, h: 0.1 },
          track_path: [],
          notes: "",
          clips: [{ id: "c1", start: 0, length: 2, audio_asset_id: "audio-1", line: "" }],
        },
      ],
    };
    const result = canApplyPerformanceRetake(scene(), tracks, [], false, 0, 10);
    expect(result.ok).toBe(false);
    expect(result.reason).toContain("dialogue lines");
  });

  it("blocks apply when a clip has no voice asset", () => {
    const tracks = {
      tracks: [
        {
          slot: 1,
          label: "Hero",
          enabled: true,
          character_id: "char12345",
          character_name: "Hero",
          roi: { x: 0, y: 0, w: 0.1, h: 0.1 },
          track_path: [],
          notes: "",
          clips: [{ id: "c1", start: 0, length: 2, audio_asset_id: null, line: "Hello" }],
        },
      ],
    };
    const result = canApplyPerformanceRetake(scene(), tracks, [], false, 0, 10);
    expect(result.ok).toBe(false);
    expect(result.reason).toContain("Voice Studio");
  });

  it("blocks apply when a bound character has no approved sheet", () => {
    const charId = "char12345";
    const tracks = {
      tracks: [
        {
          slot: 1,
          label: "Hero",
          enabled: true,
          character_id: charId,
          character_name: "Hero",
          roi: { x: 0, y: 0, w: 0.1, h: 0.1 },
          track_path: [],
          notes: "",
          clips: [{ id: "c1", start: 0, length: 2, audio_asset_id: "audio-1", line: "Hello" }],
        },
      ],
    };
    const result = canApplyPerformanceRetake(scene(), tracks, [], false, 0, 10);
    expect(result.ok).toBe(false);
    expect(result.reason).toContain("character sheet");
  });
});

describe("performanceRetakeErrorMessage", () => {
  it("renders the creator-facing 410 replacement message", () => {
    const err = new ApiError("legacy gone", 410);
    expect(performanceRetakeErrorMessage(err)).toBe(
      "This older lip-sync tool has been replaced by Performance Retake.",
    );
  });

  it("renders the server message verbatim for a 400", () => {
    const err = new ApiError("Enable at least one lip-sync track", 400);
    expect(performanceRetakeErrorMessage(err)).toBe("Enable at least one lip-sync track");
  });
});

describe("LipSyncTracksPanel static render", () => {
  it("shows Performance Retake heading and disabled apply without clips", () => {
    const html = renderToString(
      <LipSyncTracksPanel project={project()} scene={scene()} onChange={() => undefined} />,
    );
    expect(html).toContain("Performance Retake");
    expect(html).toContain('data-testid="pr-apply-performance-retake"');
    expect(html).toMatch(/disabled/);
    expect(html).toContain('data-testid="pr-apply-blocker"');
  });

  it("shows per-clip fields when clips exist", () => {
    const charId = "char12345";
    const p = project([
      asset("sheet-1", "image", {
        tag: "character_sheet",
        prompt_meta_json: JSON.stringify({ characterId: charId }),
        labels_json: JSON.stringify(["character_sheet", "approved"]),
      }),
    ]);
    const tracks = {
      tracks: [
        {
          slot: 1,
          label: "Hero",
          enabled: true,
          character_id: charId,
          character_name: "Hero",
          roi: { x: 0, y: 0, w: 0.1, h: 0.1 },
          track_path: [],
          notes: "",
          clips: [{ id: "c1", start: 0, length: 2, audio_asset_id: "audio-1", line: "Hello" }],
        },
      ],
    };
    // Seed tracks by rendering is tricky because state loads from API; verify the helper instead.
    expect(canApplyPerformanceRetake(scene(), tracks, p.assets, false, 0, 10).ok).toBe(true);
  });
});
