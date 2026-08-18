import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { createProjectResilient } from "./loraHelpers";

const WEB = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173";
const OUT = path.resolve("artifacts/lora-cert-screenshots");

test("capture LoRA certification screenshots", async ({ page, request }) => {
  fs.mkdirSync(OUT, { recursive: true });
  const projectId = await createProjectResilient(request, "LoRA Screenshot");
  // 1. Setup Wizard LoRA section
  await page.goto(`${WEB}/project/${projectId}?workspace=setup`, { waitUntil: "domcontentloaded", timeout: 90000 });
  const section = page.getByTestId("lora-setup-section");
  await expect(section).toBeVisible({ timeout: 60000 });
  await section.getByRole("button", { name: "Manage" }).click();
  await expect(section.getByTestId("lora-registered-list")).toBeVisible({ timeout: 30000 });
  await page.waitForTimeout(1500);
  await section.screenshot({ path: path.join(OUT, "setup-wizard-lora-section.png") });
  // 2. Image Generator Advanced with LoRA selector
  await page.goto(`${WEB}/project/${projectId}?workspace=imagegen`, { waitUntil: "domcontentloaded", timeout: 90000 });
  await expect(page.getByRole("heading", { name: /Cinematic Image Generator/i })).toBeVisible({ timeout: 90000 });
  await page.getByTestId("cis-mode").selectOption("all_models");
  const allModels = page.getByTestId("cis-accordion-all-models");
  if (!(await allModels.evaluate((el) => (el as HTMLDetailsElement).open))) {
    await allModels.locator("summary").click();
  }
  const browser = page.getByTestId("cis-provider-browser");
  await expect(browser).toBeVisible({ timeout: 30000 });
  await expect(async () => {
    await browser.getByRole("button", { name: "Deselect All" }).click();
    await page.waitForTimeout(1200);
    const sdxlRow = page.getByTestId("cis-provider-sdxl-local");
    await sdxlRow.click({ force: true });
    await page.waitForTimeout(1200);
    const pressed = await page
      .locator('[data-testid^="cis-provider-"][aria-pressed="true"]')
      .evaluateAll((els) => els.map((e) => e.getAttribute("data-testid")));
    if (pressed.length !== 1 || !pressed.includes("cis-provider-sdxl-local")) throw new Error("retry");
  }).toPass({ timeout: 60000 });
  await page.getByTestId("cis-advanced").locator("summary").click();
  const select = page.getByTestId("lora-select");
  await expect(select).toBeVisible({ timeout: 30000 });
  await select.selectOption({ label: "Cinematic XL (Cert Fixture)" });
  await expect(page.getByTestId("lora-strength")).toBeVisible({ timeout: 15000 });
  await page.waitForTimeout(1000);
  await page.getByTestId("cis-advanced").screenshot({ path: path.join(OUT, "imagegen-advanced-lora.png") });
  // 3. Timeline Advanced with video LoRA selector
  await page.goto(`${WEB}/project/${projectId}?workspace=timeline`, { waitUntil: "domcontentloaded", timeout: 90000 });
  await page.waitForTimeout(8000);
  const advanced = page.getByTestId("timeline-inspector-advanced");
  if (await advanced.count()) {
    await advanced.locator("summary").click({ force: true });
    await page.waitForTimeout(1500);
    await advanced.screenshot({ path: path.join(OUT, "timeline-advanced-lora.png") }).catch(() => undefined);
  }
  await request.delete(`${WEB.replace("http://127.0.0.1:5173", "http://127.0.0.1:8758")}/api/projects/${projectId}`).catch(() => undefined);
  console.log("SCREENSHOTS DONE");
});