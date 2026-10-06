import { execFileSync } from "node:child_process";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { openCoDirectorFullScreen } from "../codirector/helpers/audit";
import { assertNotOwnerWriteTarget, studioApiBase } from "../setup/ownerProjectGuard";

const LIVE_PROJECT_ID = "0ffe56e2-0d58-4926-91bf-0f947898d02e";
const LIVE_CHARACTER_ID = "10303eba-ed95-49fe-a86b-e5493b7a1c75";
const CERT_PROJECT_ID = "2bc632b8-b329-4d3b-bc40-b68dc41b6bb1";
const ANGLES = ["side", "three_quarter", "back"] as const;

function seedFixture(mode: "none" | "side" | "two" | "all"): { projectId: string; characterId: string } {
  const script = path.join(__dirname, "seed_approval_gate_fixture.py");
  const py = path.join(process.cwd(), "studio-api", ".venv", "Scripts", "python.exe");
  const raw = execFileSync(py, [script, mode], { encoding: "utf8" }).trim();
  const parsed = JSON.parse(raw.split("\n").filter(Boolean).pop() || "{}") as {
    projectId?: string;
    characterId?: string;
  };
  const projectId = String(parsed.projectId || CERT_PROJECT_ID);
  const characterId = String(parsed.characterId || "");
  assertNotOwnerWriteTarget(projectId, characterId);
  return { projectId, characterId };
}

async function skipOnboarding(page: Page) {
  const skip = page.getByRole("button", { name: "Skip for now" });
  if (await skip.isVisible().catch(() => false)) {
    await skip.click({ force: true }).catch(() => undefined);
  }
}

async function openCharacter(page: Page, projectId: string, characterId: string) {
  await openCoDirectorFullScreen(page, projectId);
  await skipOnboarding(page);
  await page.getByTestId("codirector-content-tab-characters").click();
  await expect(page.getByTestId("codirector-content-characters")).toBeVisible({ timeout: 30_000 });
  await page.getByTestId("character-compact-saved-select").selectOption(characterId);
  await expect(studio(page)).toBeVisible({ timeout: 20_000 });
}

function studio(page: Page) {
  return page.getByTestId("character-compact").getByTestId("cc-v2-studio");
}

async function hitTest(page: Page, testId: string) {
  return page.evaluate((id) => {
    const root = document.querySelector('[data-testid="character-compact"]') || document;
    const el = root.querySelector(`[data-testid="${id}"]`) as HTMLButtonElement | null;
    if (!el) return { found: false, hitIsSelf: false, disabled: true };
    el.scrollIntoView({ block: "center" });
    const r = el.getBoundingClientRect();
    const top = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    return {
      found: true,
      disabled: el.disabled,
      text: (el.textContent || "").trim(),
      hitIsSelf: !!(top && (top === el || el.contains(top))),
    };
  }, testId);
}

async function ccState(request: import("@playwright/test").APIRequestContext, projectId: string, characterId: string) {
  const res = await request.get(`${studioApiBase()}/api/projects/${projectId}/characters/${characterId}/cc-v2`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return res.json() as Promise<{
    sheetGate?: { ready?: boolean; missing?: string[] };
    multiView?: { angles?: Record<string, { approved?: boolean; assetUrl?: string | null }> };
    sheet?: { status?: string; assetId?: string | null };
    multiviewEnrichment?: { status?: string };
  }>;
}

test.describe("Character Creator multiview approval gate", () => {
  test("A/B/C/D fixture + live Save/reload/hit-test/G/H", async ({ page, request }) => {
    test.setTimeout(240_000);
    assertNotOwnerWriteTarget(LIVE_PROJECT_ID, LIVE_CHARACTER_ID);

    const one = seedFixture("side");
    const stateA = await ccState(request, one.projectId, one.characterId);
    expect(stateA.multiView?.angles?.side?.approved).toBeTruthy();
    expect(stateA.multiView?.angles?.three_quarter?.approved).toBeFalsy();
    expect(stateA.multiView?.angles?.back?.approved).toBeFalsy();
    expect(stateA.sheetGate?.ready).toBeFalsy();

    await openCharacter(page, one.projectId, one.characterId);
    await expect(studio(page).getByTestId("cc-v2-compose-sheet")).toBeDisabled();

    await request.post(
      `${studioApiBase()}/api/projects/${one.projectId}/characters/${one.characterId}/multiview/three_quarter/approve`,
      { data: {} },
    );
    const stateB = await ccState(request, one.projectId, one.characterId);
    expect(stateB.multiView?.angles?.side?.approved).toBeTruthy();
    expect(stateB.multiView?.angles?.three_quarter?.approved).toBeTruthy();
    expect(stateB.multiView?.angles?.back?.approved).toBeFalsy();
    expect(stateB.sheetGate?.ready).toBeFalsy();
    await page.reload();
    await openCharacter(page, one.projectId, one.characterId);
    await expect(studio(page).getByTestId("cc-v2-compose-sheet")).toBeDisabled();

    await request.post(
      `${studioApiBase()}/api/projects/${one.projectId}/characters/${one.characterId}/multiview/back/approve`,
      { data: {} },
    );
    const stateC = await ccState(request, one.projectId, one.characterId);
    expect(ANGLES.every((name) => stateC.multiView?.angles?.[name]?.approved)).toBeTruthy();
    expect(stateC.sheetGate?.ready).toBeTruthy();
    await page.reload();
    await openCharacter(page, one.projectId, one.characterId);
    await expect(studio(page).getByTestId("cc-v2-compose-sheet")).toBeEnabled({ timeout: 20_000 });

    page.once("dialog", (dialog) => dialog.accept());
    await studio(page).getByTestId("cc-v2-reject-three_quarter").click();
    await expect.poll(async () => {
      const next = await ccState(request, one.projectId, one.characterId);
      return next.sheetGate?.ready === false && next.multiView?.angles?.side?.approved === true;
    }).toBeTruthy();
    await expect(studio(page).getByTestId("cc-v2-compose-sheet")).toBeDisabled();

    const liveBefore = await ccState(request, LIVE_PROJECT_ID, LIVE_CHARACTER_ID);
    expect(ANGLES.every((name) => liveBefore.multiView?.angles?.[name]?.approved)).toBeTruthy();
    expect(liveBefore.sheetGate?.ready).toBeTruthy();

    await openCharacter(page, LIVE_PROJECT_ID, LIVE_CHARACTER_ID);
    for (const angle of ANGLES) {
      await expect(studio(page).getByTestId(`cc-v2-angle-${angle}`).locator("img")).toBeVisible();
      const hit = await hitTest(page, `cc-v2-approve-${angle}`);
      expect(hit.found).toBeTruthy();
      expect(hit.hitIsSelf).toBeTruthy();
      expect(hit.disabled).toBeTruthy();
      expect(hit.text).toBe("Approved");
    }
    const saveHit = await hitTest(page, "cc-v2-compose-sheet");
    expect(saveHit.found && saveHit.hitIsSelf).toBeTruthy();
    await expect(studio(page).getByTestId("cc-v2-compose-sheet")).toBeEnabled();

    const failed: string[] = [];
    page.on("response", (res) => {
      if (res.url().includes("/multiview/") && res.url().includes("/approve") && res.status() >= 400) {
        failed.push(`${res.status()} ${res.url()}`);
      }
    });
    await studio(page).getByTestId("cc-v2-approve-side").dblclick({ force: true }).catch(() => undefined);
    expect(failed).toEqual([]);

    await studio(page).getByTestId("cc-v2-compose-sheet").click();
    await expect.poll(async () => {
      const next = await ccState(request, LIVE_PROJECT_ID, LIVE_CHARACTER_ID);
      return Boolean(next.sheet?.assetId) && next.sheet?.status === "ready";
    }, { timeout: 180_000 }).toBeTruthy();
    await expect(studio(page).getByTestId("cc-v2-img-sheet")).toBeVisible({ timeout: 30_000 });

    await page.reload();
    await openCharacter(page, LIVE_PROJECT_ID, LIVE_CHARACTER_ID);
    const liveReload = await ccState(request, LIVE_PROJECT_ID, LIVE_CHARACTER_ID);
    expect(ANGLES.every((name) => liveReload.multiView?.angles?.[name]?.approved)).toBeTruthy();
    expect(liveReload.sheet?.assetId).toBeTruthy();
    await expect(studio(page).getByTestId("cc-v2-compose-sheet")).toBeEnabled();

    const remake = await request.post(
      `${studioApiBase()}/api/projects/${one.projectId}/characters/${one.characterId}/multiview/back/regenerate`,
      { data: {} },
    );
    expect(remake.ok() || remake.status() === 409, await remake.text()).toBeTruthy();
    if (remake.ok()) {
      const stateE = await ccState(request, one.projectId, one.characterId);
      expect(stateE.multiView?.angles?.back?.approved).toBeFalsy();
      expect(stateE.multiView?.angles?.side?.approved).toBeTruthy();
      expect(stateE.sheetGate?.ready).toBeFalsy();
    }
  });

  test("UI Approve click persists each angle and unlocks Save without enrich", async ({ page, request }) => {
    test.setTimeout(180_000);
    const fixture = seedFixture("none");
    const before = await ccState(request, fixture.projectId, fixture.characterId);
    for (const name of ANGLES) {
      expect(before.multiView?.angles?.[name]?.approved).toBeFalsy();
    }
    expect(before.sheetGate?.ready).toBeFalsy();
    expect(before.multiviewEnrichment?.status === "ok").toBeFalsy();

    await openCharacter(page, fixture.projectId, fixture.characterId);
    await expect(studio(page).getByTestId("cc-v2-compose-sheet")).toBeDisabled();

    for (const angle of ANGLES) {
      await expect(studio(page).getByTestId(`cc-v2-angle-${angle}`).locator("img")).toBeVisible();
      const hit = await hitTest(page, `cc-v2-approve-${angle}`);
      expect(hit.found && hit.hitIsSelf).toBeTruthy();
      expect(hit.disabled).toBeFalsy();
      expect(hit.text).toBe("Approve");
      await studio(page).getByTestId(`cc-v2-approve-${angle}`).click();
      await expect.poll(async () => {
        const next = await ccState(request, fixture.projectId, fixture.characterId);
        return next.multiView?.angles?.[angle]?.approved === true;
      }).toBeTruthy();
      await expect(studio(page).getByTestId(`cc-v2-approve-${angle}`)).toBeDisabled();
      await expect(studio(page).getByTestId(`cc-v2-approve-${angle}`)).toHaveText("Approved");
    }

    const after = await ccState(request, fixture.projectId, fixture.characterId);
    expect(ANGLES.every((name) => after.multiView?.angles?.[name]?.approved)).toBeTruthy();
    expect(after.sheetGate?.ready).toBeTruthy();
    expect(after.multiviewEnrichment?.status === "ok").toBeFalsy();
    await expect(studio(page).getByTestId("cc-v2-compose-sheet")).toBeEnabled();
  });
});
