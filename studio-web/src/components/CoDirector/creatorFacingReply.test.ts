import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import {
  approvalResultMessageId,
  coDirectorMessageIdentity,
  mergeServerMessages,
  projectCreatorReply,
  upsertCoDirectorMessage,
} from "./creatorFacingReply";
import { CoDirectorMessage } from "./CoDirectorMessage";

vi.mock("./CoDirectorSession", () => ({
  useCoDirectorSession: () => ({ uiContext: { projectId: "project-1" } }),
}));

const RECEIPT = JSON.stringify({
  requested_action: "read:character.search",
  tool_id: "character.search",
  execution_status: "succeeded",
  projectId: "06b04b34-f3de-46fa-9d90-64c8932bab4b",
  workflowId: "msg-1",
  evidence: {
    read: {
      result: {
        data: {
          matches: [{ displayName: "Cade", characterId: "93145921-28cb-46d1-86fc-28c213192a42", sourceName: null }],
        },
      },
    },
  },
});

describe("creator facing replies", () => {
  it("keeps a tool receipt out of the normal sentence", () => {
    const projected = projectCreatorReply(RECEIPT);
    expect(projected.text).toContain("Cade");
    expect(projected.text).not.toContain("requested_action");
    expect(projected.text).not.toContain("characterId");
    expect(projected.text).not.toContain("93145921");
    expect(projected.text).not.toContain("{");
    expect(projected.technical).toContain("requested_action");
  });

  it("leaves an ordinary sentence alone", () => {
    const projected = projectCreatorReply("I found Cade and I'm preparing the Timeline scene.");
    expect(projected.text).toBe("I found Cade and I'm preparing the Timeline scene.");
    expect(projected.technical).toBeNull();
  });

  it("keeps technical details collapsed and out of the sentence", () => {
    const html = renderToStaticMarkup(
      createElement(CoDirectorMessage, {
        message: {
          id: "asst-1",
          role: "assistant",
          content: RECEIPT,
          createdAt: "2026-09-25T00:00:00.000Z",
        },
      }),
    );
    expect(html).toContain("I found Cade");
    expect(html).toContain("Technical details");
    expect(html).not.toContain("<details open");
    const bubble = html.split("Technical details")[0];
    expect(bubble).not.toContain("requested_action");
    expect(bubble).not.toContain("93145921");
  });

  it("renders the same receipt once", () => {
    const local = [{ id: "msg-1:assistant", role: "assistant", content: RECEIPT, requestId: "msg-1" }];
    const incoming = [{ id: "msg-1:assistant", role: "assistant", content: RECEIPT, clientRequestId: "msg-1:assistant" }];
    const merged = mergeServerMessages(local, incoming);
    expect(merged).toHaveLength(1);
  });
});

describe("Co-Director event identity dedupe", () => {
  it("uses approval result id, not text, as the stable key", () => {
    const approvalId = "approve:wf-1:proposal-9";
    expect(approvalResultMessageId(approvalId, "failed")).toBe(`${approvalId}:failed`);
    expect(coDirectorMessageIdentity({ id: `${approvalId}:failed`, role: "assistant", content: "a" })).toBe(
      `id:${approvalId}:failed`,
    );
    expect(
      coDirectorMessageIdentity({
        role: "assistant",
        content: "Couldn't approve that proposal: The change could not be verified against project state.",
        approvalId,
        messageType: "error",
      }),
    ).toBe(`approval:${approvalId}:failed`);
  });

  it("keeps the same approval failure once across local insert + reconnect", () => {
    const approvalId = "approve:wf-1:proposal-9";
    const id = approvalResultMessageId(approvalId, "failed");
    const text = "Couldn't approve that proposal: The change could not be verified against project state.";
    const local = [
      {
        id,
        role: "assistant",
        content: text,
        approvalId,
        messageType: "error",
      },
    ];
    const incoming = [
      {
        id,
        role: "assistant",
        content: text,
        clientRequestId: `${approvalId}:failed`,
      },
      {
        id: "random-local-dup",
        role: "assistant",
        content: text,
        approvalId,
        messageType: "error",
      },
    ];
    const merged = mergeServerMessages(local, incoming);
    expect(merged).toHaveLength(1);
    expect(merged[0].id).toBe(id);
  });

  it("dedupes by request+type without relying on identical text", () => {
    const first = {
      id: "",
      role: "assistant",
      content: "Working on it…",
      requestId: "req-22",
      messageType: "execution_status",
    };
    const second = {
      id: "",
      role: "assistant",
      content: "Still working…",
      requestId: "req-22",
      messageType: "execution_status",
    };
    const merged = upsertCoDirectorMessage([first], second);
    expect(merged).toHaveLength(1);
    expect(merged[0].content).toBe("Still working…");
  });

  it("dedupes workflow+seq identities", () => {
    const a = { id: "", role: "assistant", content: "one", workflowId: "wf-7", workflowSeq: 3 };
    const b = { id: "", role: "assistant", content: "two", workflowId: "wf-7", seq: 3 };
    expect(mergeServerMessages([a], [b])).toHaveLength(1);
  });
});
