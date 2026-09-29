import { describe, expect, it } from "vitest";
import {
  anyTimelineGeneratorExecutable,
  canonicalGeneratorId,
  draftPathwayCopy,
  generatorOptionsFromPayload,
  generatorQualityControl,
  joinProductionControlVideoOptions,
  nextTurboLoraState,
  promoteCopy,
  resolveGeneratorOption,
  resolveNativeAudioState,
  supportsTurboLora,
  supportsVideoMotionReferences,
  usesFastQuality,
} from "./draftCapabilities";

const payload = {
  timelineAdapters: [
    {
      id: "minimax-h3",
      label: "MiniMax H3",
      aliases: ["minimax-h3-local", "minimax-h3-t2v-local"],
      supportsVideoReferences: true,
      supportsAudioReferences: true,
      maximumReferenceVideos: 3,
      maximumReferenceAudio: 3,
    },
    {
      id: "ltx-2.5-distilled",
      label: "LTX 2.5",
      aliases: ["ltx-2.5"],
      supportsVideoReferences: true,
      maximumReferenceVideos: 1,
    },
    {
      id: "seedance-2.0",
      label: "Seedance 2.0",
      aliases: ["seedance-api", "seedance-fal", "fal_seedance"],
      supportsVideoReferences: true,
      maximumReferenceVideos: 1,
    },
    {
      id: "seedance-kie",
      label: "Seedance (Kie)",
      aliases: [],
      supportsVideoReferences: false,
      maximumReferenceVideos: 0,
    },
  ],
};

describe("draftCapabilities", () => {
  it("maps persist aliases to product ids", () => {
    expect(canonicalGeneratorId("minimax-h3")).toBe("minimax-h3");
    expect(canonicalGeneratorId("minimax-h3-local")).toBe("minimax-h3");
    expect(canonicalGeneratorId("minimax-h3-t2v-local")).toBe("minimax-h3");
    expect(canonicalGeneratorId("seedance-api")).toBe("seedance-2.0");
    expect(canonicalGeneratorId("seedance-fal")).toBe("seedance-2.0");
    expect(canonicalGeneratorId("fal_seedance_25")).toBe("seedance-2.5");
    expect(canonicalGeneratorId("ltx-2.5-distilled")).toBe("ltx-2.5-distilled");
    expect(canonicalGeneratorId("ltx-2.5")).toBe("ltx-2.5-distilled");
    expect(canonicalGeneratorId("seedance-kie")).toBe("seedance-kie");
  });

  it("accepts scene-engine aliases without collapsing Kie onto fal", () => {
    const options = generatorOptionsFromPayload(payload);
    const minimax = resolveGeneratorOption(options, "minimax-h3-t2v-local");
    expect(minimax?.id).toBe("minimax-h3");
    expect(supportsVideoMotionReferences(minimax)).toBe(true);
    expect(minimax?.maximumReferenceVideos).toBe(3);
    expect(minimax?.maximumReferenceAudio).toBe(3);
    const seedanceFal = resolveGeneratorOption(options, undefined, "seedance-api");
    expect(seedanceFal?.id).toBe("seedance-2.0");
    const seedanceKie = resolveGeneratorOption(options, "seedance-kie");
    expect(seedanceKie?.id).toBe("seedance-kie");
    expect(seedanceKie?.id).not.toBe(seedanceFal?.id);
  });

  it("presents backend-joined generators", () => {
    const rows = joinProductionControlVideoOptions(
      { models: [{ id: "ltx-2.5-distilled", executable: true }] },
      {
        generators: [
          {
            id: "ltx-2.5-distilled",
            label: "LTX 2.5",
            executable: true,
            readiness: "Ready",
          },
          {
            id: "minimax-h3",
            label: "MiniMax H3",
            executable: false,
            disabledReason: "Timeline reference-to-video only",
            capabilityLabel: "Requires Setup",
          },
        ],
        timelineAdapters: [
          { id: "ltx-2.5-distilled", label: "LTX 2.5", aliases: ["ltx-2.5"], draftPathway: "local_live" },
        ],
      },
    );
    const h3 = rows.find((item) => item.id === "minimax-h3");
    expect(h3?.executable).toBe(false);
    expect(String(h3?.disabledReason || "").length).toBeGreaterThan(0);
    const ltx = rows.find((item) => item.id === "ltx-2.5-distilled");
    expect(ltx?.executable).toBe(true);
    expect(ltx?.draftPathway).toBe("local_live");
  });

  it("threads supportsTextToVideo from the adapter capability join", () => {
    const rows = joinProductionControlVideoOptions(null, {
      generators: [
        { id: "ltx-2.5-distilled", label: "LTX 2.5", executable: true, timelineAdapterId: "ltx-2.5-distilled" },
        { id: "minimax-h3", label: "MiniMax H3", executable: true, timelineAdapterId: "minimax-h3" },
        { id: "seedance-2.0", label: "Seedance 2.0", executable: true, timelineAdapterId: "seedance-2.0" },
      ],
      timelineAdapters: [
        { id: "ltx-2.5-distilled", label: "LTX 2.5", aliases: ["ltx-2.5"], supportsTextToVideo: false, supportsImageToVideo: true },
        { id: "minimax-h3", label: "MiniMax H3", aliases: ["minimax-h3-local"], supportsTextToVideo: false, supportsImageToVideo: false },
        { id: "seedance-2.0", label: "Seedance 2.0", aliases: ["seedance-api"], supportsTextToVideo: true, supportsImageToVideo: true },
      ],
    });
    expect(rows.find((item) => item.id === "ltx-2.5-distilled")?.supportsTextToVideo).toBe(false);
    expect(rows.find((item) => item.id === "minimax-h3")?.supportsTextToVideo).toBe(false);
    expect(rows.find((item) => item.id === "seedance-2.0")?.supportsTextToVideo).toBe(true);
  });

  it("threads supportsTurboLora from the capability join", () => {
    const rows = joinProductionControlVideoOptions(null, {
      generators: [
        { id: "ltx-2.5-full", label: "LTX 2.5 Full", executable: true, supportsTurboLora: true },
        { id: "ltx-2.5-distilled", label: "LTX 2.5 Distilled", executable: true, supportsTurboLora: false },
        { id: "minimax-h3", label: "MiniMax H3", executable: true },
      ],
    });
    expect(supportsTurboLora(rows.find((row) => row.id === "ltx-2.5-full"))).toBe(true);
    expect(supportsTurboLora(rows.find((row) => row.id === "ltx-2.5-distilled"))).toBe(false);
    expect(supportsTurboLora(rows.find((row) => row.id === "minimax-h3"))).toBe(false);
    expect(nextTurboLoraState(true, rows.find((row) => row.id === "ltx-2.5-full"))).toBe(true);
    expect(nextTurboLoraState(true, rows.find((row) => row.id === "minimax-h3"))).toBe(false);
  });

  it("uses Fast/Quality copy for MiniMax H3 from the product id", () => {
    const rows = joinProductionControlVideoOptions(null, {
      generators: [
        { id: "minimax-h3", label: "MiniMax H3", executable: true, draftPathway: "local_live" },
      ],
    });
    const h3 = rows.find((row) => row.id === "minimax-h3");
    expect(usesFastQuality(h3)).toBe(true);
    expect(draftPathwayCopy("local_live", h3)).toContain("Same picture size");
    expect(promoteCopy(true, h3)).toContain("Quality starts a new generation");
  });

  it("uses Fast/Quality copy for LTX 2.5 only when flagged", () => {
    const rows = joinProductionControlVideoOptions(null, {
      generators: [
        { id: "ltx-2.5-distilled", label: "LTX 2.5", executable: true, usesFastQuality: true, draftPathway: "local_live" },
      ],
    });
    const ltx25 = rows.find((row) => row.id === "ltx-2.5-distilled");
    expect(usesFastQuality(ltx25)).toBe(true);
    expect(draftPathwayCopy("local_live", ltx25)).toContain("Same picture size");
    expect(promoteCopy(true, ltx25)).toContain("Quality starts a new generation");
  });

  it("merges Production Control I2V workflow records even when Timeline generators omit them", () => {
    const rows = joinProductionControlVideoOptions(
      {
        models: [
          {
            id: "minimax-h3",
            workflowCapabilities: {
              i2v: { supported: true, executable: true, readiness: "Available on demand" },
              t2v: { supported: true, executable: true, readiness: "Available on demand" },
              multiFrame: { supported: false, executable: false },
            },
          },
          {
            id: "ltx-2.5-distilled",
            workflowCapabilities: {
              i2v: { supported: true, executable: true, readiness: "Ready" },
              multiFrame: { supported: false, executable: false },
            },
          },
        ],
      },
      {
        generators: [
          { id: "minimax-h3", label: "MiniMax H3", executable: false, supportsImageToVideo: false },
          { id: "ltx-2.5-distilled", label: "LTX 2.5", executable: false, supportsImageToVideo: false },
        ],
      },
    );
    expect(rows.find((row) => row.id === "minimax-h3")?.workflowCapabilities?.i2v?.supported).toBe(true);
    expect(rows.find((row) => row.id === "ltx-2.5-distilled")?.workflowCapabilities?.multiFrame?.supported).toBe(false);
  });

  it("requires both the video-reference flag and a video slot", () => {
    const options = generatorOptionsFromPayload({
      timelineAdapters: [
        { id: "flag-without-slot", supportsVideoReferences: true, maximumReferenceVideos: 0 },
      ],
    });
    expect(supportsVideoMotionReferences(options[0])).toBe(false);
  });

  it("allows Generate Scene when any batch engine is executable", () => {
    const rows = joinProductionControlVideoOptions(
      { models: [{ id: "ltx-2.5-distilled", executable: false }, { id: "minimax-h3", executable: true }] },
      {
        generators: [
          { id: "ltx-2.5-distilled", label: "LTX 2.5", executable: false, readiness: "Requires Setup" },
          { id: "minimax-h3", label: "MiniMax H3", executable: true, readiness: "Ready" },
        ],
      },
    );
    expect(anyTimelineGeneratorExecutable(rows, "ltx-2.5-distilled")).toBe(false);
    expect(anyTimelineGeneratorExecutable(rows, "ltx-2.5-distilled", "minimax-h3")).toBe(true);
  });

  it("reads qualityControl and native audio from the adapter/runtime join, not display names", () => {
    const rows = joinProductionControlVideoOptions(null, {
      generators: [
        {
          id: "minimax-h3",
          label: "MiniMax H3 Local",
          executable: true,
          readiness: "Ready",
          supportsAudio: true,
          qualityControl: "h3_megapixels",
        },
        {
          id: "ltx-2.5-distilled",
          label: "LTX 2.5 Local",
          executable: true,
          readiness: "Ready",
          supportsAudio: true,
          qualityControl: "ltx_quality",
        },
        {
          id: "seedance-2.0",
          label: "Seedance 2.0",
          executable: true,
          readiness: "Ready",
          supportsAudio: false,
        },
      ],
      timelineAdapters: [
        { id: "minimax-h3", audio_generation: true, qualityControl: "h3_megapixels" },
        { id: "ltx-2.5-distilled", audio_generation: true, qualityControl: "ltx_quality" },
        { id: "seedance-2.0", audio_generation: false },
      ],
    });
    const h3 = rows.find((row) => row.id === "minimax-h3");
    const ltx = rows.find((row) => row.id === "ltx-2.5-distilled");
    const seedance = rows.find((row) => row.id === "seedance-2.0");
    expect(generatorQualityControl(h3)).toBe("h3_megapixels");
    expect(generatorQualityControl(ltx)).toBe("ltx_quality");
    expect(generatorQualityControl(seedance)).toBe("");
    expect(h3?.audio_generation).toBe(true);
    expect(resolveNativeAudioState(h3, "ready").status).toBe("supported");
    expect(resolveNativeAudioState(h3, "ready").label).toBe("SUPPORTED");
    expect(resolveNativeAudioState(ltx, "ready").status).toBe("supported");
    expect(resolveNativeAudioState(seedance, "ready").status).toBe("not_supported");
    const seedanceReady = joinProductionControlVideoOptions(null, {
      generators: [
        { id: "seedance-2.0", label: "Seedance 2.0", executable: true, readiness: "Ready" },
      ],
      timelineAdapters: [
        {
          id: "seedance-2.0",
          audio_generation: true,
          qualityControl: "seedance_resolution",
          supportedResolutions: ["480p", "720p", "1080p", "4k"],
        },
      ],
    }).find((row) => row.id === "seedance-2.0");
    expect(generatorQualityControl(seedanceReady)).toBe("seedance_resolution");
    expect(seedanceReady?.supportedResolutions).toEqual(["480p", "720p", "1080p", "4k"]);
    expect(resolveNativeAudioState(seedanceReady, "ready").status).toBe("supported");
    expect(resolveNativeAudioState(seedanceReady, "ready").detail).toContain("produces synchronized native audio");
    expect(resolveNativeAudioState(seedance, "ready").detail).toContain("does not provide native audio");
    expect(resolveNativeAudioState(h3, "loading").status).toBe("checking");
    expect(
      resolveNativeAudioState({ ...h3!, executable: false, readiness: "offline" }, "ready").status,
    ).toBe("offline");
    expect(resolveNativeAudioState(null, "error").status).toBe("unavailable");
  });
});
