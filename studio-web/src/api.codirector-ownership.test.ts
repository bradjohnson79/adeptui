import { describe, expect, it } from "vitest";

import { api } from "./api.ts";

type FetchCall = { url: string; init: RequestInit | undefined };

function installFetchCapture() {
  const calls: FetchCall[] = [];
  const fetchMock = (_url: string | URL | Request, init?: RequestInit) => {
    calls.push({ url: String(_url), init });
    return Promise.resolve(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
  };
  Object.defineProperty(globalThis, "fetch", {
    configurable: true,
    value: fetchMock,
  });
  return calls;
}

function bodyOf(call: FetchCall | undefined): Record<string, unknown> {
  expect(call).toBeDefined();
  return JSON.parse(String(call?.init?.body)) as Record<string, unknown>;
}

describe("Co-Director ownership projectId wiring", () => {
  it("m29 image approve sends projectId in the request body when provided", async () => {
    const calls = installFetchCapture();
    const projectId = "11111111-2222-3333-4444-555555555555";

    await api.m29ImageApprove("ver-1", "user", projectId, "scene-7");

    const target = calls.find((c) =>
      c.url.includes("/api/codirector/m29/image/ver-1/approve"),
    );
    const body = bodyOf(target);
    expect(body.projectId).toBe(projectId);
    expect(body.sceneId).toBe("scene-7");
    expect(body.actor).toBe("user");
  });

  it("m29 image approve omits projectId when the caller has no active project", async () => {
    const calls = installFetchCapture();

    await api.m29ImageApprove("ver-2");

    const target = calls.find((c) =>
      c.url.includes("/api/codirector/m29/image/ver-2/approve"),
    );
    const body = bodyOf(target);
    expect("projectId" in body).toBe(false);
  });

  it("m29 timeline apply threads projectId into the body for ownership enforcement", async () => {
    const calls = installFetchCapture();
    const projectId = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";

    await api.m29TimelineApply("prop-1", "user", projectId);

    const target = calls.find((c) =>
      c.url.includes("/api/codirector/m29/timeline/prop-1/apply"),
    );
    expect(bodyOf(target).projectId).toBe(projectId);
  });

  it("m29 render get sends projectId as a query parameter", async () => {
    const calls = installFetchCapture();
    const projectId = "11111111-2222-3333-4444-555555555555";

    await api.m29RenderGet("man-1", projectId);

    const target = calls.find((c) =>
      c.url.includes("/api/codirector/m29/render/man-1"),
    );
    expect(target).toBeDefined();
    expect(target!.url).toMatch(/projectId=11111111-2222-3333-4444-555555555555/);
  });

  it("m214 storyteller approve sends projectId in the body when provided", async () => {
    const calls = installFetchCapture();
    const projectId = "22222222-3333-4444-5555-666666666666";

    await api.m214StorytellerApprove("handoff-1", projectId);

    const target = calls.find((c) =>
      c.url.includes("/api/codirector/m214/storyteller/handoff/handoff-1/approve"),
    );
    expect(bodyOf(target).projectId).toBe(projectId);
  });

  it("m214 attachment confirm threads projectId into the confirm body", async () => {
    const calls = installFetchCapture();
    const projectId = "33333333-4444-5555-6666-777777777777";

    await api.m214AttachmentConfirm("interp-1", {
      decision: "accept",
      projectId,
      note: "looks good",
    });

    const target = calls.find((c) =>
      c.url.includes("/api/codirector/m214/attachments/interp-1/confirm"),
    );
    const body = bodyOf(target);
    expect(body.projectId).toBe(projectId);
    expect(body.decision).toBe("accept");
    expect(body.note).toBe("looks good");
  });
});
