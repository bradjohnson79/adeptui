import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const SCHNICK = "2347bf46-3762-4763-86c5-4a6032522278";
const SESSION_ID = "avs-a10ef709c2";

async function openAvatar(page: Page) {
  await page.goto(`/project/${SCHNICK}?workspace=avatar`, {
    waitUntil: "domcontentloaded",
    timeout: 60_000,
  });
  const workspace = page.getByTestId("avatar-studio-workspace");
  const needsCharacter = page.getByTestId("avatar-requires-character");
  await expect(workspace.or(needsCharacter).first()).toBeVisible({ timeout: 60_000 });
  if (await needsCharacter.isVisible().catch(() => false)) {
    const picker = page.getByTestId("avatar-character-select");
    if (await picker.isVisible().catch(() => false)) {
      const options = picker.locator("option");
      const count = await options.count();
      for (let i = 0; i < count; i += 1) {
        const label = (await options.nth(i).textContent()) || "";
        if (/korri/i.test(label)) {
          await picker.selectOption({ index: i });
          break;
        }
      }
    }
  }
  await expect(page.getByTestId("avatar-studio-workspace")).toBeVisible({ timeout: 60_000 });
  const sessionSelect = page.getByTestId("avatar-session-select");
  if (await sessionSelect.isVisible().catch(() => false)) {
    const hasPreferred = await sessionSelect.locator(`option[value="${SESSION_ID}"]`).count();
    if (hasPreferred) {
      await sessionSelect.selectOption(SESSION_ID);
    }
  }
}

test.describe("Avatar Library picker / Character voice / footer — Schnick Coffee", () => {
  test("Library Image picker, Character voice, footer restyle, session persist", async ({
    page,
    request,
  }) => {
    test.setTimeout(180_000);
    await expect
      .poll(async () => {
        try {
          return (await request.get(`${API}/api/health`)).ok();
        } catch {
          return false;
        }
      }, { timeout: 60_000 })
      .toBeTruthy();
    const assetsRes = await request.get(`${API}/api/projects/${SCHNICK}/library`);
    expect(assetsRes.ok(), "Schnick Library assets").toBeTruthy();
    const assetsBody = await assetsRes.json();
    const items = Array.isArray(assetsBody?.items) ? assetsBody.items : [];
    const still = items.find((item: { kind?: string; mime_type?: string; id?: string }) => {
      const hay = `${item.kind || ""} ${item.mime_type || ""}`.toLowerCase();
      return hay.includes("image") && item.id;
    });
    expect(still?.id, "Schnick has at least one Library image").toBeTruthy();

    await openAvatar(page);
    await page.getByTestId("avatar-source-kind").selectOption("library");
    await expect(page.getByTestId("avatar-choose-frame")).toBeVisible({ timeout: 15_000 });
    await page.getByTestId("avatar-choose-frame").click({ force: true });
    const picker = page.getByTestId("avatar-frame-picker");
    await expect(picker).toBeVisible({ timeout: 30_000 });
    await expect(picker.getByText("Choose Avatar Frame")).toBeVisible();
    const grid = page.getByTestId("avatar-frame-picker-grid");
    await expect(grid).toBeVisible({ timeout: 30_000 });
    const template = await grid.evaluate((el) => getComputedStyle(el).gridTemplateColumns);
    expect(template.split(" ").filter(Boolean).length).toBe(3);

    const thumb = grid.locator(`button[data-asset-id="${still.id}"]`).first();
    const fallbackThumb = grid.locator("button.character-compact__asset").first();
    if (await thumb.count()) {
      await thumb.click();
    } else {
      await fallbackThumb.click();
    }
    const selectedId =
      (await grid.locator("button.is-selected").getAttribute("data-asset-id")) || still.id;
    await page.getByTestId("avatar-frame-picker-ok").click();
    await expect(picker).toBeHidden({ timeout: 15_000 });
    await expect(page.getByTestId("avatar-frame-label")).toBeVisible();
    const preview = page.getByTestId("avatar-preview-still");
    await expect(preview).toBeVisible({ timeout: 20_000 });
    await expect(preview).toHaveAttribute("data-asset-id", selectedId);
    await page.waitForTimeout(800);

    const modeKind = page.getByTestId("avatar-mode-kind");
    if (await modeKind.isVisible().catch(() => false)) {
      await modeKind.selectOption("single");
    }
    const speaker = page.getByTestId("avatar-speaker-a");
    const speakerLabelNow = await speaker.locator("option:checked").textContent();
    if (!/korri/i.test(speakerLabelNow || "")) {
      const speakerOptions = speaker.locator("option");
      const speakerCount = await speakerOptions.count();
      for (let i = 0; i < speakerCount; i += 1) {
        const label = (await speakerOptions.nth(i).textContent()) || "";
        if (/korri/i.test(label)) {
          await speaker.selectOption({ index: i });
          break;
        }
      }
    }
    await page.getByTestId("avatar-voice-mode").selectOption("character");
    const missing = page.getByTestId("avatar-character-voice-missing");
    const voiceValue = await page.getByTestId("avatar-voice-mode").inputValue();
    expect(voiceValue).toBe("character");
    if (await missing.isVisible().catch(() => false)) {
      await expect(missing).toContainText("does not have a configured character voice");
      await expect(page.getByRole("button", { name: "Open Voice Studio" }).first()).toBeVisible();
    }
    await page.getByTestId("avatar-save-draft").click();
    await page.waitForTimeout(800);

    const sessionId = await page.getByTestId("avatar-session-select").inputValue();
    const saved = await request.get(`${API}/api/projects/${SCHNICK}/avatar-sessions/${sessionId}`);
    expect(saved.ok()).toBeTruthy();
    const session = await saved.json();
    expect(session.source_kind).toBe("library");
    expect(session.source_still_asset_id).toBe(selectedId);
    expect(session.voice_mode).toBe("character");

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("avatar-studio-workspace")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("avatar-source-kind")).toHaveValue("library");
    await expect(page.getByTestId("avatar-voice-mode")).toHaveValue("character");
    await expect(page.getByTestId("avatar-preview-still")).toHaveAttribute("data-asset-id", selectedId);

    const footerShot = page.getByTestId("avatar-review-tabs");
    await expect(footerShot).toBeVisible();
    await page.screenshot({
      path: "docs/release-gate/avatar/evidence/library-voice-footer-tabs.png",
      fullPage: false,
    });
    await page.locator(".avatar-preview-summary").screenshot({
      path: "docs/release-gate/avatar/evidence/library-voice-footer-summary.png",
    });

    await assertCoDirectorSession(request, sessionId, selectedId);
  });
});

async function assertCoDirectorSession(
  request: APIRequestContext,
  sessionId: string,
  stillId: string,
) {
  const inspect = await request.post(`${API}/api/codirector/projects/${SCHNICK}/tools/read`, {
    data: { toolId: "avatar.inspect", arguments: { sessionId } },
  });
  expect(inspect.ok(), "avatar.inspect").toBeTruthy();
  const inspectBody = await inspect.json();
  const packet = inspectBody?.result?.data || inspectBody?.data || inspectBody;
  expect(packet.sourceKind || packet.source_kind).toBe("library");
  expect(String(packet.sourceAssetId || packet.source_still_asset_id || "")).toBe(stillId);
  expect(String(packet.voiceMode || "")).toBe("character");
}
