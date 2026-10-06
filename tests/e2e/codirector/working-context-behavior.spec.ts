/**
 * Sanitation Phase 1 — Working Context / confidence / confirmation (non-pixel).
 * Hits Studio API. Does not spawn a new Schnick project.
 */
import { expect, test } from "@playwright/test";

const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";

async function createProject(request: any, name: string): Promise<string> {
  const res = await request.post(`${API}/api/projects`, {
    data: { name, global_prompt: "Phase 1 sanitation behavior." },
  });
  expect(res.ok()).toBeTruthy();
  return (await res.json()).id;
}

test.describe("Working Context behavior", () => {
  test("HIGH camera-only does not ask", async ({ request }) => {
    const projectId = await createProject(request, `WC-HIGH-${Date.now()}`);
    await request.patch(`${API}/api/codirector/projects/${projectId}/working-context`, {
      data: {
        activeSceneId: "schnick",
        scene: { sceneId: "schnick", name: "Schnick Coffee", approved: true },
      },
    });
    const res = await request.post(
      `${API}/api/codirector/projects/${projectId}/working-context/compile-confidence`,
      {
        data: {
          instruction: "Give me a full close-up on Korri. High angle, 20 degrees.",
          characterId: "korri",
          candidateSceneIds: ["schnick"],
          candidateCharacterIds: ["korri"],
        },
      },
    );
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.confidence.level).toBe("HIGH");
    expect(body.confidence.asked).toBeFalsy();
  });

  test("MEDIUM asks once then Yes executes without re-ask", async ({ request }) => {
    const projectId = await createProject(request, `WC-MED-${Date.now()}`);
    const first = await request.post(
      `${API}/api/codirector/projects/${projectId}/working-context/compile-confidence`,
      {
        data: {
          instruction: "Give me a close-up of Korri.",
          candidateSceneIds: ["schnick", "meadow"],
          candidateCharacterIds: ["korri"],
        },
      },
    );
    expect(first.ok()).toBeTruthy();
    const medium = await first.json();
    expect(medium.confidence.level).toBe("MEDIUM");
    expect(medium.confidence.question).toBeTruthy();

    const yes = await request.post(
      `${API}/api/codirector/projects/${projectId}/working-context/compile-confidence`,
      { data: { instruction: "Yes." } },
    );
    expect(yes.ok()).toBeTruthy();
    const bound = await yes.json();
    expect(bound.confidence.level).toBe("HIGH");
    expect(bound.confidence.asked).toBeFalsy();
    expect(bound.context.confirmations.at(-1).resolved).toBeTruthy();
    expect(bound.context.confirmations.at(-1).originalInstruction).toContain("close-up");
  });

  test("LOW does not pretend generation is ready", async ({ request }) => {
    const projectId = await createProject(request, `WC-LOW-${Date.now()}`);
    const res = await request.post(
      `${API}/api/codirector/projects/${projectId}/working-context/compile-confidence`,
      { data: { instruction: "Make a shot." } },
    );
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.confidence.level).toBe("LOW");
    expect(body.confidence.asked).toBeTruthy();
  });

  test("approval survives GET after write", async ({ request }) => {
    const projectId = await createProject(request, `WC-APP-${Date.now()}`);
    await request.post(`${API}/api/codirector/projects/${projectId}/working-context/approvals`, {
      data: { what: "image", characterId: "korri" },
    });
    const got = await request.get(`${API}/api/codirector/projects/${projectId}/working-context`);
    expect(got.ok()).toBeTruthy();
    const body = await got.json();
    expect(body.scene.approved).toBeTruthy();
    expect(body.approvals.at(-1).what).toBe("image");
  });

  test("working context is project isolated", async ({ request }) => {
    const a = await createProject(request, `WC-ISO-A-${Date.now()}`);
    const b = await createProject(request, `WC-ISO-B-${Date.now()}`);
    await request.patch(`${API}/api/codirector/projects/${a}/working-context`, {
      data: { activeSceneId: "only-a" },
    });
    const other = await (await request.get(`${API}/api/codirector/projects/${b}/working-context`)).json();
    expect(other.activeSceneId).not.toBe("only-a");
    const missing = await request.get(`${API}/api/codirector/projects/not-a-real-project/working-context`);
    expect(missing.status()).toBe(404);
  });

  test("confirmation memory survives GET reload", async ({ request }) => {
    const projectId = await createProject(request, `WC-RELOAD-${Date.now()}`);
    const first = await request.post(
      `${API}/api/codirector/projects/${projectId}/working-context/compile-confidence`,
      {
        data: {
          instruction: "Give me a close-up of Korri.",
          candidateSceneIds: ["schnick", "meadow"],
          candidateCharacterIds: ["korri"],
        },
      },
    );
    expect(first.ok()).toBeTruthy();
    expect((await first.json()).confidence.level).toBe("MEDIUM");
    const yes = await request.post(
      `${API}/api/codirector/projects/${projectId}/working-context/compile-confidence`,
      { data: { instruction: "Yes." } },
    );
    expect(yes.ok()).toBeTruthy();
    const reload = await request.get(`${API}/api/codirector/projects/${projectId}/working-context`);
    expect(reload.ok()).toBeTruthy();
    const once = await reload.json();
    expect(once.confirmations.at(-1).resolved).toBeTruthy();
    expect(once.confirmations.at(-1).originalInstruction).toContain("close-up");
    const again = await (await request.get(`${API}/api/codirector/projects/${projectId}/working-context`)).json();
    expect(again.confirmations.at(-1).resolved).toBeTruthy();
    expect(again.confirmations.at(-1).originalInstruction).toBe(once.confirmations.at(-1).originalInstruction);
    expect(again.confidence.asked).toBeFalsy();
  });
});
