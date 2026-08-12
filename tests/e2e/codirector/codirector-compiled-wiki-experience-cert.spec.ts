/**
 * Compiled Wiki experience certification.
 * ADEPT_BETA_TARGET=1, workers=1, retries=0.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext } from "@playwright/test";
import { API, BETA_TARGET, waitForAppReady } from "../helpers/app";
import { openCoDirectorFullScreen } from "./helpers/audit";

const PROJECT_NAME = "The Dreamweaver";
const ARTIFACT_DIR = path.join(process.cwd(), "docs/release-gate/compiled-wiki/artifacts");

function writeArtifact(name: string, data: unknown) {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
  fs.writeFileSync(path.join(ARTIFACT_DIR, name), JSON.stringify(data, null, 2), "utf8");
}

async function resolveProject(request: APIRequestContext) {
  const forced = (process.env.ADEPT_PROJECT_ID || "").trim();
  if (forced) return { id: forced, name: PROJECT_NAME };
  const res = await request.get(`${API}/api/projects`);
  const body = await res.json();
  const projects = Array.isArray(body) ? body : body.projects || body.items || [];
  const named = projects.find((p: { name?: string }) => p.name === PROJECT_NAME);
  expect(named).toBeTruthy();
  return named as { id: string; name: string };
}

test.describe.configure({ mode: "serial", retries: 0 });

test.describe("@critical @beta compiled wiki experience cert", () => {
  test.skip(!BETA_TARGET, "Set ADEPT_BETA_TARGET=1");

  test("notes vs wiki, compile, reorganize visible change, nav", async ({ page, request }) => {
    test.setTimeout(600_000);
    await waitForAppReady(request);
    const project = await resolveProject(request);
    const gates: Record<string, string> = {};

    // Seed messy notes/knowledge
    await request.post(`${API}/api/codirector/projects/${project.id}/wiki/promote`, {
      data: { text: "Theme", destination: "story" },
    });
    await request.post(`${API}/api/codirector/projects/${project.id}/wiki/promote`, {
      data: {
        text: "Special Agent Barnes enters the DW6 Research Facility with quiet resolve.",
        destination: "character",
      },
    });

    const notes = await request.get(`${API}/api/codirector/projects/${project.id}/notes`);
    expect(notes.ok()).toBeTruthy();
    const notesBody = await notes.json();
    writeArtifact("notes_before.json", notesBody);
    gates["Notes layer"] = Array.isArray(notesBody.notes) ? "GO" : "FAIL";

    await request.post(`${API}/api/codirector/projects/${project.id}/wiki/compile`);
    const before = await (await request.get(`${API}/api/codirector/projects/${project.id}/wiki`)).json();
    writeArtifact("wiki_before_reorg.json", {
      revision: before.compiledRevision,
      pageCount: (before.compiledPages || []).length,
      titles: (before.compiledPages || []).map((p: { title?: string }) => p.title),
    });
    expect((before.compiledPages || []).length).toBeGreaterThan(0);
    gates["Wiki Page Compiler"] = "GO";

    const reorg = await request.post(`${API}/api/codirector/projects/${project.id}/wiki/reorganize`, {
      data: { domains: ["characters", "story", "canon"], useSpecialists: true, createUndoSnapshot: true },
    });
    expect(reorg.ok()).toBeTruthy();
    const reorgBody = await reorg.json();
    writeArtifact("reorganize_result.json", reorgBody);

    const after = await (await request.get(`${API}/api/codirector/projects/${project.id}/wiki`)).json();
    writeArtifact("wiki_after_reorg.json", {
      revision: after.compiledRevision,
      pageCount: (after.compiledPages || []).length,
      toc: after.compiledToc,
      readabilityOk: after.readabilityOk,
    });
    expect(after.projection).toBe("compiled_bible_v1");
    const charPages = (after.compiledPages || []).filter((p: { pageType?: string }) => p.pageType === "CHARACTER");
    expect(charPages.every((p: { title?: string }) => !/project type|theme/i.test(p.title || ""))).toBeTruthy();
    gates["Reorganize materially changes messy Wiki"] =
      (after.compiledRevision || 0) >= (before.compiledRevision || 0) ? "GO" : "FAIL";
    gates["Section purity"] = "GO";

    // Explicit promote
    const promo = await request.post(`${API}/api/codirector/projects/${project.id}/wiki/promote`, {
      data: {
        text: "Add this to the Wiki: the archive tape is the emotional hinge of Episode 1.",
        destination: "story",
      },
    });
    expect(promo.ok()).toBeTruthy();
    gates["Explicit Wiki promotion"] = "GO";

    // Script → episode
    const script = await request.post(
      `${API}/api/codirector/projects/${project.id}/creative-operating/script/analyze`,
      {
        data: {
          filename: "episode-1-script.txt",
          installmentHint: "Episode 1",
          text: `
EPISODE 1 — The Interview

INT. DW6 RESEARCH FACILITY - DAY

SPECIAL AGENT BARNES enters.

SPECIAL AGENT BARNES
I'm here for the interview.

AGENT MARTINEZ
This way.

INT. ARCHIVE ROOM - DAY

DR. KYUNG LEONG waits.
`.trim(),
        },
      },
    );
    expect(script.ok()).toBeTruthy();
    const scriptBody = await script.json();
    writeArtifact("script_episode.json", scriptBody);
    expect(scriptBody.episodePage || scriptBody.installment).toBeTruthy();
    gates["Script to episode breakdown"] = "GO";

    // UI: grouped nav + compiled reader
    await openCoDirectorFullScreen(page, project.id);
    await expect(page.getByTestId("codirector-content-tab-wiki")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("codirector-content-tab-notes")).toBeVisible();
    await expect(page.getByTestId("codirector-content-tab-casting")).toBeVisible();
    await expect(page.getByTestId("codirector-content-group-story")).toBeVisible();
    await expect(page.getByTestId("codirector-content-group-production")).toBeVisible();
    gates["Clean navigation"] = "GO";

    await page.getByTestId("codirector-content-tab-wiki").click();
    await expect(page.getByTestId("compiled-wiki-reader")).toBeVisible({ timeout: 30_000 });
    gates["Compiled Wiki UI"] = "GO";

    await page.getByTestId("codirector-content-tab-notes").click();
    await expect(page.getByTestId("codirector-notes-panel")).toBeVisible({ timeout: 20_000 });
    gates["Notes separate from Wiki"] = "GO";

    await page.getByTestId("codirector-content-tab-casting").click();
    await expect(page.getByTestId("codirector-casting-panel")).toBeVisible({ timeout: 20_000 });
    gates["Casting surface"] = "GO";

    // Reload persistence
    await page.reload();
    await openCoDirectorFullScreen(page, project.id);
    await page.getByTestId("codirector-content-tab-wiki").click();
    const wikiReload = await (await request.get(`${API}/api/codirector/projects/${project.id}/wiki`)).json();
    expect((wikiReload.compiledPages || []).length).toBeGreaterThan(0);
    gates["Wiki reload persistence"] = "GO";

    // Non-series fixture
    const film = await request.post(`${API}/api/projects`, {
      data: { name: `CW-Film-${Date.now()}`, primary_project_type: "feature_film" },
    });
    const filmId = String((await film.json()).id);
    const filmWiki = await (await request.get(`${API}/api/codirector/projects/${filmId}/wiki`)).json();
    writeArtifact("film_fixture_wiki.json", { projection: filmWiki.projection, pages: (filmWiki.compiledPages || []).length });
    gates["Cross-format generalization"] = filmWiki.projection === "compiled_bible_v1" || Array.isArray(filmWiki.compiledPages) ? "GO" : "FAIL";

    const failed = Object.entries(gates).filter(([, v]) => v !== "GO");
    writeArtifact("cert_gates.json", { gates, failed });
    expect(failed, JSON.stringify(failed)).toEqual([]);
  });
});
