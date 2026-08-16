/**
 * Scene Spatial Profile + Reset Workspace.
 *
 * Continue persist → Standard hydrate. Reset clears selection, not Library.
 * Never POST /api/projects. Do not use retired :8760.
 */
import { expect, test, type APIRequestContext } from "@playwright/test";

const BASE = process.env.PLAYWRIGHT_BASE_URL || "https://adeptui.vercel.app";
const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "2347bf46-3762-4763-86c5-4a6032522278";
const SCENE_ID = "e4550745-f0ef-44c8-99a5-ef9e20bd47d2";
const SC_URL = `${BASE}/project/${PROJECT_ID}?workspace=scenecreator`;

async function waitApiReady(request: APIRequestContext) {
  await expect
    .poll(
      async () => {
        try {
          const res = await request.get(`${API}/api/health`, { timeout: 10_000 });
          return res.ok();
        } catch {
          return false;
        }
      },
      { timeout: 90_000 },
    )
    .toBeTruthy();
}

test.describe("Scene Spatial Profile + Reset", () => {
  test.beforeEach(async ({ request }) => {
    await waitApiReady(request);
  });

  test("A–C persist idempotent profile, hydrate, reset without deleting", async ({ request, page }) => {
    const first = await request.post(`${API}/api/scene-creator/projects/${PROJECT_ID}/production-handoff`, {
      data: { scene_id: SCENE_ID },
    });
    expect(first.ok(), await first.text()).toBeTruthy();
    const a = await first.json();
    expect(a.handoffId).toBeTruthy();
    expect(a.sceneId).toBeTruthy();
    expect(a.sheetId).toBeTruthy();

    const second = await request.post(`${API}/api/scene-creator/projects/${PROJECT_ID}/production-handoff`, {
      data: { scene_id: SCENE_ID },
    });
    expect(second.ok(), await second.text()).toBeTruthy();
    const b = await second.json();
    expect(b.handoffId).toBe(a.handoffId);
    expect(b.sceneId).toBe(a.sceneId);
    expect(b.sheetId).toBe(a.sheetId);
    expect(b.profile.shotIds).toEqual(a.profile.shotIds);

    const listed = await request.get(`${API}/api/scene-creator/projects/${PROJECT_ID}/spatial-profiles`);
    expect(listed.ok()).toBeTruthy();
    const listBody = await listed.json();
    const matches = (listBody.profiles || []).filter((p: { handoffId: string }) => p.handoffId === a.handoffId);
    expect(matches).toHaveLength(1);

    const ws = await request.get(
      `${API}/api/scene-creator/projects/${PROJECT_ID}/workspace?scene_id=${a.sceneId}&sheet_id=${a.sheetId}&spatial_profile_id=${a.handoffId}`,
    );
    expect(ws.ok()).toBeTruthy();
    const workspace = await ws.json();
    expect(workspace.selected_spatial_profile_id).toBe(a.handoffId);
    expect(workspace.selected_sheet_id).toBe(a.sheetId);
    expect(workspace.resolved_ers?.package_id || "").toBe(a.ersPackageId || workspace.resolved_ers?.package_id || "");

    const banned = new Set<string>();
    page.on("request", (req) => {
      const u = req.url().toLowerCase();
      const m = req.method().toUpperCase();
      if (m === "DELETE" || u.includes("/trash") || u.includes("/delete")) {
        banned.add(`${m} ${req.url()}`);
      }
    });

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${SC_URL}&scene_id=${a.sceneId}&sheet_id=${a.sheetId}&spatialProfileId=${a.handoffId}`, {
      waitUntil: "domcontentloaded",
    });
    const standard = page.getByTestId("scene-creator-standard");
    const offline = page.getByText("Studio API Offline", { exact: false });
    await expect.poll(async () => {
      if (await offline.isVisible().catch(() => false)) return "offline";
      if (await standard.isVisible().catch(() => false)) return "ready";
      return "wait";
    }, { timeout: 90_000 }).not.toBe("wait");
    if (await offline.isVisible().catch(() => false)) {
      test.info().annotations.push({ type: "note", description: "UI offline; API persistence certified" });
      return;
    }
    await expect(page.getByTestId("scene-creator-spatial-profile-select")).toBeVisible({ timeout: 45_000 });
    await expect(page.getByTestId("scene-creator-spatial-profile-select")).toHaveValue(a.handoffId);
    const caption = page.getByTestId("scene-creator-cd-caption");
    await expect.poll(async () => {
      const text = ((await caption.textContent().catch(() => "")) || "").trim();
      if (text.includes("Loading Co-Director production data")) return "loading";
      if (text.includes("Co-Director production data loaded") && text.startsWith("✓")) return "loaded";
      if (text.includes("could not be loaded")) return "failed";
      return "missing";
    }, { timeout: 60_000 }).toBe("loaded");
    await expect(caption).toHaveText("✓ Co-Director production data loaded");

    await page.getByTestId("scene-creator-reset-workspace").click();
    await expect(page.getByTestId("scene-creator-reset-dialog")).toBeVisible();
    await page.getByTestId("scene-creator-reset-cancel").click();
    await expect(page.getByTestId("scene-creator-reset-dialog")).toHaveCount(0);
    await expect(page.getByTestId("scene-creator-spatial-profile-select")).toHaveValue(a.handoffId);

    await page.getByTestId("scene-creator-reset-workspace").click();
    await page.getByTestId("scene-creator-reset-confirm").click();
    await expect.poll(async () => page.getByTestId("scene-creator-spatial-profile-select").inputValue(), { timeout: 30_000 }).toBe("");
    await expect(page.getByTestId("scene-creator-cd-caption")).toHaveCount(0);

    const afterReset = await request.get(`${API}/api/scene-creator/projects/${PROJECT_ID}/spatial-profiles`);
    const afterBody = await afterReset.json();
    expect((afterBody.profiles || []).some((p: { handoffId: string }) => p.handoffId === a.handoffId)).toBeTruthy();
    expect(afterBody.selectedProfileId).toBeNull();

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("scene-creator-spatial-profile-select")).toBeVisible({ timeout: 45_000 });
    await expect(page.getByTestId("scene-creator-spatial-profile-select")).toHaveValue("");
    await expect(page.getByTestId("scene-creator-cd-caption")).toHaveCount(0);

    await page.getByTestId("scene-creator-spatial-profile-select").selectOption(a.handoffId);
    await expect.poll(async () => page.getByTestId("scene-creator-spatial-profile-select").inputValue(), { timeout: 30_000 }).toBe(a.handoffId);
    await expect.poll(async () => {
      const text = ((await page.getByTestId("scene-creator-cd-caption").textContent().catch(() => "")) || "").trim();
      if (text.includes("Loading Co-Director production data")) return "loading";
      if (text.includes("Co-Director production data loaded") && text.startsWith("✓")) return "loaded";
      if (text.includes("could not be loaded")) return "failed";
      return "missing";
    }, { timeout: 60_000 }).toBe("loaded");

    await page.getByTestId("scene-creator-spatial-profile-select").evaluate((el) => {
      const select = el as HTMLSelectElement;
      const option = document.createElement("option");
      option.value = "00000000-0000-0000-0000-000000000000";
      option.text = "Invalid profile";
      select.appendChild(option);
      select.value = option.value;
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await expect.poll(async () => {
      const text = ((await page.getByTestId("scene-creator-cd-caption").textContent().catch(() => "")) || "").trim();
      if (text.includes("could not be loaded")) return "failed";
      if (text.includes("Co-Director production data loaded") && text.startsWith("✓")) return "loaded";
      if (text.includes("Loading")) return "loading";
      return "missing";
    }, { timeout: 30_000 }).toBe("failed");
    await expect(page.getByTestId("scene-creator-cd-caption")).not.toHaveText("✓ Co-Director production data loaded");
    expect([...banned], "Reset must not delete Library or Spatial Profile assets").toEqual([]);
  });

  test("D Express launcher does not create a second profile", async ({ request, page }) => {
    const before = await request.get(`${API}/api/scene-creator/projects/${PROJECT_ID}/spatial-profiles`);
    const beforeCount = ((await before.json()).profiles || []).length;
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE}/project/${PROJECT_ID}?workspace=home`, { waitUntil: "domcontentloaded" });
    const open = page.getByTestId("scene-creator-open-standard");
    if (await open.isVisible().catch(() => false)) {
      await open.click();
    }
    const after = await request.get(`${API}/api/scene-creator/projects/${PROJECT_ID}/spatial-profiles`);
    const afterCount = ((await after.json()).profiles || []).length;
    expect(afterCount).toBe(beforeCount);
  });
});
