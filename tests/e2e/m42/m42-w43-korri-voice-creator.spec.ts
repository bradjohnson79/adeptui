import { expect, test } from "@playwright/test";
import { ensureKorriCharacter, openCharacterVoice } from "./helpers/korriVoice";

test.describe("M42 W43 Korri Voice Creator", () => {
  test("Scenario A — Voice Creator workspace replaces form-only panel", async ({ page, request }) => {
    const { projectId } = await ensureKorriCharacter(request);
    await openCharacterVoice(page, projectId);
    await expect(page.getByTestId("voice-creator-workspace")).toBeVisible();
    await expect(page.getByTestId("voice-method-cards")).toBeVisible();
    await expect(page.getByTestId("voice-personality-section")).toBeVisible();
    await expect(page.getByTestId("voice-no-fake-waveform")).toBeVisible();
    await expect(page.getByTestId("voice-ask-codirector")).toBeVisible();
    await expect(page.getByTestId("voice-design-prompt")).toHaveCount(0);
    await expect(page.getByTestId("voice-ref-path")).toHaveCount(0);
    await expect(page.getByTestId("voice-consent-reject")).toHaveCount(0);
  });

  test("Scenario B — Design brief preview grounded (no warm mid baritone)", async ({ page, request }) => {
    const { projectId } = await ensureKorriCharacter(request);
    await openCharacterVoice(page, projectId);
    await page.getByTestId("voice-method-DESIGN").click();
    await expect(page.getByTestId("voice-design-brief")).toBeVisible();
    const age = page.getByTestId("voice-brief-perceivedAge");
    if ((await age.count()) > 0) {
      await expect(age).not.toHaveValue(/baritone/i);
    }
    await page.getByTestId("voice-design-preview").click();
    const advanced = page.getByTestId("voice-advanced");
    await advanced.locator("summary").click();
    const body = page.getByTestId("voice-design-preview-body");
    await expect(body).toBeVisible({ timeout: 60_000 });
    const text = await body.innerText();
    expect(text.toLowerCase()).not.toContain("warm mid baritone");
    expect(text).toContain("compiledVoiceDescription");
  });

  test("gate exposes Voice Creator flags", async ({ request }) => {
    const res = await request.get("/api/m42-product/gate/wave43");
    expect(res.ok(), "wave43 gate must be reachable").toBeTruthy();
    const body = await res.json();
    expect(body.flags).toHaveProperty("korriVoiceCreatorWorkspaceOperational");
    expect(body.flags).toHaveProperty("korriVoiceNoMockData");
    expect(body.conditionalGoForbidden).toBeTruthy();
  });
});
