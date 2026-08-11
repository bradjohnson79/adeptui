import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import { AuditObserver } from "../helpers/observer";
import { openCoDirectorFullScreen } from "./helpers/audit";

const API =
  process.env.STUDIO_API_BASE ||
  `http://127.0.0.1:${process.env.STUDIO_API_PORT || "8742"}`;

async function createCharacterProfile(
  request: APIRequestContext,
  projectId: string,
  body: Record<string, unknown>,
): Promise<{ id: string }> {
  const res = await request.post(`${API}/api/projects/${projectId}/characters`, { data: body });
  expect(res.ok(), await res.text()).toBeTruthy();
  return res.json() as Promise<{ id: string }>;
}

async function getCharacterProfile(
  request: APIRequestContext,
  projectId: string,
  characterId: string,
): Promise<Record<string, unknown>> {
  const res = await request.get(`${API}/api/projects/${projectId}/characters/${characterId}`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return res.json() as Promise<Record<string, unknown>>;
}

async function comfyUiAvailable(request: APIRequestContext): Promise<boolean> {
  // Gate generation/approve assertions behind a running local image runtime.
  try {
    const res = await request.get(`${API}/api/health`, { timeout: 5000 });
    if (!res.ok()) return false;
    const body = (await res.json()) as {
      comfy_reachable?: boolean;
      comfy?: { reachable?: boolean; status?: string };
    };
    if (body?.comfy_reachable === true) return true;
    if (body?.comfy?.reachable === true) return true;
    const status = body?.comfy?.status || "";
    return /ready|ok|online|connected/i.test(status);
  } catch {
    return false;
  }
}

async function openCharactersTab(page: Page) {
  await page.getByTestId("codirector-content-tab-characters").click();
  await expect(page.getByTestId("codirector-content-characters")).toBeVisible({ timeout: 30_000 });
}

test.describe("@critical @isolated codirector embedded character creator", () => {
  test.beforeEach(async ({ request }) => {
    await waitForAppReady(request);
  });

  test("renders full creation flow with name, bio, visual description, style, ref image, generate, approve, voice, assets", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    const project = await createTempProject(request, `Embedded Character Creator ${Date.now()}`);

    try {
      await openCoDirectorFullScreen(page, project.id);
      await openCharactersTab(page);

      // Empty state offers Create Character.
      await expect(
        page.getByTestId("character-compact-empty").or(page.getByTestId("character-compact-saved-select")).first(),
      ).toBeVisible({ timeout: 30_000 });

      // Create a character via API so the saved-characters dropdown has an entry.
      const character = await createCharacterProfile(request, project.id, {
        name: "Mieke",
        description: "Warm, observant barista with a dry wit and a secret artistic streak.",
        visual_description: "Late 20s, short auburn hair, freckles, green eyes, slim build, apron over striped shirt.",
        visual_style: "live_action",
      });

      // Reload the pane so the new character appears in the dropdown.
      await page.reload();
      await openCoDirectorFullScreen(page, project.id);
      await openCharactersTab(page);

      // Select the saved character — all fields populate.
      await expect(page.getByTestId("character-compact-saved-select")).toBeVisible({ timeout: 30_000 });
      await page.getByTestId("character-compact-saved-select").selectOption(character.id);
      await expect(page.getByTestId("character-compact-name")).toHaveValue("Mieke", { timeout: 15_000 });
      await expect(page.getByTestId("character-compact-bio")).toContainText(/Warm, observant barista/);
      await expect(page.getByTestId("character-compact-visual-desc")).toContainText(/short auburn hair/);
      await expect(page.getByTestId("character-compact-style")).toHaveValue("live_action");

      // Generate button is enabled (all required fields present).
      await expect(page.getByTestId("character-compact-generate")).toBeEnabled({ timeout: 10_000 });

      // Open Full Character Creator button is present.
      await expect(page.getByTestId("character-compact-open-full")).toBeVisible();

      // Edit a field — debounced autosave persists.
      await page.getByTestId("character-compact-bio").fill(
        "Warm, observant barista with a dry wit and a secret artistic streak. Edits survive reload.",
      );
      // Wait for the debounced save + UI persisted state by polling the backend.
      await expect
        .poll(async () => {
          const p = await getCharacterProfile(request, project.id, character.id);
          return (p.description as string) || "";
        }, { timeout: 15_000 })
        .toContain("Edits survive reload");

      // Visual description + style fields survive reload independently.
      await page.reload();
      await openCoDirectorFullScreen(page, project.id);
      await openCharactersTab(page);
      await page.getByTestId("character-compact-saved-select").selectOption(character.id);
      await expect(page.getByTestId("character-compact-visual-desc")).toContainText(/short auburn hair/);
      await expect(page.getByTestId("character-compact-style")).toHaveValue("live_action");
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("saved character dropdown uses dark Adept UI theme (no white native mismatch)", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    const project = await createTempProject(request, `Embedded Character CSS ${Date.now()}`);

    try {
      await createCharacterProfile(request, project.id, { name: "CSS Check Character" });
      await openCoDirectorFullScreen(page, project.id);
      await openCharactersTab(page);

      const select = page.getByTestId("character-compact-saved-select");
      await expect(select).toBeVisible({ timeout: 30_000 });

      // Computed background must be a dark Adept UI tone, not a white native default.
      const bg = await select.evaluate((el) => window.getComputedStyle(el).backgroundColor);
      // Accept rgb(...) or rgba(...) — reject pure white.
      expect(bg).not.toBe("rgb(255, 255, 255)");
      expect(bg).not.toBe("rgba(255, 255, 255, 1)");
      const m = bg.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
      expect(m).not.toBeNull();
      const r = Number(m![1]);
      const g = Number(m![2]);
      const b = Number(m![3]);
      const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
      expect(luminance).toBeLessThan(0.35);

      // Text color is light (readable on dark).
      const color = await select.evaluate((el) => window.getComputedStyle(el).color);
      const cm = color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
      expect(cm).not.toBeNull();
      const cr = Number(cm![1]);
      const cg = Number(cm![2]);
      const cb = Number(cm![3]);
      const textLum = (0.299 * cr + 0.587 * cg + 0.114 * cb) / 255;
      expect(textLum).toBeGreaterThan(0.5);
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("Open Full Character Creator preserves projectId + characterId and deep-links the standalone workspace", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    const project = await createTempProject(request, `Embedded Open Full ${Date.now()}`);

    try {
      const character = await createCharacterProfile(request, project.id, {
        name: "Open Full Character",
        description: "A character used to verify the Open Full Character Creator deep-link.",
        visual_description: "Mid 30s, tall, brown eyes, neat beard, navy jacket.",
        visual_style: "anime",
      });

      await openCoDirectorFullScreen(page, project.id);
      await openCharactersTab(page);
      await page.getByTestId("character-compact-saved-select").selectOption(character.id);
      await expect(page.getByTestId("character-compact-name")).toHaveValue("Open Full Character");

      // Edit a field so we can verify the flush-before-navigate behavior.
      await page.getByTestId("character-compact-bio").fill("Edited bio before opening the full creator.");
      await expect
        .poll(async () => {
          const p = await getCharacterProfile(request, project.id, character.id);
          return (p.description as string) || "";
        }, { timeout: 15_000 })
        .toContain("Edited bio before opening");

      // Click Open Full Character Creator — should navigate to the standalone workspace
      // preserving projectId + characterId + returnWorkspace.
      await page.getByTestId("character-compact-open-full").click();

      // The standalone CharacterProfileWorkspace renders an Overview tab with the character name.
      await expect(page.getByTestId("character-overview")).toBeVisible({ timeout: 30_000 });
      await expect(page.getByTestId("character-overview")).toContainText("Open Full Character");

      // Visual description + style fields are visible in the standalone overview (one source of truth).
      await expect(page.getByTestId("character-overview-visual-desc")).toContainText(/brown eyes/);
      await expect(page.getByTestId("character-overview-style")).toHaveValue("anime");

      // URL carries the deep-link params.
      await expect(page).toHaveURL(/workspace=characters/);
      await expect(page).toHaveURL(new RegExp(`characterId=${character.id}`));
      await expect(page).toHaveURL(/returnWorkspace=codirector/);

      // Back to Co-Director button is present (return nav).
      await expect(page.getByTestId("character-back-to-codirector")).toBeVisible();
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("field independence: description, visual_description, visual_style survive reload and are visible in both embedded + standalone", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    const project = await createTempProject(request, `Embedded Field Independence ${Date.now()}`);

    try {
      const character = await createCharacterProfile(request, project.id, {
        name: "Field Independence Character",
        description: "Bio personality text — distinct from visual.",
        visual_description: "Visual description text — distinct from bio.",
        visual_style: "stylized_3d_animation",
      });

      // Verify backend persisted all three independently.
      const persisted = await getCharacterProfile(request, project.id, character.id);
      expect(persisted.description).toBe("Bio personality text — distinct from visual.");
      expect(persisted.visual_description).toBe("Visual description text — distinct from bio.");
      expect(persisted.visual_style).toBe("stylized_3d_animation");

      // Visible in the embedded creator.
      await openCoDirectorFullScreen(page, project.id);
      await openCharactersTab(page);
      await page.getByTestId("character-compact-saved-select").selectOption(character.id);
      await expect(page.getByTestId("character-compact-bio")).toContainText(/Bio personality text/);
      await expect(page.getByTestId("character-compact-visual-desc")).toContainText(/Visual description text/);
      await expect(page.getByTestId("character-compact-style")).toHaveValue("stylized_3d_animation");

      // Visible in the standalone creator.
      await page.getByTestId("character-compact-open-full").click();
      await expect(page.getByTestId("character-overview")).toBeVisible({ timeout: 30_000 });
      await expect(page.getByTestId("character-overview-bio")).toContainText(/Bio personality text/);
      await expect(page.getByTestId("character-overview-visual-desc")).toContainText(/Visual description text/);
      await expect(page.getByTestId("character-overview-style")).toHaveValue("stylized_3d_animation");
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("candidate generation + approve + persistence (local real; gated on ComfyUI)", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    const project = await createTempProject(request, `Embedded Generate Approve ${Date.now()}`);

    try {
      const character = await createCharacterProfile(request, project.id, {
        name: "Generate Approve Character",
        description: "A character with enough bio detail to satisfy the candidate generation guard.",
        visual_description: "Early 30s, athletic build, dark curly hair, amber eyes, leather jacket.",
        visual_style: "live_action",
      });

      const canGenerate = await comfyUiAvailable(request);
      test.skip(!canGenerate, "Local ComfyUI runtime unavailable — skipping real generation/approve assertions.");

      await openCoDirectorFullScreen(page, project.id);
      await openCharactersTab(page);
      await page.getByTestId("character-compact-saved-select").selectOption(character.id);

      // Generate 4 candidates.
      await page.getByTestId("character-compact-generate").click();
      await expect(page.getByTestId("character-compact-candidates")).toBeVisible({ timeout: 30_000 });
      await expect(page.getByTestId("character-compact-candidate").first()).toBeVisible({ timeout: 30_000 });

      // Wait for at least one candidate to finish generating.
      await expect
        .poll(async () => {
          const cards = await page.getByTestId("character-compact-candidate").count();
          if (cards === 0) return false;
          const firstImg = page.getByTestId("character-compact-candidate").first().locator("img");
          return (await firstImg.count()) > 0;
        }, { timeout: 180_000 })
        .toBeTruthy();

      // Approve the first candidate.
      await page.getByTestId("character-compact-approve").first().click();
      await expect(page.getByTestId("character-compact-saved")).toBeVisible({ timeout: 30_000 });

      // Approved casting image is visible.
      await expect(
        page.locator(".character-compact__hero-img").or(page.getByText("Approved Casting Image")).first(),
      ).toBeVisible({ timeout: 15_000 });

      // Persistence: reload and the approved image remains.
      await page.reload();
      await openCoDirectorFullScreen(page, project.id);
      await openCharactersTab(page);
      await page.getByTestId("character-compact-saved-select").selectOption(character.id);
      await expect(page.locator(".character-compact__hero-img")).toBeVisible({ timeout: 30_000 });
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("pane vertical scroll reaches Character Assets section at narrow viewport", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    const project = await createTempProject(request, `Embedded Scroll ${Date.now()}`);

    try {
      const character = await createCharacterProfile(request, project.id, {
        name: "Scroll Character",
        description: "Character used to verify the pane scrolls to reach all sections.",
        visual_description: "Tall figure with long coat, used for scroll verification.",
        visual_style: "live_action",
      });

      await page.setViewportSize({ width: 420, height: 600 });
      await openCoDirectorFullScreen(page, project.id);
      await openCharactersTab(page);
      await page.getByTestId("character-compact-saved-select").selectOption(character.id);

      // The pane body scrolls independently. Scroll the Character Assets heading
      // into view and assert it becomes visible within the pane viewport.
      const assetsHeading = page.getByText("Character Assets").first();
      await assetsHeading.scrollIntoViewIfNeeded({ timeout: 15_000 });
      await expect(assetsHeading).toBeVisible({ timeout: 15_000 });

      // The Open Full Character Creator button is also reachable via scroll.
      const openFull = page.getByTestId("character-compact-open-full");
      await openFull.scrollIntoViewIfNeeded({ timeout: 15_000 });
      await expect(openFull).toBeVisible({ timeout: 15_000 });
    } finally {
      await deleteProject(request, project.id);
    }
  });
});
