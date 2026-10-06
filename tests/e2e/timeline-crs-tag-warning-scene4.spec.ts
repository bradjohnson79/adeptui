import { test, expect } from "@playwright/test";
import fs from "fs";
import path from "path";

const PROJECT = "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";
const SCENE = "a4c85c6d-2f0e-4e49-8535-7c698306f398";
const OUT_DIR = "C:/Users/bradj/theme_walk/timeline_crs_tag_warning";

test("Scene 4 bound CRS @tags clear missing-sheet banner", async ({ page, request }) => {
  fs.mkdirSync(OUT_DIR, { recursive: true });

  const apiBase = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
  const health = await request.get(`${apiBase}/api/healthz`);
  test.skip(!health.ok(), "Studio API not accessible");

  await page.goto(`/project/${PROJECT}?workspace=timeline&sceneId=${SCENE}`, {
    waitUntil: "domcontentloaded",
  });

  const refsList = page.getByTestId("references-list");
  await expect(refsList).toBeVisible({ timeout: 25000 });

  const korriChip = page.locator('[data-testid^="reference-chip-"]').filter({ hasText: "@Korri40YearsOld" });
  const addexChip = page.locator('[data-testid^="reference-chip-"]').filter({ hasText: "@Addex" });
  await expect(korriChip.first()).toBeVisible({ timeout: 15000 });
  await expect(addexChip.first()).toBeVisible({ timeout: 15000 });

  const bodyBefore = (await page.locator("body").textContent()) || "";
  expect(bodyBefore).toContain("@Korri40YearsOld");
  expect(bodyBefore).toContain("@Addex");

  await page.screenshot({ path: path.join(OUT_DIR, "01_scene4_refs_and_tags.png"), fullPage: true });

  const generateBtn = page.locator('[data-testid="timeline-header-generate"], [data-testid="timeline-toolbar-generate"], button:has-text("Generate")').first();
  if (await generateBtn.isVisible().catch(() => false)) {
    await generateBtn.click().catch(() => {});
    await page.waitForTimeout(3000);
  }

  await page.screenshot({ path: path.join(OUT_DIR, "02_scene4_after_generate_click.png"), fullPage: true });

  const bodyText = (await page.locator("body").textContent()) || "";
  const falseBanner =
    /Korri40YearsOld is named in this shot but has no Character Reference Sheet/i.test(bodyText) ||
    /Korri is named in this shot but has no Character Reference Sheet/i.test(bodyText);

  expect(bodyText).toContain("@Korri40YearsOld");
  expect(bodyText).toContain("@Addex");
  expect(falseBanner).toBeFalsy();

  const notice = page.locator('[data-testid="timeline-action-notice"]');
  if (await notice.count()) {
    const noticeText = (await notice.first().textContent()) || "";
    expect(noticeText).not.toMatch(/no Character Reference Sheet/i);
  }

  fs.writeFileSync(
    path.join(OUT_DIR, "ui_probe.json"),
    JSON.stringify(
      {
        project: PROJECT,
        scene: SCENE,
        korriChip: "@Korri40YearsOld",
        addexChip: "@Addex",
        falseBannerPresent: falseBanner,
        tagsRemain: {
          korri: bodyText.includes("@Korri40YearsOld"),
          addex: bodyText.includes("@Addex"),
        },
      },
      null,
      2,
    ),
    "utf8",
  );
});
