/**
 * Playwright — Co-Director full-stack multimodal vision on live local Beta.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

const BASE = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173";
const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT_ID = "2347bf46-3762-4763-86c5-4a6032522278";
const KORRI_ID = "c49371ed-ba6b-4c16-ba98-a8b28b72118b";
const ANADRIYA_ID = "b7086f85-3ee3-44db-a395-ae1a94e37fe1";
const EVIDENCE = path.join("docs", "release-gate", "codirector", "evidence");
const UPLOAD_FIXTURE = path.join("tests", "e2e", "codirector", "fixtures", "vision-upload.png");
const VISUAL_QUESTION =
  "Describe the exact arrangement of Korri's visible outfit and the placement/pattern of major markings in the current reference. Include any unusual labels, color treatments, or footwear.";

test.setTimeout(300_000);

async function openCharacter(page: Page, characterId: string) {
  await page.goto(`${BASE}/project/${PROJECT_ID}?workspace=characters&characterId=${characterId}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("character-core")).toBeVisible({ timeout: 30_000 });
  const select = page.getByTestId("character-select");
  if (await select.isVisible().catch(() => false)) {
    if ((await select.inputValue().catch(() => "")) !== characterId) {
      await select.selectOption(characterId);
    }
  }
}

async function openCoDirector(page: Page) {
  const shell = page.getByTestId("codirector-shell");
  if (!(await shell.isVisible().catch(() => false))) {
    const ask = page.getByTestId("character-ask-codirector-crs");
    if (await ask.isVisible().catch(() => false)) {
      await ask.click();
    } else {
      await page.getByRole("button", { name: /co-director/i }).first().click();
    }
  }
  await expect(page.getByTestId("codirector-shell")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("codirector-conversation")).toBeVisible({ timeout: 20_000 });
}

async function sendToCoDirector(page: Page, text: string) {
  const input = page.getByTestId("codirector-composer-input");
  await expect(input).toBeVisible();
  await expect(page.getByTestId("codirector-send-button")).toBeEnabled({ timeout: 60_000 });
  await input.fill(text);
  const before = (await page.locator('[data-testid="codirector-conversation"] .codirector-msg.assistant').all()).length;
  await page.getByTestId("codirector-send-button").click();
  await expect
    .poll(
      async () => {
        const error = page.getByTestId("codirector-send-error");
        if (await error.isVisible().catch(() => false)) return "error";
        const msgs = await page.locator('[data-testid="codirector-conversation"] .codirector-msg.assistant').all();
        const last = msgs[msgs.length - 1];
        if (msgs.length <= before || !last) return "streaming";
        const content = (await last.textContent().catch(() => "")) || "";
        return content.length > 20 ? "done" : "streaming";
      },
      { timeout: 240_000 },
    )
    .toMatch(/done|error/);
}

async function lastAssistantText(page: Page) {
  const msgs = await page.locator('[data-testid="codirector-conversation"] .codirector-msg.assistant').all();
  const last = msgs[msgs.length - 1];
  return last ? (await last.textContent().catch(() => "")) || "" : "";
}

async function shot(page: Page, name: string) {
  fs.mkdirSync(EVIDENCE, { recursive: true });
  await page.screenshot({ path: path.join(EVIDENCE, name), fullPage: true });
}

test.describe("Co-Director fullstack vision", () => {
  test.beforeEach(async ({ request }) => {
    await expect
      .poll(async () => {
        try {
          return (await request.get(`${API}/api/health`, { timeout: 10_000 })).ok();
        } catch {
          return false;
        }
      }, { timeout: 60_000 })
      .toBeTruthy();
  });

  test("A Character context shows Korri reference", async ({ page }) => {
    await openCharacter(page, KORRI_ID);
    await expect(page.getByTestId("character-reference-preview")).toBeVisible({
      timeout: 20_000,
    });
    await shot(page, "vision-A-korri-reference.png");
  });

  test("B Co-Director shows Visual context · Korri", async ({ page }) => {
    await openCharacter(page, KORRI_ID);
    await openCoDirector(page);
    await expect(page.getByTestId("codirector-visual-context")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("codirector-visual-context")).toContainText(/Visual context · Korri/i);
    await shot(page, "vision-B-visual-context-chip.png");
  });

  test("C Visual question completes", async ({ page }) => {
    await openCharacter(page, KORRI_ID);
    await openCoDirector(page);
    await sendToCoDirector(page, VISUAL_QUESTION);
    const text = await lastAssistantText(page);
    expect(text.toLowerCase()).not.toContain("i can't see");
    expect(text.toLowerCase()).not.toContain("i cannot see");
    expect(text.length).toBeGreaterThan(40);
    await shot(page, "vision-C-visual-question.png");
  });

  test("D Grounding uses image-only details", async ({ page }) => {
    await openCharacter(page, KORRI_ID);
    await openCoDirector(page);
    await sendToCoDirector(page, VISUAL_QUESTION);
    const text = (await lastAssistantText(page)).toLowerCase();
    const hits = [
      "starbucks",
      "magenta",
      "olive",
      "pouches",
      "boots",
      "buckle",
      "apron",
      "pinafore",
      "tattered",
      "frayed",
      "thermal",
    ].filter((token) => text.includes(token));
    expect(hits.length, `image-only hits in: ${text.slice(0, 400)}`).toBeGreaterThanOrEqual(2);
    expect(text).not.toContain("i can't see");
    await shot(page, "vision-D-grounding.png");
  });

  test("E Direct upload vision", async ({ page }) => {
    await openCharacter(page, KORRI_ID);
    await openCoDirector(page);
    await page.getByTestId("codirector-file-input").setInputFiles(UPLOAD_FIXTURE);
    await expect(page.getByTestId("codirector-attachment-tray")).toBeVisible({ timeout: 10_000 });
    await sendToCoDirector(
      page,
      "Describe the hairstyle, visible clothing, pose, and distinctive visual details in this image.",
    );
    const text = (await lastAssistantText(page)).toLowerCase();
    expect(text).not.toContain("i can't see");
    expect(
      text.includes("triangle") ||
        text.includes("yellow") ||
        text.includes("magenta") ||
        text.includes("purple") ||
        text.includes("pink"),
    ).toBeTruthy();
    await shot(page, "vision-E-direct-upload.png");
  });

  test("F Character switch updates visual context", async ({ page }) => {
    await openCharacter(page, KORRI_ID);
    await openCoDirector(page);
    await expect(page.getByTestId("codirector-visual-context")).toContainText(/Korri/i);
    await page.getByTestId("character-select").selectOption(ANADRIYA_ID);
    await expect(page.getByTestId("codirector-visual-context")).toContainText(/Anadriya/i, { timeout: 15_000 });
    await sendToCoDirector(page, "Describe the visible clothing and markings from her current reference.");
    const error = page.getByTestId("codirector-send-error");
    const errorVisible = await error.isVisible().catch(() => false);
    const text = (await lastAssistantText(page)).toLowerCase();
    if (errorVisible) {
      await expect(error).toContainText(/vision/i);
    } else {
      expect(text.includes("starbucks") || text.includes("korri")).toBeFalsy();
    }
    await shot(page, "vision-F-character-switch.png");
  });

  test("G Missing vision asset is visible", async ({ page }) => {
    await openCharacter(page, ANADRIYA_ID);
    await openCoDirector(page);
    await sendToCoDirector(page, "Describe the visible clothing and markings from her current reference.");
    await expect(page.getByTestId("codirector-send-error")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("codirector-send-error")).toContainText(/vision/i);
    await shot(page, "vision-G-error.png");
  });

  test("H Reload keeps conversation and visual context", async ({ page }) => {
    await openCharacter(page, KORRI_ID);
    await openCoDirector(page);
    const prompt = "Please confirm you can see the current Character work and stay with this project.";
    await sendToCoDirector(page, prompt);
    const before = await lastAssistantText(page);
    expect(before.length).toBeGreaterThan(20);
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("character-core")).toBeVisible({ timeout: 30_000 });
    await openCoDirector(page);
    await expect(page.getByTestId("codirector-visual-context")).toContainText(/Korri/i, { timeout: 20_000 });
    await expect(page.getByTestId("codirector-conversation")).toContainText(/stay with this project/i, { timeout: 20_000 });
    await shot(page, "vision-H-reload.png");
  });

  test("I Responsive visual-context chip", async ({ page }) => {
    await openCharacter(page, KORRI_ID);
    await openCoDirector(page);
    await expect(page.getByTestId("codirector-visual-context")).toBeVisible();
    for (const [name, width, height] of [
      ["1920", 1920, 1080],
      ["1440", 1440, 900],
      ["1024", 1024, 768],
      ["768", 768, 1024],
    ] as const) {
      await page.setViewportSize({ width, height });
      await expect(page.getByTestId("codirector-visual-context")).toBeVisible();
      await shot(page, `vision-I-responsive-${name}.png`);
    }
  });
});
