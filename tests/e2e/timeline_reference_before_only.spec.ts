import { test, expect } from "@playwright/test";
import path from "path";
const BASE = "http://127.0.0.1:5173";
const PROJECT = "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";
const EVIDENCE = String.raw`C:\Users\bradj\theme_walk\timeline_reference_tag`;
const EVIDENCE_AGENT = String.raw`C:\Users\bradj\agent-tools\theme_walk\timeline_reference_tag`;
test("BEFORE Filter", async ({ page }) => {
  test.setTimeout(90000);
  await page.goto(`${BASE}/project/${PROJECT}?workspace=timeline`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2500);
  await expect(page.getByTestId("scene-references-pane")).toBeVisible({ timeout: 45000 });
  await expect(page.getByTestId("references-filter")).toBeVisible();
  await page.screenshot({ path: path.join(EVIDENCE, "00_BEFORE_filter.png"), fullPage: false });
  await page.screenshot({ path: path.join(EVIDENCE_AGENT, "00_BEFORE_filter.png"), fullPage: false });
});
