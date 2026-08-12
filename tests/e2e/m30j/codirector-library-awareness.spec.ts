/**
 * M3.0j — Co-Director Project Library Awareness (skeleton)
 * Label: DETERMINISTIC_BROWSER_REGRESSION where API-only; REAL_LOCAL for generation chains.
 */
import { test, expect } from "@playwright/test";
import { API, createTempProject, waitForAppReady } from "../helpers/app";

test.describe("M3.0j Co-Director library awareness @DETERMINISTIC", () => {
  test.beforeAll(async ({ request }) => {
    await waitForAppReady(request);
  });

  test("LIBRARY-CD-01 folder map via codirector-context", async ({ request }) => {
    const project = await createTempProject(request, "CD Library Map");
    const res = await request.get(`${API}/api/projects/${project.id}/library/codirector-context`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.folderMap).toBeTruthy();
    expect(body.librarySchemaVersion).toBeGreaterThan(0);
  });

  test("LIBRARY-CD-06 resolve Audio/Music path", async ({ request }) => {
    const project = await createTempProject(request, "CD Resolve Music");
    const res = await request.post(`${API}/api/projects/${project.id}/library/resolve`, {
      data: { path: "Audio/Music" },
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.resolved).toBe(true);
    expect(body.match.systemKey).toBe("audio.music");
  });

  test("LIBRARY-CD-12 ambiguous Audio query returns candidates", async ({ request }) => {
    const project = await createTempProject(request, "CD Ambiguity");
    const res = await request.post(`${API}/api/projects/${project.id}/library/resolve`, {
      data: { query: "Audio" },
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.ambiguous).toBe(true);
    expect((body.candidates || []).length).toBeGreaterThan(1);
  });

  test("LIBRARY-CD-16 lazy entity folder via preflight", async ({ request }) => {
    const project = await createTempProject(request, "CD Entity Folder");
    const res = await request.post(`${API}/api/projects/${project.id}/library/preflight`, {
      data: {
        task: "generate_prop_reference",
        entityType: "prop",
        entityName: "Crystal Codex",
        entityId: "prop-codex-e2e",
        systemKey: "props.references",
      },
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.ready).toBe(true);
    expect(String(body.targetPath)).toContain("Crystal Codex");
  });

  test.skip("LIBRARY-CD-20 post-generation storage report — REAL_LOCAL", async () => {
    // Requires real generation chain; enable when M3.0j cert harness is wired.
  });
});
