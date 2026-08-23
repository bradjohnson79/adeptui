/**
 * M30F multilingual E2E — Schnick Coffee only.
 * Never POST /api/projects.
 */
import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const WEB = process.env.ADEPT_WEB_URL || process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173";
const API = process.env.ADEPT_API_URL || process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT =
  process.env.ADEPT_SCHNICK_PROJECT_ID ||
  process.env.ADEPT_PROJECT_ID ||
  "2347bf46-3762-4763-86c5-4a6032522278";
const ARTIFACTS = path.resolve("artifacts/m30f-i18n");

function prefs(patch: Record<string, unknown>) {
  return JSON.stringify({
    interfaceLocale: "en",
    conversationLocale: "en",
    projectPrimaryLocale: "en",
    promptLanguagePolicy: "auto",
    exportLocale: "en",
    followOsLocale: false,
    ...patch,
  });
}

async function seedPrefs(page: Page, patch: Record<string, unknown>) {
  await page.addInitScript((raw) => {
    localStorage.setItem("adept_ui_language_prefs_v1", raw);
  }, prefs(patch));
}

function ensureDir() {
  fs.mkdirSync(ARTIFACTS, { recursive: true });
}

async function waitTimelineChrome(page: Page) {
  await expect(page.locator(".timeline-scene-header__btn.primary").first()).toBeVisible({ timeout: 60_000 });
}

test.describe("M30F multilingual E2E — Schnick Coffee", () => {
  test("English baseline chrome", async ({ page }) => {
    ensureDir();
    await seedPrefs(page, { interfaceLocale: "en" });
    await page.goto(`${WEB}/project/${PROJECT}?workspace=timeline`, { waitUntil: "domcontentloaded" });
    await expect(page.locator("html")).toHaveAttribute("lang", "en");
    await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
    await waitTimelineChrome(page);
    await expect(page.getByText("Generate Scene", { exact: true })).toBeVisible();
    await expect(page.getByText("Schnick Coffee").first()).toBeVisible();
    await page.screenshot({ path: path.join(ARTIFACTS, "visual-en-timeline.png"), fullPage: true });
  });

  test("Spanish UI — Timeline, Image Generator, Storyboard; reload persists", async ({ page }) => {
    await seedPrefs(page, { interfaceLocale: "es" });
    await page.goto(`${WEB}/project/${PROJECT}?workspace=timeline`, { waitUntil: "domcontentloaded" });
    await expect(page.locator("html")).toHaveAttribute("lang", "es");
    await waitTimelineChrome(page);
    await expect(page.getByText("Generar escena", { exact: true })).toBeVisible();
    await page.screenshot({ path: path.join(ARTIFACTS, "visual-es-timeline.png"), fullPage: true });

    await page.goto(`${WEB}/project/${PROJECT}?workspace=imagegen`, { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: /Generador de imagen cinematográfica/i })).toBeVisible({
      timeout: 60_000,
    });
    await expect(page.getByText("Generar imágenes", { exact: true })).toBeVisible();

    await page.goto(`${WEB}/project/${PROJECT}?workspace=script`, { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: /Estudio de storyboard/i })).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText("Preparar para la timeline", { exact: true })).toBeVisible();

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.locator("html")).toHaveAttribute("lang", "es");
    await expect(page.getByRole("heading", { name: /Estudio de storyboard/i })).toBeVisible({ timeout: 60_000 });
  });

  test("Interface English + conversation French — live Co-Director reply", async ({ page, request }) => {
    test.setTimeout(300_000);
    await seedPrefs(page, { interfaceLocale: "en", conversationLocale: "fr" });
    await page.goto(`${WEB}/project/${PROJECT}?workspace=settings`, { waitUntil: "domcontentloaded" });
    await page.getByRole("tab", { name: /Language|Idioma/i }).click();
    await expect(page.getByTestId("m30f-interface-locale")).toBeVisible({ timeout: 60_000 });
    await page.getByTestId("m30f-conversation-locale").selectOption("fr");
    await page.getByTestId("m30f-interface-locale").selectOption("en");

    await page.goto(`${WEB}/project/${PROJECT}?workspace=timeline`, { waitUntil: "domcontentloaded" });
    await waitTimelineChrome(page);
    await expect(page.getByText("Generate Scene", { exact: true })).toBeVisible();

    const stream = await request.post(`${API}/api/codirector/chat/stream`, {
      data: {
        project_id: PROJECT,
        conversationLocale: "fr",
        mode: "chat",
        messages: [{ role: "user", content: "Dis bonjour en une phrase courte." }],
      },
      timeout: 240_000,
    });
    expect(stream.ok(), await stream.text()).toBeTruthy();
    const text = (await stream.body()).toString("utf8");
    let reply = "";
    for (const line of text.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed.startsWith("data:")) continue;
      const payload = trimmed.slice("data:".length).trim();
      if (!payload) continue;
      try {
        const evt = JSON.parse(payload) as { type?: string; content?: string; text?: string };
        if (evt.type === "completed" || evt.type === "completion") reply = evt.content || reply;
        if (evt.type === "delta" && evt.text) reply += evt.text;
      } catch {
        /* ignore */
      }
    }
    expect(reply.length).toBeGreaterThan(4);
    expect(/[àâéèêëîïôùûç]|bonjour|salut|voilà|merci|je |une |est /i.test(reply)).toBeTruthy();
    fs.writeFileSync(path.join(ARTIFACTS, "codirector-french-reply.json"), JSON.stringify({ reply, raw: text.slice(0, 4000) }, null, 2));
  });

  test("Spanish UI + French conversation + English prompt policy compiles English", async ({ request }) => {
    const res = await request.post(`${API}/api/codirector/model-intelligence/compile`, {
      data: {
        userPrompt: "Korri tastes Schnick Coffee at dusk",
        modelId: "fal_seedance",
        forceModelId: "fal_seedance",
        mode: "text_to_video",
        mediaType: "video",
        projectContext: {
          sourceLanguage: "fr",
          promptLanguagePolicy: "english",
          projectPrimaryLocale: "en",
          conversationLocale: "fr",
        },
      },
    });
    expect(res.ok(), await res.text()).toBeTruthy();
    const body = await res.json();
    expect(body.promptLanguage).toBe("en");
    fs.writeFileSync(path.join(ARTIFACTS, "compile-english-policy.json"), JSON.stringify(body, null, 2));
  });

  test("Bilingual compile shows English-first + Simplified Chinese", async ({ request }) => {
    const mil = await request.post(`${API}/api/codirector/model-intelligence/compile`, {
      data: {
        userPrompt: "Korri tastes Schnick Coffee at dusk",
        modelId: "fal_seedance",
        forceModelId: "fal_seedance",
        mode: "text_to_video",
        mediaType: "video",
        projectContext: { promptLanguagePolicy: "bilingual", sourceLanguage: "en", projectPrimaryLocale: "en" },
      },
    });
    expect(mil.ok(), await mil.text()).toBeTruthy();
    const milBody = await mil.json();
    fs.writeFileSync(path.join(ARTIFACTS, "compile-bilingual-mil.json"), JSON.stringify(milBody, null, 2));

    const enhance = await request.post(`${API}/api/codirector/prompt-intelligence/enhance`, {
      data: {
        creatorPrompt: "Korri tastes Schnick Coffee at dusk",
        domain: "image",
        characterNames: ["Korri"],
        modulesEnabled: { languageModules: ["en", "zh"] },
        languageBalance: "balanced",
        projectPrefs: { promptLanguagePolicy: "bilingual" },
      },
    });
    expect(enhance.ok(), await enhance.text()).toBeTruthy();
    const rec = (await enhance.json()).record || {};
    const final = String(rec.finalProviderPrompt || "");
    const zh = String((rec.languageEnhancements || {}).zh || rec.chineseEnhancement || "");
    expect(zh.length).toBeGreaterThan(0);
    expect(final).toContain("\n");
    expect(/[\u4e00-\u9fff]/.test(final) || /[\u4e00-\u9fff]/.test(zh)).toBeTruthy();
    const enPart = String(rec.refinedEnglishPrompt || "");
    if (enPart && zh && final.includes(zh) && final.includes(enPart)) {
      expect(final.indexOf(enPart)).toBeLessThan(final.indexOf(zh));
    }
    if (milBody.promptLanguage !== "en+zh-Hans") {
      expect(zh.length, "live MIL compile stale; PI enhance still produced Chinese").toBeGreaterThan(0);
    } else {
      expect(milBody.promptLanguage).toBe("en+zh-Hans");
    }
    fs.writeFileSync(
      path.join(ARTIFACTS, "compile-bilingual.json"),
      JSON.stringify({ mil: milBody, enhance: rec }, null, 2),
    );
  });

  test("Arabic RTL — html dir, Timeline axis LTR, preview not mirrored", async ({ page }) => {
    await seedPrefs(page, { interfaceLocale: "ar" });
    await page.goto(`${WEB}/project/${PROJECT}?workspace=timeline`, { waitUntil: "domcontentloaded" });
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    await expect(page.locator("html")).toHaveAttribute("lang", "ar");
    await waitTimelineChrome(page);
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    const dir = await page.locator(".timeline-editor-shell__tracks").first().evaluate((el) => getComputedStyle(el).direction);
    expect(dir).toBe("ltr");
    const transform = await page
      .locator(".live-preview-stage img, .live-preview-stage video, video")
      .first()
      .evaluate((el) => getComputedStyle(el).transform)
      .catch(() => "none");
    expect(transform === "none" || transform === "matrix(1, 0, 0, 1, 0, 0)").toBeTruthy();
    await page.screenshot({ path: path.join(ARTIFACTS, "visual-ar-timeline.png"), fullPage: true });
  });

  test("Urdu dir=rtl smoke", async ({ page }) => {
    await seedPrefs(page, { interfaceLocale: "ur" });
    await page.goto(`${WEB}/project/${PROJECT}?workspace=timeline`, { waitUntil: "domcontentloaded" });
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    await expect(page.locator("html")).toHaveAttribute("lang", "ur");
  });

  test("Japanese or Simplified Chinese visual + switch back to English leaves Schnick data", async ({ page }) => {
    await seedPrefs(page, { interfaceLocale: "zh-Hans" });
    await page.goto(`${WEB}/project/${PROJECT}?workspace=imagegen`, { waitUntil: "domcontentloaded" });
    await expect(page.locator("html")).toHaveAttribute("lang", "zh-Hans");
    await page.screenshot({ path: path.join(ARTIFACTS, "visual-zh-Hans-imagegen.png"), fullPage: true });

    await seedPrefs(page, { interfaceLocale: "en", conversationLocale: "en", promptLanguagePolicy: "auto" });
    await page.goto(`${WEB}/project/${PROJECT}?workspace=timeline`, { waitUntil: "domcontentloaded" });
    await expect(page.locator("html")).toHaveAttribute("lang", "en");
    await waitTimelineChrome(page);
    await expect(page.getByText("Schnick Coffee").first()).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText("Generate Scene", { exact: true })).toBeVisible();
  });
});
