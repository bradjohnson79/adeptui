import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { CoDirectorProposal } from "../../api";
import { approvalSummary, handleApprovalChoice } from "./approvalSummary";
import { CoDirectorProposalCard } from "./CoDirectorProposalCard";

function proposal(toolId: string, args: Record<string, unknown>): CoDirectorProposal {
  return {
    id: "proposal-plain",
    projectId: "project-internal-9f3a",
    proposalType: "tool_call",
    title: toolId,
    summary: "raw",
    payload: { entityMutations: [], factMutations: [], summary: "", changeReason: "" },
    status: "pending",
    createdBy: "codirector",
    createdAt: "2026-09-25T00:00:00Z",
    updatedAt: "2026-09-25T00:00:00Z",
    isStale: false,
    toolCall: {
      toolId,
      toolSchemaVersion: 1,
      arguments: args,
      capabilitySnapshot: {},
      preview: { summary: toolId, lines: [`characterId ${args.characterId || "hidden-line"}`], warnings: [] },
      inputHash: "hash-internal-aa11",
      baseResourceVersions: {},
    },
  };
}

const cases: Array<{ toolId: string; args: Record<string, unknown>; wants: string; hidden: string[] }> = [
  {
    toolId: "character_creator.create_from_brief",
    args: { name: "Harbor", brief: "Keeps a lantern.", characterId: "char-internal-111" },
    wants: "Create a new character named Harbor.",
    hidden: ["character_creator.create_from_brief", "char-internal-111", "project-internal-9f3a"],
  },
  {
    toolId: "character_creator.propose_visual_sheet",
    args: { characterId: "char-internal-222", characterName: "Harbor", profileSummary: "Grey coat." },
    wants:
      "There isn’t an existing character image, so I’ll create the front reference first and use that as the character’s visual identity.",
    hidden: ["character_creator.propose_visual_sheet", "char-internal-222", "project-internal-9f3a"],
  },
  {
    toolId: "timeline.propose_add_prompt_segment",
    args: { sceneDurationSec: 6, aspectRatio: "16:9", text: "[0s-6s] A quiet dock.", sceneId: "scene-internal-333" },
    wants: "Add a 6-second timed prompt to Timeline.",
    hidden: ["timeline.propose_add_prompt_segment", "scene-internal-333", "project-internal-9f3a"],
  },
  {
    toolId: "propose_image_generate",
    args: { aspectRatio: "16:9", prompt: "A lantern on a dock.", referenceAssetId: "asset-internal-444" },
    wants: "Generate a 16:9 still image.",
    hidden: ["propose_image_generate", "asset-internal-444", "project-internal-9f3a"],
  },
  {
    toolId: "prop_creator.generate_view",
    args: { name: "coffee mug", propId: "prop-internal-555" },
    wants: "Generate a prop image of coffee mug.",
    hidden: ["prop_creator.generate_view", "prop-internal-555", "project-internal-9f3a"],
  },
  {
    toolId: "character_creator.generate_voice_candidates",
    args: {
      characterName: "Lar",
      testLine: "We should leave before sunrise.",
      performance: "Calm but serious",
      characterId: "char-internal-lar",
    },
    wants: "Create a voice performance for Lar.",
    hidden: ["character_creator.generate_voice_candidates", "char-internal-lar", "project-internal-9f3a"],
  },
  {
    toolId: "audio.generate_ambience",
    args: {
      prompt: "Quiet coffee-shop chatter, cups, and subtle room tone.",
      sceneId: "scene-internal-333",
    },
    wants: "Create background ambience for this scene.",
    hidden: ["audio.generate_ambience", "scene-internal-333", "project-internal-9f3a"],
  },
];

describe("approval card summaries", () => {
  it("shows a plain Timeline scene with the named character, prop, and place", () => {
    const args = {
      prompt: "Cade is sitting cross-legged at a table inside Schnick Coffee Shop, looking out the window.",
      characterName: "Cade",
      propName: "Silver thermos",
      environmentName: "Schnick Coffee Shop",
      aspectRatio: "16:9",
      characterId: "char-internal-cade",
      projectId: "project-internal-9f3a",
      sceneId: "scene-internal-333",
    };
    const summary = approvalSummary("create_scene", args);
    expect(summary.wants).toBe("Create a new scene in Timeline.");
    const html = renderToStaticMarkup(
      createElement(CoDirectorProposalCard, {
        proposal: proposal("create_scene", args),
        busy: false,
        onApprove: () => undefined,
        onReject: () => undefined,
        onRevise: () => undefined,
        onCancel: () => undefined,
      }),
    );
    for (const visible of [
      "Timeline",
      "Cade",
      "Silver thermos",
      "Schnick Coffee Shop",
      "looking out the window",
      "16:9",
      "Nothing will be created until you approve.",
    ]) {
      expect(html).toContain(visible);
    }
    const visible = html.replace(/data-testid="[^"]*"/g, "");
    for (const hidden of [
      "create_scene",
      "char-internal-cade",
      "project-internal-9f3a",
      "scene-internal-333",
      "proposal-plain",
      "workflow",
      "{",
    ]) {
      expect(visible).not.toContain(hidden);
    }
    expect(html).not.toContain("codirector-proposal-details");
  });

  it.each(cases)("$toolId stays in plain language", ({ toolId, args, wants, hidden }) => {
    expect(approvalSummary(toolId, args).wants).toBe(wants);
    const html = renderToStaticMarkup(
      createElement(CoDirectorProposalCard, {
        proposal: proposal(toolId, args),
        busy: false,
        onApprove: () => undefined,
        onReject: () => undefined,
        onRevise: () => undefined,
        onCancel: () => undefined,
      }),
    );
    expect(html).toContain(wants);
    expect(html).toContain("Prepared and waiting for approval.");
    expect(html).toContain(">Approve<");
    expect(html).toContain(">Revise<");
    expect(html).toContain(">Reject<");
    for (const secret of hidden) {
      expect(html).not.toContain(secret);
    }
  });

  it("revise and reject do not call approve", () => {
    const onApprove = vi.fn();
    const onRevise = vi.fn();
    const onReject = vi.fn();
    handleApprovalChoice("revise", { onApprove, onRevise, onReject });
    handleApprovalChoice("reject", { onApprove, onRevise, onReject });
    expect(onApprove).not.toHaveBeenCalled();
    expect(onRevise).toHaveBeenCalledOnce();
    expect(onReject).toHaveBeenCalledOnce();
  });
});
