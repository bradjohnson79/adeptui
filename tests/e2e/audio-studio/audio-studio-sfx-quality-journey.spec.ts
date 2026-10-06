/**
 * Live Audio Studio SFX journey on Korri Anadriya.
 * Never POST /api/projects. Requires ADEPT_ALLOW_KORRI_MUTATION=1.
 */
import { expect, test, type APIRequestContext } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";
const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";

test.describe("Audio Studio SFX quality journey", () => {
  test.skip(process.env.ADEPT_ALLOW_KORRI_MUTATION !== "1", "Requires ADEPT_ALLOW_KORRI_MUTATION=1");
  test.setTimeout(15 * 60 * 1000);
  test.use({ viewport: { width: 1600, height: 900 } });

  test("footsteps two takes, warm second request, approve, timeline, cancel", async ({ page, request }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(String(err)));
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });

    await page.goto(`/project/${PROJECT_ID}?workspace=audiostudio&audioTab=sfx`);
    const workspace = page.getByTestId("audio-studio-workspace");
    await expect(workspace).toBeVisible({ timeout: 30000 });
    const box = await workspace.boundingBox();
    const viewport = page.viewportSize();
    const mid = (box?.x || 0) + (box?.width || 0) / 2;
    expect(Math.abs(mid - (viewport?.width || 0) / 2)).toBeLessThan(90);

    await page.getByTestId("audio-studio-tab-sfx").click();
    await page.getByTestId("audio-sfx-preset-footsteps").click();
    await page.getByTestId("audio-sfx-prompt").fill("Footsteps on metal grating, mid-distance.");
    await page.getByTestId("audio-sfx-takes").selectOption("2");
    await page.getByTestId("audio-sfx-generate").click();

    const progress = page.getByTestId("audio-generation-progress");
    await expect(progress).toBeVisible({ timeout: 20000 });
    await expect.poll(async () => (await progress.innerText()).toLowerCase(), { timeout: 180000 }).not.toContain(
      "gpu preferred",
    );

    await expect.poll(async () => page.locator('[data-testid^="audio-candidate-player-"]').count(), {
      timeout: 12 * 60 * 1000,
    }).toBeGreaterThanOrEqual(2);

    await expect(page.getByTestId("audio-sfx-generate")).toBeEnabled({ timeout: 120000 });
    const cards = page.locator('[data-testid^="audio-candidate-"]:not([data-testid*="player"])');
    await expect(cards.first()).toBeVisible();
    const selectBtn = cards.first().getByRole("button", { name: /Select/ });
    if (await selectBtn.isEnabled()) {
      await selectBtn.click();
    }
    const approve = cards.first().getByRole("button", { name: /^Approve$/ });
    await expect(approve).toBeEnabled({ timeout: 30000 });
    await approve.click();
    await expect(cards.first().getByRole("button", { name: "Approved" })).toBeVisible({ timeout: 20000 });
    await cards.first().getByRole("button", { name: /Add to Timeline/i }).click();
    await expect(page.getByTestId("audio-studio-status")).toContainText(/SFX|Timeline/i, { timeout: 20000 });

    const warmStarted = Date.now();
    await page.getByTestId("audio-sfx-takes").selectOption("1");
    await page.getByTestId("audio-sfx-generate").click();
    await expect.poll(async () => page.locator('[data-testid^="audio-candidate-player-"]').count(), {
      timeout: 8 * 60 * 1000,
    }).toBeGreaterThanOrEqual(1);
    const warmMs = Date.now() - warmStarted;
    const artifactDir = path.join("artifacts", "audio-studio-quality");
    fs.mkdirSync(artifactDir, { recursive: true });
    fs.writeFileSync(path.join(artifactDir, "playwright-warm-second-request.json"), JSON.stringify({ warmMs }, null, 2));
    expect(warmMs, "warm second request should finish well under a cold reload window").toBeLessThan(8 * 60 * 1000);

    await page.getByTestId("audio-sfx-takes").selectOption("2");
    await page.getByTestId("audio-sfx-generate").click();
    await expect(page.getByTestId("audio-generation-cancel")).toBeVisible({ timeout: 20000 });
    await expect
      .poll(async () => (await progress.innerText()).toLowerCase(), { timeout: 120000 })
      .toMatch(/take 2|generating take/);
    await page.getByTestId("audio-generation-cancel").click();
    await expect.poll(async () => {
      const text = `${await page.getByTestId("audio-studio-status").innerText().catch(() => "")} ${await progress.innerText().catch(() => "")}`;
      return /cancel|stopped/i.test(text);
    }, { timeout: 60000 }).toBeTruthy();

    const leftover = errors.filter((line) => !/favicon|ResizeObserver|fonts\.gstatic|fonts\.googleapis|x-adept-deny-owner-writes|net::ERR/i.test(line));
    expect(leftover, leftover.join("\n")).toEqual([]);

    const batches = await getJson(request, `/api/audio-studio/projects/${PROJECT_ID}/workspace`);
    expect(batches?.mock).toBeFalsy();
  });
});

async function getJson(request: APIRequestContext, pathName: string) {
  const res = await request.get(`${API}${pathName}`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return res.json();
}
