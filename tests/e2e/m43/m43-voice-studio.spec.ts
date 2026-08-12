import { expect, test } from "@playwright/test";
import { ensureKorriCharacter, openVoiceStudio } from "../m42/helpers/korriVoice";

/**
 * M43 Voice Studio — unified creator UX certification.
 * Requires live beta + Qwen voice design readiness (same as M42 voice smoke).
 */
test.describe("M43 Voice Studio UX", () => {
  test("unified Voice Studio shell, prefill, methods, and no nested scroll traps", async ({ page, request }) => {
    const { projectId } = await ensureKorriCharacter(request);
    await openVoiceStudio(page, projectId);

    await expect(page.getByTestId("character-tabs").getByRole("button", { name: "Voice Studio" })).toBeVisible();
    await expect(page.getByTestId("character-tabs").getByRole("button", { name: "Voice Performance" })).toHaveCount(0);

    await expect(page.getByTestId("voice-studio-prefill")).toContainText(/traits loaded/i);
    await expect(page.getByTestId("voice-method-cards")).toBeVisible();
    await expect(page.getByTestId("voice-method-DESIGN")).toBeVisible();
    await expect(page.getByTestId("voice-method-LIBRARY")).toBeVisible();
    await expect(page.getByTestId("voice-method-CLONE")).toBeVisible();
    await expect(page.getByTestId("voice-method-UPLOAD")).toBeVisible();

    await expect(page.getByTestId("voice-master-prompt")).toBeVisible();
    await expect(page.getByTestId("voice-design-generate")).toBeVisible();
    await expect(page.getByTestId("voice-ask-codirector")).toBeVisible();
    await expect(page.getByTestId("voice-advanced")).toBeVisible();

    // Upload semantics present
    await page.getByTestId("voice-method-UPLOAD").click();
    await expect(page.getByTestId("voice-upload-kinds")).toBeVisible();
    await expect(page.getByTestId("voice-upload-kinds")).toContainText("Finished dialogue performance");

    // Nested scroll: no overflow:auto traps on main gallery/stack
    const nested = await page.evaluate(() => {
      const root = document.querySelector('[data-testid="voice-creator-workspace"]');
      if (!root) return { ok: false, reason: "missing root" };
      const bad: string[] = [];
      const walk = (el: Element) => {
        const style = window.getComputedStyle(el);
        const oy = style.overflowY;
        if ((oy === "auto" || oy === "scroll") && el.scrollHeight > el.clientHeight + 2) {
          const testid = el.getAttribute("data-testid") || el.className || el.tagName;
          // Advanced details may expand — ignore closed advanced
          if (!el.closest('[data-testid="voice-advanced"]')) bad.push(String(testid));
        }
        for (const c of Array.from(el.children)) walk(c);
      };
      walk(root);
      return { ok: bad.length === 0, bad };
    });
    expect(nested.ok, `nested scrollbars: ${JSON.stringify(nested)}`).toBeTruthy();
  });

  test("generate three voices, select for testing without approve, persist batch + draft", async ({
    page,
    request,
  }) => {
    const { projectId, characterId } = await ensureKorriCharacter(request);
    await openVoiceStudio(page, projectId);

    await page.getByTestId("voice-method-DESIGN").click();
    await page.getByTestId("voice-design-generate").click();

    // Wait for candidates (generation can take a while)
    await expect(page.getByTestId("voice-candidates-panel")).toBeVisible({ timeout: 180_000 });
    const useButtons = page.locator('[data-testid^="voice-use-"]');
    await expect(useButtons.first()).toBeVisible({ timeout: 180_000 });
    const count = await useButtons.count();
    expect(count, "expected up to 3 ready candidates").toBeGreaterThanOrEqual(1);

    await useButtons.first().click();
    await expect(page.getByTestId("voice-studio-selected-card")).toBeVisible();
    await expect(page.getByTestId("voice-studio-selected-card")).toContainText(/testing|Selected/i);

    // Use vs Approve: selecting must not silently approve
    const ws = await request.get(`/api/projects/${projectId}/characters/${characterId}/voice`);
    expect(ws.ok()).toBeTruthy();
    const body = await ws.json();
    expect(body.mock).toBe(false);
    expect(Array.isArray(body.candidateBatches)).toBeTruthy();
    expect(body.candidateBatches.length).toBeGreaterThanOrEqual(1);
    expect(body.voiceStudioDraft?.testingCandidateId || body.testingSelection?.candidateId).toBeTruthy();
    const active = body.activeVoice || body.voices?.find((v: any) => v.id === body.activeVoiceProfileId);
    // Fresh generate drafts should remain unapproved after Select for Testing
    if (active && body.voiceStudioDraft?.testingCandidateId) {
      expect(String(active.approval_status || "").toLowerCase()).not.toBe("approved");
    }

    // Resume: reload preserves draft
    await page.reload();
    await openVoiceStudio(page, projectId);
    await expect(page.getByTestId("voice-studio-selected-card").or(page.getByTestId("voice-candidates-panel"))).toBeVisible({
      timeout: 45_000,
    });
  });

  test("performance wizard + approve path surface", async ({ page, request }) => {
    const { projectId, characterId } = await ensureKorriCharacter(request);
    // Seed a testing selection via API so performance phase can open without a full generate
    const ws = await request.get(`/api/projects/${projectId}/characters/${characterId}/voice`);
    expect(ws.ok()).toBeTruthy();
    const body = await ws.json();
    const voiceId = body.activeVoiceProfileId || body.voices?.[0]?.id;
    const cand =
      body.voices?.flatMap((v: any) => v.candidates || v.lineage?.candidatesMeta || [])?.[0] ||
      null;
    if (voiceId && cand?.id) {
      await request.post(`/api/projects/${projectId}/characters/${characterId}/voice/select-testing`, {
        data: { voiceId, candidateId: cand.id },
      });
    }
    await request.put(`/api/projects/${projectId}/characters/${characterId}/voice/studio-draft`, {
      data: { phase: "performance", testingVoiceProfileId: voiceId, testingCandidateId: cand?.id },
    });

    await openVoiceStudio(page, projectId);
    await page.getByTestId("open-voice-performance").evaluate((el: HTMLElement) => el.click());

    await expect(page.getByTestId("voice-performance-workspace")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("vp-generate-preview")).toBeVisible();
    await expect(page.getByTestId("voice-advanced")).toBeVisible();
    await expect(page.getByTestId("vp-advanced")).toBeAttached();
  });
});
