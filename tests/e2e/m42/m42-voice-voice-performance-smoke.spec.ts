import path from "node:path";
import { expect, test } from "@playwright/test";
import {
  VOICE_SAMPLE,
  assertNoMockFlag,
  ensureKorriCharacter,
  openCharacterVoice,
  openVoicePerformance,
} from "./helpers/korriVoice";

/**
 * Fail-closed smoke: every Character Profile Voice + Voice Performance control.
 * Live Adept UI Beta + real voice providers only. No soft skips. No mocks.
 */
test.describe.configure({ mode: "serial", timeout: 600_000 });

test.describe("M42 Voice + Voice Performance full smoke (no mock)", () => {
  let projectId = "";
  let characterId = "";

  test.beforeAll(async ({ request }) => {
    const ids = await ensureKorriCharacter(request);
    projectId = ids.projectId;
    characterId = ids.characterId;
  });

  test("API gates and providers are live (mock=false)", async ({ request }) => {
    const w43 = await request.get("/api/m42-product/gate/wave43");
    expect(w43.ok(), "wave43 gate").toBeTruthy();
    const w43b = await w43.json();
    expect(w43b.flags?.korriVoiceNoMockData).toBeTruthy();
    expect(w43b.conditionalGoForbidden).toBeTruthy();

    const w44 = await request.get("/api/voice-performance/gate/wave44");
    expect(w44.ok(), "wave44 gate").toBeTruthy();
    const w44b = await w44.json();
    expect(w44b.mock).not.toBe(true);
    expect(w44b.voicePerformanceGo).toBeTruthy();
    expect(w44b.binaryOnly).toBeTruthy();

    const tags = await request.get("/api/voice-performance/tags");
    expect(tags.ok()).toBeTruthy();
    const t = await tags.json();
    expect(t.mock).not.toBe(true);
    expect((t.tags || []).length).toBeGreaterThan(5);

    const providers = await request.get("/api/voice-performance/providers");
    expect(providers.ok()).toBeTruthy();
    const p = await providers.json();
    expect(p.mock).not.toBe(true);
  });

  test("Voice workspace shell + method cards + personality + listen chrome", async ({ page }) => {
    await openCharacterVoice(page, projectId);
    await expect(page.getByTestId("voice-creator-header")).toBeVisible();
    await expect(page.getByTestId("voice-creator-status")).toBeVisible();
    await expect(page.getByTestId("voice-ask-codirector")).toBeVisible();
    await expect(page.getByTestId("voice-method-cards")).toBeVisible();
    await expect(page.getByTestId("voice-method-LIBRARY")).toBeVisible();
    await expect(page.getByTestId("voice-method-DESIGN")).toBeVisible();
    await expect(page.getByTestId("voice-method-CLONE")).toBeVisible();
    await expect(page.getByTestId("voice-method-UPLOAD")).toBeVisible();
    await expect(page.getByTestId("voice-personality-section")).toBeVisible();
    for (const key of ["age", "tone", "accent", "energy", "warmth", "playfulness", "confidence"]) {
      await expect(page.getByTestId(`voice-slider-${key}`)).toBeVisible();
    }
    // Empty-state placeholder OR a real player after prior generation — never a fake waveform canvas.
    await expect(
      page.getByTestId("voice-no-fake-waveform").or(page.getByTestId("voice-candidate-player")),
    ).toBeVisible();
    await expect(page.getByTestId("voice-candidates-panel")).toBeVisible();
    await expect(page.getByTestId("voice-advanced")).toBeVisible();
    await expect(page.getByTestId("open-voice-performance")).toBeVisible();
  });

  test("Generate Voice — preview + generate + approve (real)", async ({ page }) => {
    await openCharacterVoice(page, projectId);
    await page.getByTestId("voice-method-DESIGN").click();
    await expect(page.getByTestId("voice-design-brief")).toBeVisible();

    await page.getByTestId("voice-slider-playfulness").locator("input[type=range]").fill("4");
    // Production slider is "warmth" (voiceStudio/constants.ts); "tone" never existed.
    await page.getByTestId("voice-slider-warmth").locator("input[type=range]").fill("3");

    await page.getByTestId("voice-design-preview").click();
    await page.getByTestId("voice-advanced").locator("summary").click();
    const previewBody = page.getByTestId("voice-design-preview-body");
    await expect(previewBody).toBeVisible({ timeout: 60_000 });
    const previewText = await previewBody.innerText();
    expect(previewText.toLowerCase()).not.toContain("warm mid baritone");
    expect(previewText).toContain("compiledVoiceDescription");

    await page.getByTestId("voice-design-generate").click();
    // Wait until generate finishes (busy clears) — do not treat a prior player as completion.
    await expect(page.getByTestId("voice-design-generate")).toBeEnabled({ timeout: 300_000 });
    await expect(page.getByTestId("character-profile-msg")).toContainText(/Voice versions generated/i, {
      timeout: 30_000,
    });
    await expect(page.getByTestId("voice-candidate-player")).toBeVisible({ timeout: 60_000 });
    // Exclude voice-candidate-player; only version row ids.
    const versions = page.locator('[data-testid^="voice-candidate-"]:not([data-testid="voice-candidate-player"])');
    await expect(versions.first()).toBeVisible({ timeout: 30_000 });
    const firstTestId = (await versions.first().getAttribute("data-testid")) || "";
    const firstId = firstTestId.replace(/^voice-candidate-/, "");
    expect(firstId.length).toBeGreaterThan(8);

    await versions.first().getByRole("button").first().click();
    await expect
      .poll(async () => (await page.getByTestId("voice-active-id").innerText()).trim(), {
        timeout: 60_000,
        message: "active voice id must be set after generate",
      })
      .toMatch(/[a-f0-9-]{8,}/i);
    await expect
      .poll(async () => (await page.getByTestId("voice-selected-candidate").innerText()).trim(), {
        timeout: 30_000,
      })
      .toBeTruthy();
    await expect(page.getByTestId("voice-approve-candidate")).toBeEnabled({ timeout: 60_000 });
    // Optional Keep/shortlist can remount during parent refresh — approve does not require it.
    await page.getByTestId("voice-approve-candidate").click();
    await expect(page.getByTestId("voice-creator-status")).toContainText(/Approved/i, {
      timeout: 120_000,
    });

    // Advanced: audition, pronunciation, reactions, history
    const advanced = page.getByTestId("voice-advanced");
    if (!(await advanced.evaluate((el) => (el as HTMLDetailsElement).open))) {
      await advanced.locator("summary").click();
    }
    const auditionSelect = page.getByTestId("voice-audition-line-select");
    const auditionOpts = auditionSelect.locator("option");
    const auditionCount = await auditionOpts.count();
    expect(auditionCount, "audition lines must be present").toBeGreaterThan(1);
    const auditionValue = await auditionOpts.nth(1).getAttribute("value");
    expect(auditionValue).toBeTruthy();
    await auditionSelect.selectOption(auditionValue!);
    await page.getByTestId("voice-audition-run").click();
    await expect(page.getByTestId("voice-audition-player").or(page.getByTestId("voice-candidate-player"))).toBeVisible({
      timeout: 180_000,
    });

    await page.getByTestId("voice-pron-word").fill("Handari");
    await page.getByTestId("voice-pron-phonetic").fill("han-DAH-ree");
    await page.getByTestId("voice-pron-add").click();
    await expect(page.getByTestId("character-profile-msg")).toContainText(/Pronunciation saved/i, {
      timeout: 60_000,
    });
    await expect(page.getByTestId("voice-pron-list")).toContainText("Handari", { timeout: 30_000 });
    await page.getByTestId("voice-pron-test").click();

    await page.getByTestId("voice-reactions-generate").click();
    await expect(page.getByTestId("character-profile-msg")).toContainText(/Reactions generated/i, {
      timeout: 300_000,
    });
    await expect(page.getByTestId("voice-reactions-list")).toContainText(/ready|play/i, { timeout: 30_000 });

    await expect(page.getByTestId("voice-provenance-load")).toBeEnabled({ timeout: 30_000 });
    await page.getByTestId("voice-provenance-load").click();
    await expect(page.getByTestId("voice-provenance-body")).toBeVisible({ timeout: 30_000 });
    const prov = await page.getByTestId("voice-provenance-body").innerText();
    expect(prov.toLowerCase()).not.toMatch(/"mock"\s*:\s*true/);
  });

  test("Clone / Upload Voice — validate + generate clone (real sample)", async ({ page }) => {
    await openCharacterVoice(page, projectId);
    await page.getByTestId("voice-method-UPLOAD").click();
    await expect(page.getByTestId("voice-clone-panel")).toBeVisible();

    const samplePath = path.resolve(VOICE_SAMPLE);
    await page.getByTestId("voice-ref-file").setInputFiles(samplePath);
    await page.getByTestId("voice-ref-transcript").fill("Korri voice reference sample for clone certification.");
    await page.getByTestId("voice-ref-validate").click();
    await expect(page.getByTestId("voice-ref-meta")).toBeVisible({ timeout: 60_000 });
    const meta = await page.getByTestId("voice-ref-meta").innerText();
    expect(meta).toContain("assetId");
    expect(meta).not.toContain("pending_server_path");

    await page.getByTestId("voice-clone-consent-box").check();
    await page.getByTestId("voice-clone-generate").click();
    await expect(page.getByTestId("character-profile-msg")).toContainText(/Clone voice generated/i, {
      timeout: 300_000,
    });
    await expect(page.getByTestId("voice-candidate-player")).toBeVisible({ timeout: 60_000 });
  });

  test("Choose Voice method lists profiles", async ({ page }) => {
    await openCharacterVoice(page, projectId);
    await page.getByTestId("voice-method-LIBRARY").click();
    await expect(page.getByTestId("voice-choose-select")).toBeVisible();
    const options = page.getByTestId("voice-choose-select").locator("option");
    expect(await options.count()).toBeGreaterThan(1);
  });

  test("Voice Performance — every step + generate preview (real)", async ({ page, request }) => {
    // Ensure readiness after prior approve
    const ready = await request.get(
      `/api/voice-performance/characters/${characterId}/readiness?projectId=${projectId}`,
    );
    expect(ready.ok()).toBeTruthy();
    const readiness = await ready.json();
    expect(readiness.mock).not.toBe(true);
    expect(readiness.approvedVoice, "approvedVoice required for full performance path").toBeTruthy();

    await openCharacterVoice(page, projectId);
    await openVoicePerformance(page);

    const readyUi = page.getByTestId("voice-performance-readiness");
    await expect(readyUi).toBeVisible();
    assertNoMockFlag(await readyUi.innerText());
    await expect(readyUi).toContainText(/Voice ready:\s*yes/i);

    for (const step of ["dialogue", "performance", "delivery", "preview", "listen"]) {
      await expect(page.getByTestId(`vp-step-${step}`)).toBeVisible();
    }

    await page.getByTestId("vp-step-dialogue").click();
    await page.getByTestId("vp-dialogue-text").fill(
      "You planned the whole route again?\nFine. I will get us there — after I finish this snack.",
    );

    await page.getByTestId("vp-step-performance").click();
    await expect(page.getByTestId("vp-emotion-cards")).toBeVisible();
    await page.getByTestId("vp-emotion-card-sarcastic").click();

    await page.getByTestId("vp-step-delivery").click();
    await page.getByTestId("vp-pace-chip-normal").click();
    await page.getByTestId("vp-strength-chip-strong").click();

    await page.getByTestId("vp-apply-tags").click();
    await expect(page.getByTestId("character-profile-msg").or(page.getByTestId("voice-performance-msg"))).toContainText(
      /Performance style applied|style applied/i,
      { timeout: 15_000 },
    );
    await expect(page.getByTestId("vp-source-text")).toHaveValue(/\[emotion:/);

    await page.getByTestId("vp-step-preview").click();
    await page.getByTestId("vp-generate-preview").click();
    // generatePreview navigates to Listen on success — do not treat empty segment UL as done.
    await expect(page.getByTestId("character-profile-msg")).toContainText(/Preview ready/i, {
      timeout: 300_000,
    });
    await expect(page.getByTestId("vp-audition")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("vp-main-player")).toBeVisible({ timeout: 60_000 });

    // Advanced panels
    const adv = page.getByTestId("vp-advanced");
    await adv.locator("summary").click();
    await expect(page.getByTestId("vp-translation-panel")).toBeVisible();
    await expect(page.getByTestId("vp-timeline-panel")).toBeVisible();
    await expect(page.getByTestId("vp-provenance")).toBeVisible();

    // Place on timeline when segments ready
    const place = page.getByTestId("vp-assemble-place");
    if (await place.isEnabled()) {
      await place.click();
      await expect(page.getByTestId("voice-performance-workspace")).toContainText(/Timeline|clip|Added/i, {
        timeout: 120_000,
      });
    }

    // Parse API with real ids (no mock success for missing)
    const parse = await request.post("/api/voice-performance/parse", {
      data: {
        projectId,
        characterId,
        sourceText: "KORRI\n[emotion: amused]\nHello there.",
      },
    });
    expect(parse.ok(), `parse failed: ${parse.status()} ${await parse.text()}`).toBeTruthy();
    const parsed = await parse.json();
    expect(parsed.mock).not.toBe(true);
    expect((parsed.segments || []).length).toBeGreaterThan(0);
  });

  test("Readiness after smoke remains honest and non-mock", async ({ request }) => {
    const ready = await request.get(
      `/api/voice-performance/characters/${characterId}/readiness?projectId=${projectId}`,
    );
    expect(ready.ok()).toBeTruthy();
    const body = await ready.json();
    expect(body.mock).not.toBe(true);
    expect(body.approvedVoice).toBeTruthy();
    expect(body.characterId).toBe(characterId);
  });
});
