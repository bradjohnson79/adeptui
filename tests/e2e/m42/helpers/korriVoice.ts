import { expect, type APIRequestContext, type Page } from "@playwright/test";

export const STABLE_PROJECT_NAME = process.env.ADEPT_KORRI_PROJECT_NAME || "Korri Character Production";
export const VOICE_SAMPLE = process.env.ADEPT_KORRI_VOICE_SAMPLE || "voice/Korri_Voice_Sample.mp3";

type ProjectList = { id?: string; name?: string }[] | { items?: { id?: string; name?: string }[]; projects?: { id?: string; name?: string }[] };

function asProjects(body: ProjectList): { id: string; name: string }[] {
  const raw = Array.isArray(body) ? body : body.items || body.projects || [];
  return raw
    .filter((p): p is { id: string; name: string } => Boolean(p?.id && p?.name))
    .map((p) => ({ id: String(p.id), name: String(p.name) }));
}

async function findKorriOptionValue(page: Page): Promise<string> {
  const select = page.getByTestId("character-select");
  const options = select.locator("option");
  const count = await options.count();
  for (let i = 0; i < count; i++) {
    const label = ((await options.nth(i).textContent()) || "").toLowerCase();
    const value = await options.nth(i).getAttribute("value");
    if (value && label.includes("korri")) return value;
  }
  return "";
}

/** Resolve or create the stable Korri project and seed Korri. Fail closed — no soft skips. */
export async function ensureKorriCharacter(request: APIRequestContext): Promise<{
  projectId: string;
  characterId: string;
}> {
  const providers = await request.get("/api/character-voice/providers");
  expect(providers.ok(), "character-voice providers must be reachable").toBeTruthy();
  const prov = await providers.json();
  expect(prov?.kokoro?.stub, "kokoro must not be stub").not.toBe(true);
  expect(prov?.qwenVoiceDesign?.ready, "qwenVoiceDesign must be ready (no mock)").toBeTruthy();
  expect(prov?.qwenVoiceClone?.ready, "qwenVoiceClone must be ready (no mock)").toBeTruthy();

  const envId = (process.env.ADEPT_PROJECT_ID || "").trim();
  const listed = await request.get("/api/projects");
  expect(listed.ok(), "GET /api/projects failed").toBeTruthy();
  const projects = asProjects(await listed.json());

  let projectId = envId;
  if (projectId) {
    expect(
      projects.some((p) => p.id === projectId),
      `ADEPT_PROJECT_ID=${projectId} not found`,
    ).toBeTruthy();
  } else {
    const existing = projects.find((p) => p.name === STABLE_PROJECT_NAME);
    if (existing) {
      projectId = existing.id;
    } else {
      const created = await request.post("/api/projects", {
        data: { name: STABLE_PROJECT_NAME },
      });
      expect(created.ok(), `create project failed: ${created.status()}`).toBeTruthy();
      const body = await created.json();
      projectId = String(body.id || body.projectId);
      expect(projectId).toBeTruthy();
    }
  }

  const seed = await request.post(`/api/projects/${projectId}/characters/seed-korri`, { data: {} });
  if (seed.ok()) {
    const korri = await seed.json();
    const characterId = String(korri.id);
    expect(characterId).toBeTruthy();
    return { projectId, characterId };
  }
  // Korri already exists as a Global Character: reuse the existing profile
  // instead of failing the fixture (global scope makes it visible here).
  const seedBody = await seed.json().catch(() => null);
  const existingId = String(seedBody?.detail?.existingId || seedBody?.detail?.details?.existingId || "");
  expect(
    seed.status() === 409 && existingId,
    `seed-korri failed: ${seed.status()} ${JSON.stringify(seedBody)}`,
  ).toBeTruthy();
  return { projectId, characterId: existingId };
}

export async function openCharacterVoice(page: Page, projectId: string): Promise<void> {
  // Canonical creator path: the Voice Studio workspace owns character voice work.
  // Character Creator's "Voice Studio" button navigates here; the shell selects
  // the character from the URL or the chooser grid.
  await page.goto(`/project/${projectId}?workspace=voicestudio`);
  await expect(page.getByTestId("voice-studio-shell")).toBeVisible({ timeout: 45_000 });

  const activeName = page.getByTestId("voice-studio-active-name");
  const workspace = page.getByTestId("voice-creator-workspace");
  const korriCard = page.locator('[data-testid="voice-studio-open-character"][data-character-name="Korri"]');

  // The shell settles into one of two states after load: it auto-restores the
  // remembered character workspace, or it shows the chooser grid. Wait for
  // either settled state before deciding — otherwise a restore that lands
  // while we wait for the chooser leaves us waiting on a card that never
  // renders (and vice versa).
  await expect(workspace.or(korriCard.first())).toBeVisible({ timeout: 60_000 });

  const currentName = ((await activeName.textContent().catch(() => "")) || "").trim();
  if (currentName !== "Korri") {
    if (await workspace.isVisible().catch(() => false)) {
      await page.getByTestId("voice-studio-choose-another").click();
    }
    await expect(korriCard).toBeVisible({ timeout: 45_000 });
    await korriCard.click();
  }
  await expect(workspace).toBeVisible({ timeout: 30_000 });
  await expect(activeName).toHaveText("Korri", { timeout: 30_000 });
}

export async function openVoicePerformance(page: Page): Promise<void> {
  const openVp = page.getByTestId("open-voice-performance");
  if ((await openVp.count()) > 0) {
    await openVp.evaluate((el: HTMLElement) => el.click());
  } else {
    await page.getByTestId("character-tabs").getByRole("button", { name: "Voice Studio", exact: true }).click();
    await page.getByTestId("open-voice-performance").evaluate((el: HTMLElement) => el.click());
  }
  await expect(page.getByTestId("character-voice")).toBeVisible({ timeout: 30_000 });
  const vp = page.getByTestId("voice-performance-workspace");
  if ((await vp.count()) === 0) {
    await page.getByTestId("open-voice-performance").evaluate((el: HTMLElement) => el.click());
  }
  await expect(page.getByTestId("voice-performance-workspace").or(page.getByTestId("character-voice"))).toBeVisible({
    timeout: 30_000,
  });
}

export async function openVoiceStudio(page: Page, projectId: string): Promise<void> {
  await openCharacterVoice(page, projectId);
  await expect(page.getByTestId("character-voice")).toBeVisible();
  await expect(page.getByTestId("voice-studio-readiness")).toBeVisible();
}

export function assertNoMockFlag(text: string): void {
  expect(text.toLowerCase()).toMatch(/mock\s*=\s*false/);
  expect(text.toLowerCase()).not.toMatch(/mock\s*=\s*true/);
}
