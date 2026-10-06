import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { CoDirectorMessage } from "./CoDirectorMessage";
import { upsertCoDirectorMessage } from "./creatorFacingReply";

vi.mock("./CoDirectorSession", () => ({
  useCoDirectorSession: () => ({ uiContext: { projectId: "project-1" } }),
}));

vi.mock("../library/LibraryQuickPreviewModal", () => ({
  LibraryQuickPreviewModal: () => null,
}));

describe("generation ready notice UI", () => {
  it("renders a small View image action without approval-card chrome", () => {
    const html = renderToStaticMarkup(
      createElement(CoDirectorMessage, {
        message: {
          id: "genrdy:exec-1",
          role: "assistant",
          content: "Your image is ready.",
          createdAt: "2026-09-26T00:00:00.000Z",
          messageType: "answer",
          generationReady: {
            messageId: "genrdy:exec-1",
            executionId: "exec-1",
            outcome: "ready",
            modality: "image",
            actionLabel: "View image",
            assetId: "asset-abc",
            previewKind: "image",
          },
        },
      }),
    );
    expect(html).toContain("Your image is ready.");
    expect(html).toContain("View image");
    expect(html).toContain("codirector-gen-ready");
    expect(html).not.toContain("codirector-approval");
    expect(html).not.toContain("asset-abc");
  });

  it("dedupes by stable genrdy identity across reconnect", () => {
    const a = {
      id: "genrdy:exec-9",
      role: "assistant",
      content: "Your video is ready.",
      generationReady: { messageId: "genrdy:exec-9", executionId: "exec-9" },
    };
    const b = {
      id: "genrdy:exec-9",
      role: "assistant",
      content: "Your video is ready.",
      generationReady: { messageId: "genrdy:exec-9", executionId: "exec-9" },
    };
    const merged = upsertCoDirectorMessage([a], b);
    expect(merged).toHaveLength(1);
  });

  it("shows Details for fail notices without raw provider text in the bubble", () => {
    const html = renderToStaticMarkup(
      createElement(CoDirectorMessage, {
        message: {
          id: "genrdy:exec-fail",
          role: "assistant",
          content: "The music cue couldn't be completed.",
          createdAt: "2026-09-26T00:00:00.000Z",
          generationReady: {
            messageId: "genrdy:exec-fail",
            executionId: "exec-fail",
            outcome: "failed",
            modality: "music",
            actionLabel: "Details",
            technical: "ProviderTimeout: fal 504",
          },
        },
      }),
    );
    expect(html).toContain("couldn't be completed");
    expect(html).toContain("Details");
    const bubble = html.split("codirector-gen-ready")[0];
    expect(bubble).not.toContain("ProviderTimeout");
    expect(bubble).not.toContain("fal 504");
  });
});
