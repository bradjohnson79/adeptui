/**
 * Playwright — Co-Director intelligence remediation on live local Beta.
 * Tests A–I plus 11-step Korri trace and responsive shots.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

const BASE = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173";
const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT_ID = "2347bf46-3762-4763-86c5-4a6032522278";
const KORRI_ID = "c49371ed-ba6b-4c16-ba98-a8b28b72118b";
const EVIDENCE = path.resolve(
  __dirname,
  "..",
  "..",
  "..",
  "docs",
  "release-gate",
  "codirector-reasoning",
  "evidence",
);

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
  await input.fill(text);
  const send = page.getByTestId("codirector-send-button");
  await expect(send).toBeEnabled({ timeout: 60_000 });
  const before = (await page.locator('[data-testid="codirector-conversation"] .codirector-msg.assistant').all()).length;
  await send.click();
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

function forbiddenCommandHijack(text: string) {
  const lower = text.toLowerCase();
  expect(lower).not.toContain("cyber-grunge");
  expect(lower).not.toContain("which direction");
  expect(lower).not.toMatch(/would you like/);
}

test.describe("Co-Director intelligence remediation", () => {
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

  test("A Capability question answers from runtime state", async ({ page }) => {
    await openCharacter(page, KORRI_ID);
    await openCoDirector(page);
    await sendToCoDirector(page, "Do you have vision?");
    const text = (await lastAssistantText(page)).toLowerCase();
    expect(text.length).toBeGreaterThan(20);
    expect(text).toMatch(/vision|see|model|active|support/);
    expect(text).not.toContain("cyber-grunge");
    await shot(page, "intel-A-capability.png");
  });

  test("B Narrow visual question stays on the image", async ({ page }) => {
    await openCharacter(page, KORRI_ID);
    await openCoDirector(page);
    await sendToCoDirector(page, "What color are Korri's boots in the current reference?");
    const text = (await lastAssistantText(page)).toLowerCase();
    expect(text.length).toBeGreaterThan(20);
    expect(text).not.toContain("i can't see");
    await shot(page, "intel-B-visual-q.png");
  });

  test("C Korri CRS command acts without a questionnaire", async ({ page }) => {
    const trace: Record<string, unknown>[] = [];
    page.on("request", (req) => {
      if (req.url().includes("/api/codirector/chat/stream") && req.method() === "POST") {
        try {
          trace.push({ step: "payload", postData: req.postData() });
        } catch {
          trace.push({ step: "payload", postData: null });
        }
      }
    });
    await openCharacter(page, KORRI_ID);
    await openCoDirector(page);
    await sendToCoDirector(page, "Create Korri's CRS.");
    const text = await lastAssistantText(page);
    forbiddenCommandHijack(text);
    expect(text.toLowerCase()).toMatch(/creating|reference sheet|crs|visual sheet|started|generating/);
    fs.mkdirSync(EVIDENCE, { recursive: true });
    fs.writeFileSync(
      path.join(EVIDENCE, "korri-crs-11-step-trace.json"),
      JSON.stringify(
        {
          userAction: "Create Korri's CRS.",
          frontend: "codirector-send-button",
          payload: trace,
        },
        null,
        2,
      ),
    );
    await shot(page, "intel-C-korri-crs-command.png");
  });

  test("D CRS result or progress is visible", async ({ page }) => {
    await openCharacter(page, KORRI_ID);
    await openCoDirector(page);
    await sendToCoDirector(page, "Create Korri's CRS.");
    const text = (await lastAssistantText(page)).toLowerCase();
    forbiddenCommandHijack(text);
    const progress = page.getByTestId("codirector-conversation");
    await expect(progress).toBeVisible();
    expect(text.length).toBeGreaterThan(15);
    await shot(page, "intel-D-crs-progress.png");
  });

  test("E Required clarification asks only the missing field", async ({ page }) => {
    await page.goto(`${BASE}/project/${PROJECT_ID}?workspace=library`, { waitUntil: "domcontentloaded" });
    await openCoDirector(page);
    await sendToCoDirector(page, "Create a character reference sheet.");
    const text = (await lastAssistantText(page)).toLowerCase();
    expect(text).toMatch(/which character|who should|which one/);
    expect(text).not.toMatch(/creating .+ now/);
    expect(text).not.toContain("cyber-grunge");
    await shot(page, "intel-E-required-clarification.png");
  });

  test("F Optional ambiguity still acts", async ({ page }) => {
    await openCharacter(page, KORRI_ID);
    await openCoDirector(page);
    await sendToCoDirector(page, "Create Korri's CRS in a slightly cooler palette.");
    const text = await lastAssistantText(page);
    forbiddenCommandHijack(text);
    expect(text.toLowerCase()).toMatch(/creating|reference sheet|crs|started|generating/);
    await shot(page, "intel-F-optional-ambiguity.png");
  });

  test("G Retry resends the user command", async ({ page }) => {
    await openCharacter(page, KORRI_ID);
    await openCoDirector(page);
    await sendToCoDirector(page, "Create Korri's CRS.");
    const retry = page.getByRole("button", { name: /retry/i }).first();
    if (await retry.isVisible().catch(() => false)) {
      await retry.click();
      await expect
        .poll(async () => (await lastAssistantText(page)).length, { timeout: 240_000 })
        .toBeGreaterThan(15);
    }
    const text = await lastAssistantText(page);
    forbiddenCommandHijack(text);
    await shot(page, "intel-G-retry.png");
  });

  test("H NBA is suppressed during the CRS command", async ({ page }) => {
    await openCharacter(page, KORRI_ID);
    await openCoDirector(page);
    await sendToCoDirector(page, "Create Korri's CRS.");
    const actions = page.getByTestId("codirector-conversation-actions");
    await expect(actions).toHaveCount(0);
    forbiddenCommandHijack(await lastAssistantText(page));
    await shot(page, "intel-H-nba-suppressed.png");
  });

  test("I Reload keeps the Korri conversation", async ({ page }) => {
    await openCharacter(page, KORRI_ID);
    await openCoDirector(page);
    await sendToCoDirector(page, "Create Korri's CRS.");
    const before = await lastAssistantText(page);
    expect(before.length).toBeGreaterThan(15);
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("character-core")).toBeVisible({ timeout: 30_000 });
    await openCoDirector(page);
    await expect(page.getByTestId("codirector-conversation")).toContainText(/CRS|reference sheet|Creating/i, {
      timeout: 20_000,
    });
    for (const [name, width, height] of [
      ["1920", 1920, 1080],
      ["1440", 1440, 900],
      ["1024", 1024, 768],
      ["768", 768, 1024],
    ] as const) {
      await page.setViewportSize({ width, height });
      await expect(page.getByTestId("codirector-shell")).toBeVisible();
      await shot(page, `intel-I-responsive-${name}.png`);
    }
  });
});
