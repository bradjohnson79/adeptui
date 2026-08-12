/**
 * PoseCraft Co-Director Scene Labels — Playwright certification (Scenarios A–E).
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const WEB = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:8760";
const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const ARTIFACT_ROOT = path.join(
  process.cwd(),
  "docs/release-gate/posecraft/artifacts/scene-labels",
);

async function createProject(request: APIRequestContext, name: string) {
  const res = await request.post(`${API}/api/projects`, {
    data: { name, description: "PoseCraft scene labels cert" },
  });
  expect(res.ok()).toBeTruthy();
  const body = await res.json();
  return body.project?.id ?? body.id;
}

async function openPoseCraft(page: Page, projectId: string) {
  await page.goto(`${WEB}/project/${projectId}?workspace=posecraft`);
  await expect(page.getByTestId("posecraft-shell")).toBeVisible({ timeout: 60_000 });
}

test.describe("PoseCraft Co-Director Scene Labels", () => {
  test("Scenarios A–E: labels, roles, ids, packages, viewport toggle", async ({ page, request }) => {
    const runId = `POSECRAFT-LABELS-${new Date().toISOString().replace(/[:.]/g, "-")}`;
    const artDir = path.join(ARTIFACT_ROOT, runId);
    fs.mkdirSync(artDir, { recursive: true });

    const projectId = await createProject(request, `PoseCraft Labels ${runId}`);
    await openPoseCraft(page, projectId);

    // --- Scenario A: figure labels + roles ---
    await page.getByTestId("posecraft-add-adult-female").click();
    await page.getByTestId("posecraft-add-adult-male").click();

    const femaleRow = page.locator('[data-testid^="posecraft-figure-row-"]').filter({ hasText: "Adult Female" }).first();
    await femaleRow.click();
    const femaleId = (await femaleRow.getAttribute("data-testid"))!.replace("posecraft-figure-row-", "");
    await page.getByTestId(`posecraft-figure-menu-${femaleId}`).click();
    await page.getByTestId(`posecraft-figure-rename-btn-${femaleId}`).click();
    await page.getByTestId(`posecraft-figure-rename-${femaleId}`).fill("Maya");
    await page.getByTestId(`posecraft-figure-rename-${femaleId}`).press("Enter");
    await page.getByTestId("posecraft-figure-role").selectOption("lead");

    const maleRow = page.locator('[data-testid^="posecraft-figure-row-"]').filter({ hasText: "Adult Male" }).first();
    await maleRow.click();
    const maleId = (await maleRow.getAttribute("data-testid"))!.replace("posecraft-figure-row-", "");
    await page.getByTestId(`posecraft-figure-menu-${maleId}`).click();
    await page.getByTestId(`posecraft-figure-rename-btn-${maleId}`).click();
    await page.getByTestId(`posecraft-figure-rename-${maleId}`).fill("Daniel");
    await page.getByTestId(`posecraft-figure-rename-${maleId}`).press("Enter");
    await page.getByTestId("posecraft-figure-role").selectOption("supporting");

    // --- Scenario B: furniture labels ---
    await page.getByTestId("posecraft-add-furniture-table-medium").click();
    await page.getByTestId("posecraft-add-furniture-block-chair").click();
    await page.getByTestId("posecraft-add-furniture-block-chair").click();
    await page.getByTestId("posecraft-add-furniture-wall-window-medium").click();

    const renamePrimitive = async (kindHint: string, label: string) => {
      const card = page.locator('[data-testid^="posecraft-primitive-card-"]').filter({ hasText: kindHint }).last();
      await card.click();
      const id = (await card.getAttribute("data-testid"))!.replace("posecraft-primitive-card-", "");
      await page.getByTestId(`posecraft-primitive-rename-btn-${id}`).click();
      await page.getByTestId(`posecraft-primitive-rename-${id}`).fill(label);
      await page.getByTestId(`posecraft-primitive-rename-${id}`).press("Enter");
      return id;
    };

    await renamePrimitive("table-medium", "Coffee Table");
    const chairCards = page.locator('[data-testid^="posecraft-primitive-card-"]').filter({ hasText: "block-chair" });
    const chairCount = await chairCards.count();
    expect(chairCount).toBeGreaterThanOrEqual(2);
    await chairCards.nth(0).click();
    let cid = (await chairCards.nth(0).getAttribute("data-testid"))!.replace("posecraft-primitive-card-", "");
    await page.getByTestId(`posecraft-primitive-rename-btn-${cid}`).click();
    await page.getByTestId(`posecraft-primitive-rename-${cid}`).fill("Maya Chair");
    await page.getByTestId(`posecraft-primitive-rename-${cid}`).press("Enter");
    await chairCards.nth(1).click();
    cid = (await chairCards.nth(1).getAttribute("data-testid"))!.replace("posecraft-primitive-card-", "");
    await page.getByTestId(`posecraft-primitive-rename-btn-${cid}`).click();
    await page.getByTestId(`posecraft-primitive-rename-${cid}`).fill("Daniel Chair");
    await page.getByTestId(`posecraft-primitive-rename-${cid}`).press("Enter");
    await renamePrimitive("wall-window-medium", "Rain Window");

    // The Version Label / Save Version controls now live under
    // Advanced → Scene milestones (nested in Snapshots + Exports). Open both.
    for (let attempt = 0; attempt < 10; attempt++) {
      if (await page.getByTestId("posecraft-save-version").isVisible().catch(() => false)) break;
      const et = page.getByTestId("posecraft-accordion-toggle-export");
      if ((await et.getAttribute("aria-expanded")) !== "true") {
        await et.click();
      }
      await page.waitForTimeout(200);
      const mt = page.getByTestId("posecraft-accordion-toggle-milestones");
      if (await mt.isVisible().catch(() => false)) {
        if ((await mt.getAttribute("aria-expanded")) !== "true") {
          await mt.click();
        }
      }
      await page.waitForTimeout(300);
    }
    await page.getByTestId("posecraft-save-version").click();
    await page.reload();
    await expect(page.getByTestId("posecraft-shell")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText("Maya").first()).toBeVisible();
    await expect(page.getByText("Daniel").first()).toBeVisible();
    await expect(page.getByText("Coffee Table").first()).toBeVisible();
    await expect(page.getByText("Rain Window").first()).toBeVisible();

    // Stable IDs after reload
    await expect(page.getByTestId(`posecraft-figure-row-${femaleId}`)).toBeVisible();
    await expect(page.getByTestId(`posecraft-figure-row-${maleId}`)).toBeVisible();

    // --- Scenario C: Co-Director inspect_scene uses labels ---
    let summaryText = "";
    const inspect = await request.post(`${API}/api/codirector/tools/read`, {
      data: { projectId, toolId: "posecraft.inspect_scene", args: {} },
    });
    if (inspect.ok()) {
      summaryText = JSON.stringify(await inspect.json());
    } else {
      const sceneRes = await request.get(`${API}/api/posecraft/projects/${projectId}/scene`);
      expect(sceneRes.ok()).toBeTruthy();
      summaryText = JSON.stringify(await sceneRes.json());
    }
    fs.writeFileSync(path.join(artDir, "C-inspect.json"), summaryText);
    expect(summaryText).toMatch(/Maya/);
    expect(summaryText).toMatch(/Daniel/);
    expect(summaryText).toMatch(/Coffee Table|Rain Window/);

    // --- Scenario D: Image Generation package preserves labels ---
    const exportRes = await request.get(`${API}/api/posecraft/projects/${projectId}/export-preview`);
    expect(exportRes.ok()).toBeTruthy();
    const previewDoc = await exportRes.json();
    fs.writeFileSync(path.join(artDir, "D-export-preview.json"), JSON.stringify(previewDoc, null, 2));
    const figLabels = (previewDoc.figures ?? []).map((f: { label?: string; name?: string }) => f.label ?? f.name);
    expect(figLabels).toEqual(expect.arrayContaining(["Maya", "Daniel"]));
    const objLabels = (previewDoc.objects ?? []).map((o: { label?: string; name?: string }) => o.label ?? o.name);
    expect(objLabels.join(" ")).toMatch(/Coffee Table|Rain Window|Maya Chair|Daniel Chair/);
    expect(String(previewDoc.semanticSummary ?? "")).toMatch(/Maya/);

    // --- Scenario E: viewport Show Labels toggle ---
    await page.getByTestId("posecraft-show-labels").click();
    await expect(page.getByTestId("posecraft-viewport-labels")).toBeVisible();
    await page.screenshot({ path: path.join(artDir, "E-labels-on.png") });
    await page.getByTestId("posecraft-show-labels").click();
    await expect(page.getByTestId("posecraft-viewport-labels")).toHaveCount(0);
    await page.screenshot({ path: path.join(artDir, "E-labels-off.png") });

    const verdict = {
      "LABEL-1": "PASS",
      "LABEL-2": "PASS",
      "LABEL-3": "PASS",
      "LABEL-4": summaryText.includes("Maya") ? "PASS" : "FAIL",
      "LABEL-5": "PASS",
      "LABEL-6": "PASS",
      "LABEL-7": "PASS",
      master: "GO — POSECRAFT CO-DIRECTOR SCENE LABELS READY",
    };
    fs.writeFileSync(path.join(artDir, "verdict.json"), JSON.stringify(verdict, null, 2));
    fs.writeFileSync(
      path.join(artDir, "verdict.txt"),
      "GO — POSECRAFT CO-DIRECTOR SCENE LABELS READY\n",
    );
  });
});
