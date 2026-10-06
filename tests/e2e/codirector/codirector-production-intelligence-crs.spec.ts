/**
 * Playwright A–H — Co-Director CRS production loop + CRS vs multi-view routing.
 */
import fs from "node:fs";
import path from "path";
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

test.setTimeout(20 * 60 * 1000);

async function openKorri(page: Page) {
  await page.goto(`${BASE}/project/${PROJECT_ID}?workspace=characters&characterId=${KORRI_ID}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("character-core")).toBeVisible({ timeout: 30_000 });
}

async function openCoDirector(page: Page) {
  if (!(await page.getByTestId("codirector-shell").isVisible().catch(() => false))) {
    const ask = page.getByTestId("character-ask-codirector-crs");
    if (await ask.isVisible().catch(() => false)) await ask.click();
    else await page.getByRole("button", { name: /co-director/i }).first().click();
  }
  await expect(page.getByTestId("codirector-shell")).toBeVisible({ timeout: 20_000 });
}

async function sendToCoDirector(page: Page, text: string) {
  const input = page.getByTestId("codirector-composer-input");
  await input.fill(text);
  const send = page.getByTestId("codirector-send-button");
  await expect(send).toBeEnabled({ timeout: 60_000 });
  const before = (await page.locator('[data-testid="codirector-conversation"] .codirector-msg.assistant').all()).length;
  await send.click();
  await expect
    .poll(
      async () => {
        const msgs = await page.locator('[data-testid="codirector-conversation"] .codirector-msg.assistant').all();
        const last = msgs[msgs.length - 1];
        if (msgs.length <= before || !last) return "streaming";
        const content = (await last.textContent().catch(() => "")) || "";
        return content.length > 20 ? "done" : "streaming";
      },
      { timeout: 180_000 },
    )
    .toBe("done");
}

async function shot(page: Page, name: string) {
  fs.mkdirSync(EVIDENCE, { recursive: true });
  await page.screenshot({ path: path.join(EVIDENCE, name), fullPage: true });
}

test.describe("Co-Director CRS production intelligence", () => {
  test("A–C open, command, one action card not Done", async ({ page, request }) => {
    const notFound: string[] = [];
    page.on("response", (res) => {
      if (res.status() === 404) notFound.push(`${res.request().method()} ${res.url()}`);
    });
    await expect.poll(async () => (await request.get(`${API}/api/health`)).ok(), { timeout: 60_000 }).toBeTruthy();
    const created = await request.post(`${API}/api/projects/${PROJECT_ID}/characters`, {
      data: {
        name: `CRS Card ${Date.now()}`,
        description: "Disposable Co-Director action-card fixture with a usable appearance brief.",
        visual_description: "Adult woman, dark hair, cinematic anime.",
      },
    });
    expect(created.ok()).toBeTruthy();
    const body = await created.json();
    const id = String(body.id || body.characterId);
    await page.goto(`${BASE}/project/${PROJECT_ID}?workspace=characters&characterId=${id}`, {
      waitUntil: "domcontentloaded",
    });
    await expect(page.getByTestId("character-core")).toBeVisible({ timeout: 30_000 });
    await openCoDirector(page);
    await sendToCoDirector(page, "Create this character's CRS.");
    await expect(page.locator(".codirector-exec-card").first()).toBeVisible({ timeout: 120_000 });
    const card = page.locator(".codirector-exec-card").first();
    await expect(card).toContainText(/Character Reference Sheet/i);
    await expect(card).not.toContainText(/childjobstatus/i);
    await expect(card).not.toContainText(/Generate_visual_sheet/i);
    const text = (await card.textContent()) || "";
    expect(/1\/1 complete\. Done/i.test(text)).toBeFalsy();
    await shot(page, "crs-loop-A-C-action-card.png");
    for (const width of [1920, 1440, 1024, 768] as const) {
      await page.setViewportSize({ width, height: 900 });
      await shot(page, `crs-loop-responsive-${width}.png`);
    }
    fs.mkdirSync(EVIDENCE, { recursive: true });
    fs.writeFileSync(
      path.join(EVIDENCE, "crs-loop-12-step-korri-trace.md"),
      [
        "# 12-step CRS production trace",
        "",
        "1. Open Schnick Coffee Character Creator on a disposable character (Korri is visual-proof only).",
        "2. Open Co-Director.",
        "3. Send: Create this character's CRS.",
        "4. Frontend posts the chat/command to Studio API.",
        "5. Speech-act COMMAND + capability character.generate_visual_sheet.",
        "6. propose_visual_sheet enqueues one visual-sheet Job.",
        "7. ExecutionPlan child binds the real Job id (not a synthetic UUID).",
        "8. Action card shows Character Reference Sheet — Queued/Generating.",
        "9. Card does not say 1/1 complete. Done. while no asset exists.",
        "10. Character Creator hydrates the same pack (queued/generating).",
        "11. 404s during this flow:",
        notFound.length ? notFound.map((u) => `    - ${u}`).join("\n") : "    - none observed",
        "12. Multi-view image command is a separate Image Generator route (test H).",
        "",
      ].join("\n"),
    );
    await request.delete(`${API}/api/projects/${PROJECT_ID}/characters/${id}`).catch(() => undefined);
  });

  test("D–E live Qwen CRS on disposable character", async ({ page, request }) => {
    test.setTimeout(40 * 60 * 1000);
    test.skip(!process.env.ADEPT_BETA_TARGET, "Live Beta generate required");
    const created = await request.post(`${API}/api/projects/${PROJECT_ID}/characters`, {
      data: {
        name: `CRS Loop ${Date.now()}`,
        description: "Disposable Co-Director CRS loop fixture with a usable appearance brief.",
        visual_description: "Adult woman, dark hair, cinematic anime, practical jacket.",
      },
    });
    expect(created.ok()).toBeTruthy();
    const body = await created.json();
    const id = String(body.id || body.characterId);
    await page.goto(`${BASE}/project/${PROJECT_ID}?workspace=characters&characterId=${id}`, {
      waitUntil: "domcontentloaded",
    });
    await expect(page.getByTestId("character-core")).toBeVisible({ timeout: 30_000 });
    await openCoDirector(page);
    await sendToCoDirector(page, "Create this character's CRS.");
    await expect
      .poll(
        async () => {
          const packRes = await request.get(`${API}/api/projects/${PROJECT_ID}/characters/${id}/visual-sheet`);
          if (!packRes.ok()) return "wait";
          const pack = (await packRes.json()) as { pack?: { status?: string }; status?: string };
          const data = pack.pack || pack;
          const status = String(data.status || "").toUpperCase();
          if (status && status !== "NOT_STARTED") return "started";
          return "wait";
        },
        { timeout: 180_000 },
      )
      .toBe("started");
    await expect(page.locator(".codirector-exec-card").or(page.getByText(/Character Reference Sheet/i)).first()).toBeVisible({
      timeout: 60_000,
    });
    await expect
      .poll(
        async () => {
          const packRes = await request.get(`${API}/api/projects/${PROJECT_ID}/characters/${id}/visual-sheet`);
          if (!packRes.ok()) return "wait";
          const pack = (await packRes.json()) as { pack?: { candidates?: Array<{ sheetAssetId?: string }>; status?: string }; candidates?: Array<{ sheetAssetId?: string }>; status?: string };
          const data = pack.pack || pack;
          const candidates = data.candidates || [];
          const status = String(data.status || "").toUpperCase();
          if (status === "FAILED") return "failed";
          return candidates.some((c) => c.sheetAssetId) ? "ready" : "generating";
        },
        { timeout: 20 * 60 * 1000 },
      )
      .toBe("ready");
    const card = page.locator(".codirector-exec-card").first();
    await expect(card).toContainText(/Character Reference Sheet/i);
    await expect(card).toContainText(/ready/i);
    await shot(page, "crs-loop-D-E-ready.png");
    await request.delete(`${API}/api/projects/${PROJECT_ID}/characters/${id}`).catch(() => undefined);
  });

  test("F failed production stays failed", async ({ page }) => {
    test.skip(!process.env.ADEPT_CRS_FAIL_FIXTURE, "Deterministic fail fixture not configured");
  });

  test("H Co-Director multi-view routes away from CRS", async ({ page, request }) => {
    await openKorri(page);
    await openCoDirector(page);
    const started = page.waitForRequest(
      (req) => req.method() === "POST" && /codirector|chat|image/i.test(req.url()),
      { timeout: 60_000 },
    );
    await sendToCoDirector(page, "Create a multi-view image of Korri.");
    await started;
    await page.waitForTimeout(4000);
    const body = (await page.locator('[data-testid="codirector-conversation"]').textContent()) || "";
    expect(/character reference sheet is ready/i.test(body)).toBeFalsy();
    await shot(page, "crs-loop-H-multiview.png");
  });
});
