import { expect, test } from "@playwright/test";
import { ensureKorriCharacter, openCharacterVoice, openVoicePerformance } from "./helpers/korriVoice";

test.describe("M42 W44 Voice Performance System", () => {
  test("gate exposes binary voicePerformanceGo (no Conditional GO)", async ({ request }) => {
    const res = await request.get("/api/voice-performance/gate/wave44");
    expect(res.ok(), "wave44 gate must be reachable").toBeTruthy();
    const body = await res.json();
    expect(body.binaryOnly).toBeTruthy();
    expect(body.conditionalGoForbidden).toBeTruthy();
    expect(body).toHaveProperty("voicePerformanceGo");
    expect(body.flags).toHaveProperty("performanceMarkupOperational");
    expect(body.flags).toHaveProperty("providerCapabilityHonestyOperational");
    expect(body.flags).toHaveProperty("korriVoicePerformanceCertificationPassed");
    expect(body.mock).not.toBe(true);
  });

  test("tag registry and providers are closed/honest", async ({ request }) => {
    const tags = await request.get("/api/voice-performance/tags");
    expect(tags.ok()).toBeTruthy();
    const t = await tags.json();
    expect(t.mock).not.toBe(true);
    expect((t.tags || []).length).toBeGreaterThan(5);
    expect(t.blockedKeys || []).toEqual(expect.arrayContaining(["provider_instruction"]));

    const providers = await request.get("/api/voice-performance/providers");
    expect(providers.ok()).toBeTruthy();
    const p = await providers.json();
    expect(p.mock).not.toBe(true);
    const qwen = (p.providers || []).find((x: { provider_key?: string }) => x.provider_key === "qwen3-tts");
    expect(qwen).toBeTruthy();
    expect(qwen.supports_emotion_tags).toBeFalsy();
  });

  test("Scenario A/B — Voice Performance workspace from Character Profile", async ({ page, request }) => {
    const { projectId } = await ensureKorriCharacter(request);
    await openCharacterVoice(page, projectId);
    await openVoicePerformance(page);
    await expect(page.getByTestId("voice-performance-workspace")).toBeVisible();
    await expect(page.getByTestId("voice-performance-readiness")).toBeVisible();
    const readyText = await page.getByTestId("voice-performance-readiness").innerText();
    expect(readyText.toLowerCase()).toContain("mock=false");

    await expect(page.getByTestId("vp-step-dialogue")).toBeVisible();
    await expect(page.getByTestId("vp-step-performance")).toBeVisible();
    await page.getByTestId("vp-dialogue-text").fill("You planned the whole route again?");
    await page.getByTestId("vp-step-performance").click();
    await page.getByTestId("vp-emotion-card-sarcastic").click();
    await page.getByTestId("vp-apply-tags").click();
    await expect(page.getByTestId("vp-source-text")).toHaveValue(/\[emotion:/);
    await page.getByTestId("vp-parse").click();
    await expect(page.getByTestId("vp-segment-list")).toBeVisible({ timeout: 60_000 });
  });

  test("Scenario D — parse API produces normalized plan (no mock)", async ({ request }) => {
    const { projectId, characterId } = await ensureKorriCharacter(request);
    const res = await request.post("/api/voice-performance/parse", {
      data: {
        projectId,
        characterId,
        sourceText: "KORRI\n[emotion: amused]\nHello.",
      },
    });
    expect(res.ok(), `parse must succeed for real project: ${res.status()}`).toBeTruthy();
    const body = await res.json();
    expect(body.mock).not.toBe(true);
    expect((body.segments || []).length).toBeGreaterThan(0);
  });
});
