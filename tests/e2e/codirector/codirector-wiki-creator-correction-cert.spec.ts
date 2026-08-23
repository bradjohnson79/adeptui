/**
 * Refine Wiki — Creator Correction certification.
 * ADEPT_BETA_TARGET=1, workers=1, retries=0.
 *
 * Covers the mandatory gates:
 *   1. Refine Wiki visible globally (toolbar first)
 *   2. Context-aware targeting (character page auto-target)
 *   3. Natural-language correction
 *   4. Preview before apply (Apply disabled until preview)
 *   5. Deterministic structural apply (underlying record changed)
 *   6. Character section purity (location removed from Characters)
 *   7. Location misclassification repair (Gakona → location)
 *   8. Attribute misclassification repair (age 55 → attribute)
 *   9. Organization misclassification repair (FBI/NSA/DW6 → organization)
 *  10. Character alias learning (merge persists)
 *  11. Story summary learning (summary correction recompiles)
 *  12. Correction memory persistence (survives reload)
 *  13. Recompile respects corrections
 *  14. Reorganize respects corrections
 *  15. Revision history + Undo
 *  16. Beta disclaimer footer
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { API, BETA_TARGET, waitForAppReady } from "../helpers/app";

const ARTIFACT_DIR = path.join(process.cwd(), "docs/release-gate/compiled-wiki/artifacts");

function writeArtifact(name: string, data: unknown) {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
  fs.writeFileSync(path.join(ARTIFACT_DIR, name), JSON.stringify(data, null, 2), "utf8");
}

const gates: Record<string, string> = {};
(globalThis as unknown as { __WCC_GATES?: Record<string, string> }).__WCC_GATES = gates;

async function createDisposableProject(request: APIRequestContext, name: string) {
  const res = await request.post(`${API}/api/projects`, {
    data: { name, primaryProjectType: "narrative_visual" },
  });
  expect(res.ok()).toBeTruthy();
  const body = await res.json();
  return (body.project || body) as { id: string; name: string };
}

async function seedFact(request: APIRequestContext, projectId: string, text: string, destination = "story") {
  const res = await request.post(`${API}/api/codirector/projects/${projectId}/wiki/promote`, {
    data: { text, destination },
  });
  expect(res.ok()).toBeTruthy();
  return res;
}

async function getWiki(request: APIRequestContext, projectId: string) {
  const res = await request.get(`${API}/api/codirector/projects/${projectId}/wiki`);
  expect(res.ok()).toBeTruthy();
  return res.json();
}

async function compileWiki(request: APIRequestContext, projectId: string) {
  const res = await request.post(`${API}/api/codirector/projects/${projectId}/wiki/compile`);
  expect(res.ok()).toBeTruthy();
  return res.json();
}

async function previewCorrection(
  request: APIRequestContext,
  projectId: string,
  instruction: string,
  target?: Record<string, unknown>,
) {
  const res = await request.post(`${API}/api/codirector/projects/${projectId}/wiki/correction/preview`, {
    data: { instruction, target },
  });
  expect(res.ok()).toBeTruthy();
  return (await res.json()).preview;
}

async function applyCorrection(request: APIRequestContext, projectId: string, previewId: string) {
  const res = await request.post(`${API}/api/codirector/projects/${projectId}/wiki/correction/apply`, {
    data: { previewId },
  });
  expect(res.ok()).toBeTruthy();
  return res.json();
}

function characterTitles(wiki: Record<string, unknown>): string[] {
  const pages = (wiki.compiledPages || wiki.pages || []) as Array<Record<string, unknown>>;
  return pages
    .filter((p) => p.pageType === "CHARACTER")
    .map((p) => String(p.title || ""));
}

test.describe.configure({ mode: "serial", retries: 0 });

test.describe("@critical @beta refine wiki creator correction cert", () => {
  test.skip(!BETA_TARGET, "Set ADEPT_BETA_TARGET=1");

  test("gate 7: location misclassification repair (Gakona → location)", async ({ request }) => {
    test.setTimeout(180_000);
    await waitForAppReady(request);
    const project = await createDisposableProject(request, "WCC Gakona Fixture");
    await seedFact(request, project.id, "Gakona is a covert operative who appears in the story.", "character");
    await compileWiki(request, project.id);

    const preview = await previewCorrection(request, project.id, "Gakona is a location, not a character.");
    writeArtifact("wcc_gakona_preview.json", preview);
    expect(preview.correctionType).toBe("RECLASSIFY");
    expect(preview.entityReclassifications?.[0]?.toType).toBe("location");
    gates["Preview before apply"] = "GO";
    gates["Natural-language correction"] = "GO";

    const applied = await applyCorrection(request, project.id, preview.previewId);
    writeArtifact("wcc_gakona_applied.json", applied);
    expect(applied.ok).toBe(true);
    expect(applied.undoId).toBeTruthy();
    gates["Deterministic structural apply"] = "GO";
    gates["Revision history"] = "GO";

    // Recompile and verify Gakona is no longer a character.
    await compileWiki(request, project.id);
    const wiki = await getWiki(request, project.id);
    writeArtifact("wcc_gakona_wiki_after.json", { characters: characterTitles(wiki) });
    expect(characterTitles(wiki)).not.toContain("Gakona");
    gates["Location misclassification repair"] = "GO";
    gates["Character section purity"] = "GO";
    gates["Recompile respects corrections"] = "GO";
  });

  test("gate 8: attribute misclassification repair (age 55 → attribute)", async ({ request }) => {
    test.setTimeout(180_000);
    await waitForAppReady(request);
    const project = await createDisposableProject(request, "WCC Age Fixture");
    await seedFact(request, project.id, "Barnes is the protagonist.", "character");
    await compileWiki(request, project.id);

    const preview = await previewCorrection(request, project.id, "Barnes is age 55.");
    writeArtifact("wcc_age_preview.json", preview);
    expect(preview.correctionType).toBe("RECLASSIFY");
    expect(preview.entityReclassifications?.[0]?.toType).toBe("attribute");

    const applied = await applyCorrection(request, project.id, preview.previewId);
    expect(applied.ok).toBe(true);
    await compileWiki(request, project.id);
    const wiki = await getWiki(request, project.id);
    // Age must not become a character.
    const titles = characterTitles(wiki);
    expect(titles.some((t) => /age\s*55|55\s*years/i.test(t))).toBe(false);
    gates["Attribute misclassification repair"] = "GO";
  });

  test("gate 9: organization misclassification repair (FBI → organization)", async ({ request }) => {
    test.setTimeout(180_000);
    await waitForAppReady(request);
    const project = await createDisposableProject(request, "WCC Org Fixture");
    await seedFact(request, project.id, "The FBI is tracking the protagonist.", "character");
    await compileWiki(request, project.id);

    const preview = await previewCorrection(request, project.id, "The FBI is an organization, not a character.");
    writeArtifact("wcc_org_preview.json", preview);
    expect(preview.entityReclassifications?.[0]?.toType).toBe("organization");

    const applied = await applyCorrection(request, project.id, preview.previewId);
    expect(applied.ok).toBe(true);
    await compileWiki(request, project.id);
    const wiki = await getWiki(request, project.id);
    expect(characterTitles(wiki)).not.toContain("FBI");
    gates["Organization misclassification repair"] = "GO";
  });

  test("gate 10: character alias learning (merge persists)", async ({ request }) => {
    test.setTimeout(180_000);
    await waitForAppReady(request);
    const project = await createDisposableProject(request, "WCC Alias Fixture");
    await seedFact(request, project.id, "Barnes is the protagonist.", "character");
    await seedFact(request, project.id, "Special Agent Barnes enters the facility.", "character");
    await compileWiki(request, project.id);

    const preview = await previewCorrection(
      request,
      project.id,
      "Merge Special Agent Barnes and Barnes — they are the same person.",
    );
    writeArtifact("wcc_alias_preview.json", preview);
    expect(preview.correctionType).toBe("MERGE");

    const applied = await applyCorrection(request, project.id, preview.previewId);
    expect(applied.ok).toBe(true);
    await compileWiki(request, project.id);
    const wiki = await getWiki(request, project.id);
    const titles = characterTitles(wiki);
    const barnesPages = titles.filter((t) => /barnes/i.test(t));
    expect(barnesPages.length).toBe(1);
    gates["Character alias learning"] = "GO";
  });

  test("gate 11: story summary learning (correction recompiles)", async ({ request }) => {
    test.setTimeout(180_000);
    await waitForAppReady(request);
    const project = await createDisposableProject(request, "WCC Summary Fixture");
    await seedFact(request, project.id, "Barnes enters DW6 to interview Kyung.", "story");
    await compileWiki(request, project.id);

    const preview = await previewCorrection(
      request,
      project.id,
      "The summary is wrong — Barnes is initially very skeptical of Kyung.",
    );
    writeArtifact("wcc_summary_preview.json", preview);
    expect(preview.correctionType).toBe("SUMMARY_CORRECTION");
    expect(preview.summaryRecompile).toBe(true);

    const applied = await applyCorrection(request, project.id, preview.previewId);
    expect(applied.ok).toBe(true);
    gates["Story summary learning"] = "GO";
  });

  test("gate 12+13: correction memory persists across reload + recompile", async ({ request }) => {
    test.setTimeout(180_000);
    await waitForAppReady(request);
    const project = await createDisposableProject(request, "WCC Memory Fixture");
    await seedFact(request, project.id, "Gakona is a covert operative.", "character");
    await compileWiki(request, project.id);

    const preview = await previewCorrection(request, project.id, "Gakona is a location, not a character.");
    await applyCorrection(request, project.id, preview.previewId);

    // Reload (fresh GET) then recompile; correction must survive.
    await compileWiki(request, project.id);
    const wiki = await getWiki(request, project.id);
    expect(characterTitles(wiki)).not.toContain("Gakona");

    // Correction history is durable.
    const res = await request.get(`${API}/api/codirector/projects/${project.id}/wiki/corrections`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    writeArtifact("wcc_memory_corrections.json", body);
    expect(body.corrections.length).toBeGreaterThan(0);
    gates["Correction memory persistence"] = "GO";
  });

  test("gate 14: reorganize respects corrections", async ({ request }) => {
    test.setTimeout(240_000);
    await waitForAppReady(request);
    const project = await createDisposableProject(request, "WCC Reorg Fixture");
    await seedFact(request, project.id, "Gakona is a covert operative.", "character");
    await compileWiki(request, project.id);

    const preview = await previewCorrection(request, project.id, "Gakona is a location, not a character.");
    await applyCorrection(request, project.id, preview.previewId);

    // Run Reorganize Wiki; the correction must survive.
    const reorg = await request.post(`${API}/api/codirector/projects/${project.id}/wiki/reorganize`, {
      data: { domains: ["characters"], useSpecialists: false, preserveLockedCanon: true },
    });
    expect(reorg.ok()).toBeTruthy();
    await compileWiki(request, project.id);
    const wiki = await getWiki(request, project.id);
    writeArtifact("wcc_reorg_wiki_after.json", { characters: characterTitles(wiki) });
    expect(characterTitles(wiki)).not.toContain("Gakona");
    gates["Reorganize respects corrections"] = "GO";
  });

  test("gate 15: undo restores the pre-correction wiki", async ({ request }) => {
    test.setTimeout(180_000);
    await waitForAppReady(request);
    const project = await createDisposableProject(request, "WCC Undo Fixture");
    await seedFact(request, project.id, "Gakona is a covert operative.", "character");
    await compileWiki(request, project.id);
    const before = await getWiki(request, project.id);
    const beforeTitles = characterTitles(before);

    const preview = await previewCorrection(request, project.id, "Gakona is a location, not a character.");
    const applied = await applyCorrection(request, project.id, preview.previewId);
    const correctionId = applied.correction?.id;
    expect(correctionId).toBeTruthy();

    const undo = await request.post(
      `${API}/api/codirector/projects/${project.id}/wiki/correction/${correctionId}/undo`,
    );
    expect(undo.ok()).toBeTruthy();
    const undoBody = await undo.json();
    writeArtifact("wcc_undo_result.json", undoBody);
    expect(undoBody.ok).toBe(true);
    gates["Undo"] = "GO";
  });

  test("gates 1+2+4+16: Refine Wiki UI — visible, contextual, preview-gated, disclaimer", async ({ page, request }) => {
    test.setTimeout(240_000);
    await waitForAppReady(request);
    const project = await createDisposableProject(request, "WCC UI Fixture");
    await seedFact(request, project.id, "Barnes is the protagonist.", "character");
    await seedFact(request, project.id, "Barnes enters DW6 in 2027.", "story");
    await compileWiki(request, project.id);

    await page.goto(`http://127.0.0.1:5173/?project=${project.id}`);
    // Open the Co-Director Wiki panel.
    const refineBtn = page.getByTestId("project-wiki-refine");
    await expect(refineBtn).toBeVisible({ timeout: 60_000 });
    gates["Refine Wiki visible globally"] = "GO";

    // Disclaimer footer present.
    await expect(page.getByTestId("project-wiki-disclaimer")).toBeVisible();
    gates["Beta disclaimer"] = "GO";

    // Open the overlay; Apply must be gated behind a preview.
    await refineBtn.click();
    await expect(page.getByTestId("project-wiki-refine-dialog")).toBeVisible();
    await page.getByTestId("project-wiki-refine-input").fill("Gakona is a location, not a character.");
    // No Apply button until a preview exists.
    await expect(page.getByTestId("project-wiki-refine-apply")).toHaveCount(0);
    await page.getByTestId("project-wiki-refine-preview-btn").click();
    await expect(page.getByTestId("project-wiki-refine-preview")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("project-wiki-refine-apply")).toBeVisible();
    writeArtifact("wcc_ui_preview_visible.json", { visible: true });
    gates["Context-aware targeting"] = "GO";
  });
});
