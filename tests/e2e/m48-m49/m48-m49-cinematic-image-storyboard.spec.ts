/**
 * M4.8–M4.9 Cinematic Image + Storyboard Studio — certification journeys.
 */
import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const WEB = process.env.ADEPT_WEB_URL || "http://127.0.0.1:5173";
const API = process.env.ADEPT_API_URL || "http://127.0.0.1:8758";
const PROJECT =
  process.env.M48_PROJECT_ID || "e32dae30-a014-4ea4-a2f2-69f4b7809bde";
const ARTIFACTS = path.resolve("artifacts/m48-m49");

function ensureDir(dir: string) {
  fs.mkdirSync(dir, { recursive: true });
}

test.describe("M48/M49 Technical Certification", () => {
  test("imagegen mounts Cinematic Image Generator with Continuity + Approve affordances", async ({
    page,
  }) => {
    ensureDir(path.join(ARTIFACTS, "technical"));
    await page.goto(`${WEB}/project/${PROJECT}?workspace=imagegen`);
    await expect(page.getByRole("heading", { name: /Cinematic Image Generator/i })).toBeVisible({
      timeout: 60_000,
    });
    await expect(page.locator(".cis-continuity-label")).toHaveText("Continuity");
    await expect(page.getByRole("button", { name: /Inherit from scene/i })).toBeVisible();
    await expect(page.locator(".cis-actions .primary")).toHaveText(/Generate/i);
    await page.screenshot({
      path: path.join(ARTIFACTS, "technical", "imagegen-mount.png"),
      fullPage: true,
    });
  });

  test("storyboard mounts Storyboard Studio with Export PDF + Prepare", async ({ page }) => {
    await page.goto(`${WEB}/project/${PROJECT}?workspace=script`);
    await expect(page.getByRole("heading", { name: /Storyboard Studio/i })).toBeVisible({
      timeout: 60_000,
    });
    await expect(page.getByRole("button", { name: /^9$/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Prepare for Timeline/i })).toBeVisible();
    await expect(page.getByRole("link", { name: /Export PDF/i })).toBeVisible();
    await page.screenshot({
      path: path.join(ARTIFACTS, "technical", "storyboard-mount.png"),
      fullPage: true,
    });
  });

  test("API families/providers/continuity/reopen/export.pdf", async ({ request }) => {
    ensureDir(path.join(ARTIFACTS, "technical"));
    const fam = await request.get(`${API}/api/image-product/families`);
    expect(fam.ok()).toBeTruthy();
    const famBody = await fam.json();
    const ids = (famBody.families || []).map((f: { family: string }) => f.family);
    expect(ids).toContain("qwen2512");

    const providers = await request.get(`${API}/api/image-studio/providers`);
    expect(providers.ok()).toBeTruthy();
    fs.writeFileSync(
      path.join(ARTIFACTS, "technical", "providers.json"),
      JSON.stringify(await providers.json(), null, 2)
    );

    ensureDir(path.join(ARTIFACTS, "continuity"));
    const inherit = await request.post(
      `${API}/api/image-studio/projects/${PROJECT}/continuity-sessions/inherit-from-scene`,
      { data: { sceneId: "Scene 12" } }
    );
    expect(inherit.ok()).toBeTruthy();
    const session = (await inherit.json()).session;
    expect(session.id).toBeTruthy();
    fs.writeFileSync(
      path.join(ARTIFACTS, "continuity", "session-scene-12.json"),
      JSON.stringify(session, null, 2)
    );

    const ws = await request.get(`${API}/api/storyboard-studio/projects/${PROJECT}/workspace`);
    expect(ws.ok()).toBeTruthy();

    const pdf = await request.get(`${API}/api/storyboard-studio/projects/${PROJECT}/export.pdf`);
    expect(pdf.ok()).toBeTruthy();
    const pdfBuf = await pdf.body();
    expect(pdfBuf.slice(0, 4).toString()).toBe("%PDF");
    ensureDir(path.join(ARTIFACTS, "storyboard"));
    fs.writeFileSync(path.join(ARTIFACTS, "storyboard", "export.pdf"), pdfBuf);
  });
});

test.describe("M48/M49 Continuity + Storyboard API journeys", () => {
  test("continuity inherit → approve → add → replace → undo → prepare → confirm", async ({
    request,
  }) => {
    ensureDir(path.join(ARTIFACTS, "continuity"));
    ensureDir(path.join(ARTIFACTS, "creative"));
    ensureDir(path.join(ARTIFACTS, "storyboard"));

    const inherit = await request.post(
      `${API}/api/image-studio/projects/${PROJECT}/continuity-sessions/inherit-from-scene`,
      { data: { sceneId: "Scene 12" } }
    );
    expect(inherit.ok()).toBeTruthy();
    const session = (await inherit.json()).session;

    // Use an existing project image asset when present
    const projectRes = await request.get(`${API}/api/projects/${PROJECT}`);
    expect(projectRes.ok()).toBeTruthy();
    const project = await projectRes.json();
    const images = (project.assets || []).filter((a: { kind: string }) => a.kind === "image");
    test.skip(!images.length, "No image assets available for API workflow without live gen");
    const assetId = images[0].id as string;

    const approve = await request.post(
      `${API}/api/image-studio/projects/${PROJECT}/continuity-sessions/${session.id}/approve-image`,
      { data: { assetId } }
    );
    expect(approve.ok()).toBeTruthy();
    const approved = (await approve.json()).session;
    expect(approved.approvedImageIds).toContain(assetId);

    // Frame 2 / 3 inherit same scene → same session id
    const inherit2 = await request.post(
      `${API}/api/image-studio/projects/${PROJECT}/continuity-sessions/inherit-from-scene`,
      { data: { sceneId: "Scene 12" } }
    );
    const session2 = (await inherit2.json()).session;
    expect(session2.id).toBe(session.id);

    const reopen = await request.get(
      `${API}/api/image-studio/projects/${PROJECT}/assets/${assetId}/reopen`
    );
    expect(reopen.ok()).toBeTruthy();
    fs.writeFileSync(
      path.join(ARTIFACTS, "creative", "reopen-provenance.json"),
      JSON.stringify(await reopen.json(), null, 2)
    );

    const add = await request.post(`${API}/api/storyboard-studio/projects/${PROJECT}/add-image`, {
      data: {
        assetId,
        prompt: "M48 cert narrative film frame",
        label: "Cert Frame",
        sceneId: "Scene 12",
        continuitySessionId: session.id,
        scriptwriterSceneId: "Scene 12",
      },
    });
    expect(add.ok()).toBeTruthy();
    const added = await add.json();
    expect(added.panelId).toBeTruthy();

    const assetB = (images[1] || images[0]).id as string;
    const replace = await request.post(
      `${API}/api/storyboard-studio/projects/${PROJECT}/replace-panel`,
      {
        data: {
          panelId: added.panelId,
          assetId: assetB,
          prompt: "Replaced panel 5 cert",
          continuitySessionId: session.id,
          sceneId: "Scene 12",
        },
      }
    );
    expect(replace.ok()).toBeTruthy();

    const undo = await request.post(
      `${API}/api/storyboard-studio/projects/${PROJECT}/undo-replace-panel`,
      { data: { panelId: added.panelId } }
    );
    expect(undo.ok()).toBeTruthy();

    const prep = await request.post(
      `${API}/api/storyboard-studio/projects/${PROJECT}/prepare-timeline`,
      { data: { panelIds: [added.panelId], approvedOnly: false } }
    );
    expect(prep.ok()).toBeTruthy();
    const proposal = (await prep.json()).proposal;
    fs.writeFileSync(
      path.join(ARTIFACTS, "storyboard", "timeline-proposal.json"),
      JSON.stringify(proposal, null, 2)
    );

    const confirm = await request.post(
      `${API}/api/storyboard-studio/projects/${PROJECT}/timeline-proposals/${proposal.id}/confirm`,
      { data: { panelIds: [added.panelId] } }
    );
    expect(confirm.ok()).toBeTruthy();
    const confirmed = await confirm.json();
    expect(confirmed.timelinePayload?.length).toBeGreaterThan(0);
    fs.writeFileSync(
      path.join(ARTIFACTS, "storyboard", "timeline-confirm.json"),
      JSON.stringify(confirmed, null, 2)
    );

    ensureDir(path.join(ARTIFACTS, "providers"));
    const mode = await request.post(`${API}/api/image-studio/providers/for-mode`, {
      data: { mode: "all_models", prompt: "cinematic street at dusk", purpose: "storyboard" },
    });
    expect(mode.ok()).toBeTruthy();
    fs.writeFileSync(
      path.join(ARTIFACTS, "providers", "all-models.json"),
      JSON.stringify(await mode.json(), null, 2)
    );
  });
});

test.describe("M48/M49 Artist discoverability (automated proxy)", () => {
  test("primary actions visible without coaching", async ({ page }) => {
    ensureDir(path.join(ARTIFACTS, "ux"));
    await page.goto(`${WEB}/project/${PROJECT}?workspace=imagegen`);
    await expect(page.locator(".cis-actions .primary")).toBeVisible({ timeout: 60_000 });
    await page.goto(`${WEB}/project/${PROJECT}?workspace=script`);
    await expect(page.getByRole("button", { name: /Prepare for Timeline/i })).toBeVisible({
      timeout: 60_000,
    });
    await page.goto(`${WEB}/project/${PROJECT}?workspace=imagegen`);
    await expect(page.getByRole("button", { name: /Open Storyboard/i })).toBeVisible();
    await page.screenshot({ path: path.join(ARTIFACTS, "ux", "artist-discoverability.png") });
  });
});
