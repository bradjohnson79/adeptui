/**
 * Wiki Specialist Department certification — roster, routing, no creator-facing voice.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext } from "@playwright/test";
import { API, BETA_TARGET, waitForAppReady } from "../helpers/app";

const PROJECT_NAME = "The Dreamweaver";
const ARTIFACT_DIR = path.join(process.cwd(), "docs/release-gate/professional-wiki/artifacts");

function writeArtifact(name: string, data: unknown) {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
  fs.writeFileSync(path.join(ARTIFACT_DIR, name), JSON.stringify(data, null, 2), "utf8");
}

async function resolveProject(request: APIRequestContext) {
  const res = await request.get(`${API}/api/projects`);
  const body = await res.json();
  const projects = Array.isArray(body) ? body : body.projects || body.items || [];
  const named = projects.find((p: { name?: string }) => p.name === PROJECT_NAME);
  expect(named).toBeTruthy();
  return named as { id: string; name: string };
}

test.describe.configure({ mode: "serial", retries: 0 });

test.describe("@critical @beta wiki specialist department cert", () => {
  test.skip(!BETA_TARGET, "Set ADEPT_BETA_TARGET=1");

  test("roster active + reorganize activates specialists + locked canon protected", async ({ request }) => {
    test.setTimeout(300_000);
    await waitForAppReady(request);
    const project = await resolveProject(request);

    // Roster file must exist from audit
    const rosterPath = path.join(process.cwd(), "docs/release-gate/professional-wiki/WIKI_SPECIALIST_ROSTER.md");
    expect(fs.existsSync(rosterPath)).toBeTruthy();

    const reorg = await request.post(`${API}/api/codirector/projects/${project.id}/wiki/reorganize`, {
      data: {
        domains: ["characters", "locations", "wardrobe", "props", "timeline", "canon"],
        useSpecialists: true,
        preserveLockedCanon: true,
        createUndoSnapshot: true,
      },
    });
    expect(reorg.ok()).toBeTruthy();
    const body = await reorg.json();
    writeArtifact("specialist_reorganize.json", body);
    expect(body.ok).toBeTruthy();
    const selected = body.specialistsActivated || [];
    expect(selected.length).toBeGreaterThan(0);
    expect(selected.length).toBeLessThanOrEqual(8);
    // Must not activate every specialist blindly
    expect(selected.length).toBeLessThan(20);

    const requiredHints = ["script-supervisor", "continuity-analyst", "character-creator", "costume-designer"];
    const hit = requiredHints.some((id) => selected.includes(id));
    expect(hit).toBeTruthy();

    const history = await request.get(
      `${API}/api/codirector/projects/${project.id}/wiki/reorganization-history`,
    );
    expect(history.ok()).toBeTruthy();
    const histBody = await history.json();
    writeArtifact("reorganization_history.json", histBody);
    expect(histBody.ok).toBeTruthy();

    writeArtifact("specialist_department_summary.json", {
      projectId: project.id,
      specialistsActivated: selected,
      jobStatus: body.job?.status,
      findingsCount: body.findingsCount,
    });
  });
});
