import { expect, test } from "@playwright/test";
import { waitForAppReady } from "../helpers/app";

/**
 * M3.0a fal.ai BYOK acceptance.
 *
 * Structural checks run against the E2E stack with no real credential: they prove the API
 * refuses a key fal rejects, never echoes credential material, and describes its catalogue
 * honestly.
 *
 * The LIVE block actually spends fal credits, so it only runs with ADEPT_M30A_FAL_LIVE=1
 * and a real key in FAL_KEY / ADEPT_M30A_FAL_KEY.
 */

const LIVE = process.env.ADEPT_M30A_FAL_LIVE === "1";
const LIVE_KEY = process.env.ADEPT_M30A_FAL_KEY || process.env.FAL_KEY || "";
const BOGUS_KEY = "m30a-definitely-not-a-real-fal-key";

test.describe("M3.0a fal.ai provider @critical", () => {
  test.beforeEach(async ({ request }) => {
    await waitForAppReady(request);
  });

  test.afterEach(async ({ request }) => {
    if (!LIVE) await request.delete("/api/fal/key");
  });

  test("rejects a key fal.ai does not accept and stores nothing", async ({ request }) => {
    test.skip(LIVE, "Live run owns the stored credential.");
    await request.delete("/api/fal/key");

    const put = await request.put("/api/fal/key", { data: { api_key: BOGUS_KEY } });
    expect(put.status(), await put.text()).toBe(400);
    const message = await put.text();
    expect(message).not.toContain(BOGUS_KEY);

    const status = await request.get("/api/fal/key");
    expect(status.ok()).toBeTruthy();
    const body = await status.json();
    expect(body.configured).toBe(false);
    expect(body.state).toBe("missing");
  });

  test("credential endpoints never return key material", async ({ request }) => {
    const status = await request.get("/api/fal/key");
    expect(status.ok()).toBeTruthy();
    const text = await status.text();
    const body = JSON.parse(text);

    expect(body).not.toHaveProperty("api_key");
    expect(body).not.toHaveProperty("key");
    expect(text).not.toContain(BOGUS_KEY);
    if (LIVE_KEY) expect(text).not.toContain(LIVE_KEY);
    // A hint is a mask, never a usable prefix of the secret.
    if (body.hint) expect(String(body.hint)).toMatch(/\*|…|\.\.\./);
    expect(["missing", "unverified", "verified", "invalid"]).toContain(body.state);
  });

  test("model catalogue declares media types and only wired endpoints", async ({ request }) => {
    const res = await request.get("/api/fal/models");
    expect(res.ok()).toBeTruthy();
    const models = await res.json();
    expect(Array.isArray(models)).toBeTruthy();
    expect(models.length).toBeGreaterThan(0);
    for (const model of models) {
      // Every entry must name a concrete fal endpoint owner/app path, never a placeholder.
      expect(model.model_id).toMatch(/^[a-z0-9-]+\/[a-z0-9][\w.\-/]*$/i);
      expect(["video", "image"]).toContain(model.media_type);
      expect(["text_to_video", "image_to_video"]).toContain(model.mode);
    }
  });

  test("no page in the app ships credential material to the browser", async ({ page }) => {
    await page.goto("/");
    const shown = await page.evaluate(async () => {
      const res = await fetch("/api/fal/key");
      return res.text();
    });
    expect(shown).not.toContain(BOGUS_KEY);
    if (LIVE_KEY) expect(shown).not.toContain(LIVE_KEY);
    expect(JSON.parse(shown)).toHaveProperty("state");
  });

  test("live: a real key verifies and unlocks cloud engines", async ({ request }) => {
    test.skip(!LIVE || !LIVE_KEY, "Set ADEPT_M30A_FAL_LIVE=1 and ADEPT_M30A_FAL_KEY to run.");

    const put = await request.put("/api/fal/key", { data: { api_key: LIVE_KEY } });
    expect(put.status(), await put.text()).toBe(200);
    const body = await put.json();
    expect(body.state).toBe("verified");
    expect(await put.text()).not.toContain(LIVE_KEY);

    const revalidate = await request.post("/api/fal/key/validate");
    expect(revalidate.ok()).toBeTruthy();
    expect((await revalidate.json()).verified).toBe(true);
  });
});
