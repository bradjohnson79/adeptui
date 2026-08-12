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
  expect(seed.ok(), `seed-korri failed: ${seed.status()} ${await seed.text()}`).toBeTruthy();
  const korri = await seed.json();
  const characterId = String(korri.id);
  expect(characterId).toBeTruthy();

  return { projectId, characterId };
}

export async function openCharacterVoice(page: Page, projectId: string): Promise<void> {
  await page.goto(`/project/${projectId}?workspace=characters`);
  await expect(page.getByTestId("character-profile-workspace")).toBeVisible({ timeout: 45_000 });
  const select = page.getByTestId("character-select");
  await expect(select).toBeVisible();

  await expect
    .poll(async () => {
      let value = await findKorriOptionValue(page);
      if (!value) {
        const seed = page.getByRole("button", { name: /Seed Korri/i });
        if ((await seed.count()) > 0) await seed.click();
        value = await findKorriOptionValue(page);
      }
      return value;
    }, { timeout: 45_000 })
    .toBeTruthy();

  const korriValue = await findKorriOptionValue(page);
  expect(korriValue, "Korri must appear in character-select after seed").toBeTruthy();
  await select.selectOption(korriValue);
  await page.getByTestId("character-tabs").getByRole("button", { name: "Voice Studio", exact: true }).click();
  await expect(page.getByTestId("voice-creator-workspace")).toBeVisible({ timeout: 30_000 });
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
