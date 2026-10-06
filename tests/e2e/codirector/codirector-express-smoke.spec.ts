/**
 * Co-Director + Express frontend smoke.
 * Creates one disposable project through the UI and leaves it in place.
 * Production source is not modified by this spec.
 */
import { expect, test, type Page, type TestInfo } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

test.use({ trace: "on", video: "on" });

type StepResult = {
  step: string;
  status: "PASS" | "FAIL" | "BLOCKED";
  detail: string;
};

const SURFACES: Array<{ tab: string; panel: string; label: string }> = [
  { tab: "timeline", panel: "codirector-content-timeline", label: "Timeline" },
  { tab: "library", panel: "codirector-content-library", label: "Library" },
  { tab: "wiki", panel: "codirector-content-wiki", label: "Wiki" },
  { tab: "notes", panel: "codirector-content-notes", label: "Notes" },
  { tab: "story", panel: "codirector-content-story", label: "Story" },
];

test("disposable Co-Director and Express smoke", async ({ page }, testInfo) => {
  test.setTimeout(300_000);
  const stamp = new Date();
  const hh = String(stamp.getHours()).padStart(2, "0");
  const mm = String(stamp.getMinutes()).padStart(2, "0");
  const ss = String(stamp.getSeconds()).padStart(2, "0");
  const token = `20261005_${hh}${mm}${ss}`;
  const projectName = `SANITATION_SMOKE_${token}`;
  const names = {
    character: `Smoke Character ${token}`,
    voice: `Smoke Voice ${token}`,
    prop: `Smoke Prop ${token}`,
    environment: `Smoke Environment ${token}`,
  };
  const evidenceDir = path.join("artifacts", "codirector-express-smoke", token);
  fs.mkdirSync(evidenceDir, { recursive: true });

  const steps: StepResult[] = [];
  const consoleErrors: string[] = [];
  const failedRequests: string[] = [];
  let projectId = "";

  page.on("console", (msg) => {
    if (msg.type() !== "error") return;
    const text = msg.text();
    if (/chrome-extension|moz-extension|edge-extension/i.test(text)) return;
    consoleErrors.push(text.slice(0, 500));
  });
  page.on("pageerror", (err) => {
    consoleErrors.push(String(err?.message || err).slice(0, 500));
  });
  page.on("response", (response) => {
    const status = response.status();
    if (status < 400) return;
    const url = response.url();
    if (!/127\.0\.0\.1:(5173|8758)|localhost:(5173|8758)/.test(url)) return;
    if (/favicon|sourcemap|\.map(\?|$)/i.test(url)) return;
    failedRequests.push(`${status} ${url.slice(0, 240)}`);
  });

  async function shot(name: string) {
    await page.screenshot({ path: path.join(evidenceDir, `${name}.png`), fullPage: true }).catch(() => undefined);
  }

  async function record(step: string, fn: () => Promise<string>) {
    try {
      const detail = await fn();
      steps.push({ step, status: "PASS", detail });
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      steps.push({ step, status: "FAIL", detail: detail.slice(0, 800) });
      await page
        .screenshot({
          path: path.join(evidenceDir, `FAIL_${step}_${token}.png`),
          fullPage: true,
        })
        .catch(() => undefined);
    }
  }

  try {
    await record("01_project_created", async () => {
      await page.goto("/");
      await expect(page.getByTestId("generation-studio-home")).toBeVisible({ timeout: 30_000 });
      await page.getByTestId("create-project-open").click();
      await expect(page.getByTestId("create-project-modal")).toBeVisible();
      await page.locator("#np-name").fill(projectName);
      await page.getByTestId("create-project-submit").click();
      await expect(page.getByTestId("create-project-modal")).toBeHidden({ timeout: 30_000 });
      await expect(page.getByTestId("codirector-project-context")).toContainText(projectName, { timeout: 20_000 });
      await page.getByTestId("enter-codirector").click();
      await page.waitForURL(/projectId=/, { timeout: 30_000 });
      projectId = new URL(page.url()).searchParams.get("projectId") || "";
      expect(projectId, "project id in the Co-Director URL").toMatch(/[0-9a-f-]{8,}/i);
      await expect(page.getByTestId("codirector-composer-input")).toBeVisible({ timeout: 30_000 });
      await shot("01_project_created");
      return `${projectName} ${projectId}`;
    });

    await record("02_codirector_reply", async () => {
      if (!projectId) throw new Error("No project id from step 1.");
      const composer = page.getByTestId("codirector-composer-input");
      await expect(composer).toBeVisible({ timeout: 30_000 });
      const expand = page.getByTestId("codirector-expand-button");
      if (await expand.isVisible().catch(() => false)) {
        await expand.click();
      }
      await expect(page.getByTestId("codirector-fullscreen-shell").or(page.getByTestId("codirector-shell")).first()).toBeVisible();
      const prompt = "This is a frontend smoke test. Please confirm that you can see this project context without creating anything.";
      const before = await page.locator("article.codirector-msg.assistant").count();
      await composer.fill(prompt);
      await page.getByTestId("codirector-send-button").click();
      await expect(page.locator("article.codirector-msg.user").filter({ hasText: "frontend smoke test" })).toBeVisible({
        timeout: 15_000,
      });
      await expect(page.getByTestId("codirector-composer-processing")).toBeHidden({ timeout: 120_000 });
      await expect.poll(async () => page.locator("article.codirector-msg.assistant").count(), { timeout: 15_000 }).toBeGreaterThan(before);
      const text = (await page.locator("article.codirector-msg.assistant").nth(before).innerText()).trim();
      expect(text.length).toBeGreaterThan(20);
      expect(text).not.toContain("Tell me what you'd like to create");
      expect(text.toLowerCase()).not.toContain("interrupted before it finished");
      await shot("02_codirector_reply");
      return text.slice(0, 400);
    });

    await record("03_character", async () => {
      await openTab(page, "characters", "codirector-content-characters");
      await expect(page.getByTestId("character-compact")).toBeVisible({ timeout: 20_000 });
      await page.getByTestId("character-compact-create").click();
      await page.getByTestId("character-field-name").fill(names.character);
      await page.getByTestId("character-save").click();
      await expect(page.getByTestId("character-compact-saved-select")).toContainText(names.character, { timeout: 20_000 });
      await shot("03_character");
      return names.character;
    });

    await record("04_voice", async () => {
      await openTab(page, "voice_creator", "codirector-content-voice-creator");
      await expect(page.getByTestId("voice-creator-express").or(page.getByTestId("voice-identity-panel")).first()).toBeVisible({
        timeout: 20_000,
      });
      await page.getByTestId("vs-character-select").click();
      await page.getByTestId("vs-character-select-option").filter({ hasText: "Create New Character" }).click();
      await page.getByTestId("vs-new-character-name").fill(names.voice);
      await page.getByTestId("vs-create-character-btn").click();
      await expect(page.getByTestId("voice-creator-express").or(page.getByTestId("voice-identity-panel")).first()).toContainText(names.voice, {
        timeout: 20_000,
      });
      await shot("04_voice");
      return `${names.voice} (identity saved, no sample synthesis)`;
    });

    await record("05_prop", async () => {
      await openTab(page, "prop_creator", "codirector-content-prop-creator");
      await expect(page.getByTestId("prop-creator-panel")).toBeVisible({ timeout: 20_000 });
      await page.getByTestId("prop-creator-name").first().fill(names.prop);
      const description = page.getByTestId("prop-creator-description");
      if (await description.isVisible().catch(() => false)) {
        await description.fill("A small smoke-test prop. Metal cube, no generation.");
      }
      await page.getByTestId("prop-creator-save").click();
      await expect(page.getByTestId("prop-creator-panel")).toContainText(names.prop, { timeout: 20_000 });
      await shot("05_prop");
      return names.prop;
    });

    await record("06_environment", async () => {
      await openTab(page, "scene_creator", "codirector-content-scene-creator");
      await expect(page.getByTestId("environment-creator-surface")).toBeVisible({ timeout: 20_000 });
      const createNew = page.getByTestId("environment-creator-new");
      if (await createNew.isEnabled().catch(() => false)) {
        await createNew.click();
      }
      await page.getByTestId("environment-creator-name").fill(names.environment);
      await page.getByTestId("environment-creator-save-top").click();
      await expect(page.getByTestId("environment-creator-save-top")).toContainText(/Saved/i, { timeout: 20_000 });
      await expect(page.getByTestId("environment-creator-surface")).toContainText(names.environment);
      await shot("06_environment");
      return names.environment;
    });

    await record("07_navigation", async () => {
      const seen: string[] = [];
      for (const surface of SURFACES) {
        await openTab(page, surface.tab, surface.panel);
        seen.push(surface.label);
      }
      await shot("07_navigation");
      return seen.join(", ");
    });

    await record("08_asset_names", async () => {
      await openTab(page, "characters", "codirector-content-characters");
      await expect(page.getByTestId("character-compact")).toContainText(names.character, { timeout: 20_000 });
      await openTab(page, "voice_creator", "codirector-content-voice-creator");
      await page.getByTestId("vs-character-select").click();
      await expect(page.getByTestId("vs-character-select-list")).toContainText(names.voice, { timeout: 15_000 });
      await page.keyboard.press("Escape");
      await openTab(page, "prop_creator", "codirector-content-prop-creator");
      await expect(page.getByTestId("prop-creator-panel")).toContainText(names.prop);
      await openTab(page, "scene_creator", "codirector-content-scene-creator");
      await expect(page.getByTestId("environment-creator-surface")).toContainText(names.environment);
      await shot("08_asset_names");
      return "character, voice, prop, environment visible";
    });

    await record("09_after_reload_persistence", async () => {
      await page.reload();
      await expect(page.getByTestId("codirector-composer-input")).toBeVisible({ timeout: 30_000 });
      await openTab(page, "characters", "codirector-content-characters");
      await expect(page.getByTestId("character-compact")).toContainText(names.character, { timeout: 20_000 });
      await openTab(page, "voice_creator", "codirector-content-voice-creator");
      await page.getByTestId("vs-character-select").click();
      await expect(page.getByTestId("vs-character-select-list")).toContainText(names.voice, { timeout: 15_000 });
      await page.keyboard.press("Escape");
      await openTab(page, "prop_creator", "codirector-content-prop-creator");
      await expect(page.getByTestId("prop-creator-panel")).toContainText(names.prop);
      await openTab(page, "scene_creator", "codirector-content-scene-creator");
      await expect(page.getByTestId("environment-creator-surface")).toContainText(names.environment);
      await shot("09_after_reload_persistence");
      return "four names present after reload";
    });
  } finally {
    const summary = {
      projectName,
      projectId,
      names,
      steps,
      consoleErrors: consoleErrors.slice(0, 40),
      failedRequests: failedRequests.slice(0, 40),
    };
    fs.writeFileSync(path.join(evidenceDir, "summary.json"), JSON.stringify(summary, null, 2));
    await testInfo.attach("smoke-summary", {
      body: JSON.stringify(summary, null, 2),
      contentType: "application/json",
    });
  }

  const failed = steps.filter((step) => step.status !== "PASS");
  expect(failed, JSON.stringify(failed, null, 2)).toEqual([]);
  const productFailures = failedRequests.filter((line) => /127\.0\.0\.1:8758/.test(line));
  expect(productFailures, "product API responses").toEqual([]);
});

async function openTab(page: Page, tab: string, panel: string) {
  const button = page.getByTestId(`codirector-content-tab-${tab}`);
  await expect(button).toBeVisible({ timeout: 20_000 });
  await button.click();
  await expect(page.getByTestId(panel)).toBeVisible({ timeout: 20_000 });
}
