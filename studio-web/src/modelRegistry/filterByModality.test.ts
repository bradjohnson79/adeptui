import { describe, expect, it } from "vitest";
import { modelsForModality, sectionsFromProductionControlModels } from "./filterByModality";
import type { ModelDescriptor } from "./contracts";

function desc(partial: Partial<ModelDescriptor> & Pick<ModelDescriptor, "id" | "modality">): ModelDescriptor {
  return {
    label: partial.id,
    locality: "local",
    capabilityLabel: "Available",
    supports: [],
    doesNotSupport: [],
    gpuCompatible: true,
    executable: true,
    ...partial,
  };
}

describe("modelsForModality", () => {
  it("keeps only matching capability modality, never by name", () => {
    const mixed = [
      desc({ id: "ollama-gemma4-31b", modality: "llm", label: "Gemma 4 31B" }),
      desc({ id: "qwen-image-2512-local", modality: "image", label: "Qwen Image" }),
      desc({ id: "minimax-h3", modality: "video", label: "MiniMax H3" }),
      desc({ id: "tiny-gguf", modality: "llm", label: "tiny-gguf" }),
    ];
    const video = modelsForModality(mixed, "video");
    expect(video.map((m) => m.id)).toEqual(["minimax-h3"]);
    expect(video.every((m) => m.modality === "video")).toBe(true);

    const image = modelsForModality(mixed, "image");
    expect(image.map((m) => m.id)).toEqual(["qwen-image-2512-local"]);
  });

  it("returns honest empty when none match", () => {
    const llmOnly = [desc({ id: "gemma", modality: "llm" })];
    expect(modelsForModality(llmOnly, "video")).toEqual([]);
    expect(modelsForModality(undefined, "audio")).toEqual([]);
  });
});

describe("sectionsFromProductionControlModels", () => {
  it("does not leak llm local rows into video even if cache returns llm payload", () => {
    const llmPayload = {
      models: [
        desc({ id: "ollama-gemma4-31b", modality: "llm", locality: "local" as const }),
        desc({ id: "qwen3.8:27b", modality: "llm", locality: "local" as const, label: "qwen3.8:27b" }),
      ],
      sections: {
        local: [
          desc({ id: "ollama-gemma4-31b", modality: "llm", locality: "local" as const }),
          desc({ id: "tiny-gguf", modality: "llm", locality: "local" as const, label: "tiny-gguf" }),
        ],
        api: [],
      },
    };
    const sections = sectionsFromProductionControlModels(llmPayload, "video");
    expect(sections.local).toEqual([]);
    expect(sections.api).toEqual([]);
  });

  it("keeps MiniMax H3 on a truthful video list and splits local vs api", () => {
    const payload = {
      sections: {
        local: [
          desc({ id: "minimax-h3", modality: "video", locality: "local" as const, label: "MiniMax H3" }),
          desc({ id: "ltx-local", modality: "video", locality: "local" as const, label: "LTX 2.3" }),
          desc({ id: "ollama-gemma4-12b", modality: "llm", locality: "local" as const }),
        ],
        api: [
          desc({ id: "seedance-kie", modality: "video", locality: "hosted" as const, label: "Seedance" }),
          desc({ id: "gemini-3-pro-kie", modality: "llm", locality: "hosted" as const }),
        ],
      },
    };
    const sections = sectionsFromProductionControlModels(payload, "video");
    expect(sections.local.map((m) => m.id)).toEqual(["minimax-h3", "ltx-local"]);
    expect(sections.api.map((m) => m.id)).toEqual(["seedance-kie"]);
    expect(sections.local.find((m) => m.id === "minimax-h3")).toBeTruthy();
  });

  it("isolates image and audio from llm", () => {
    const payload = {
      sections: {
        local: [
          desc({ id: "gemma", modality: "llm" }),
          desc({ id: "flux-local", modality: "image" }),
          desc({ id: "index-tts", modality: "audio" }),
        ],
        api: [],
      },
    };
    expect(sectionsFromProductionControlModels(payload, "image").local.map((m) => m.id)).toEqual(["flux-local"]);
    expect(sectionsFromProductionControlModels(payload, "audio").local.map((m) => m.id)).toEqual(["index-tts"]);
    expect(sectionsFromProductionControlModels(payload, "llm").local.map((m) => m.id)).toEqual(["gemma"]);
  });
});
