import { test, expect } from "@playwright/test";

/**
 * TIMELINE CHARACTER TAG CANONICALIZATION — E2E smoke.
 *
 * Canonical law: Reference type is metadata. Character identity is the tag.
 * Never encode the reference type into the character's visible @ token.
 *
 * One character = one @tag everywhere:
 *   Library @Addex / @Korri40YearsOld
 *   References @Addex (Character) ✓ / @Korri40YearsOld (Character) ✓
 *   Prompt summary @Korri40YearsOld @Addex
 *   Preflight PASS (no missing CRS warning)
 *   Reload preserves all tags
 */

const PROJECT = "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";
const SCENE = "a4c85c6d-2f0e-4e49-8535-7c698306f398";
const OUT = "C:/AdeptFilmWorks/AIVideoStudio/tests/e2e/screenshots/canonical-character-tags.png";

test("Timeline canonical character @tags — one tag everywhere, no CRS suffix", async ({ page, request }) => {
  // Verify API is accessible first — skip if sandbox blocks localhost
  const apiBase = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
  let apiOk = false;
  try {
    const res = await request.get(`${apiBase}/api/healthz`);
    apiOk = res.ok();
  } catch {
    apiOk = false;
  }
  test.skip(!apiOk, "Studio API not accessible from Playwright sandbox");

  const consoleErrors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });

  await page.goto(`/project/${PROJECT}?workspace=timeline&sceneId=${SCENE}`, {
    waitUntil: "domcontentloaded",
  });

  // Wait for the references pane to load
  const refsList = page.getByTestId("references-list");
  await expect(refsList).toBeVisible({ timeout: 20000 });

  // 1. References must show canonical tags — no CRS suffix
  const addexChip = page.locator('[data-testid^="reference-chip-"]').filter({ hasText: "@Addex" });
  const korriChip = page.locator('[data-testid^="reference-chip-"]').filter({ hasText: "@Korri40YearsOld" });
  await expect(addexChip).toBeVisible({ timeout: 10000 });
  await expect(korriChip).toBeVisible({ timeout: 10000 });

  // 2. The chips must NOT contain "CRS" in the tag portion
  const addexText = await addexChip.textContent();
  const korriText = await korriChip.textContent();
  expect(addexText).toContain("@Addex");
  expect(addexText).not.toContain("@AddexCRS");
  expect(addexText).not.toMatch(/@Addex\s*CRS/);
  expect(korriText).toContain("@Korri40YearsOld");
  expect(korriText).not.toContain("@KorriCRS");
  expect(korriText).not.toMatch(/@Korri\s*CRS/);

  // 3. Both must show the (Character) role label with ✓ (approved)
  const addexRole = page.locator('[data-testid^="reference-role-"]').filter({ hasText: "Character" });
  await expect(addexRole).toHaveCount(2, { timeout: 5000 });
  for (const role of await addexRole.all()) {
    const text = await role.textContent();
    expect(text).toContain("Character");
    expect(text).toContain("✓");
  }

  // 4. Prompt summary must show the same canonical tags
  const promptSummary = page.locator('[data-testid^="prompt-token-summary-"]');
  await expect(promptSummary).toBeVisible({ timeout: 10000 });
  const promptText = await promptSummary.first().textContent();
  expect(promptText).toContain("@Korri40YearsOld");
  expect(promptText).toContain("@Addex");
  expect(promptText).not.toContain("CRS");

  // 5. No missing Character Reference Sheet banner
  const bodyText = await page.locator("body").textContent();
  expect(bodyText).not.toMatch(/no Character Reference Sheet/i);
  expect(bodyText).not.toMatch(/has no Character Reference Sheet/i);

  await page.screenshot({ path: OUT, fullPage: true });

  // 6. Reload durability — tags must remain identical
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(refsList).toBeVisible({ timeout: 20000 });

  const addexChip2 = page.locator('[data-testid^="reference-chip-"]').filter({ hasText: "@Addex" });
  const korriChip2 = page.locator('[data-testid^="reference-chip-"]').filter({ hasText: "@Korri40YearsOld" });
  await expect(addexChip2).toBeVisible({ timeout: 10000 });
  await expect(korriChip2).toBeVisible({ timeout: 10000 });

  const addexText2 = await addexChip2.first().textContent();
  const korriText2 = await korriChip2.first().textContent();
  expect(addexText2).toContain("@Addex");
  expect(addexText2).not.toContain("CRS");
  expect(korriText2).toContain("@Korri40YearsOld");
  expect(korriText2).not.toContain("CRS");

  const promptSummary2 = page.locator('[data-testid^="prompt-token-summary-"]');
  await expect(promptSummary2).toBeVisible({ timeout: 10000 });
  const promptText2 = await promptSummary2.first().textContent();
  expect(promptText2).toContain("@Korri40YearsOld");
  expect(promptText2).toContain("@Addex");
  expect(promptText2).not.toContain("CRS");
});
