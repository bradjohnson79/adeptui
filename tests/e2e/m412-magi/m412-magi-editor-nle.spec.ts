import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

type ProjectSummary = { id?: string; archived?: number };
type RoutedSequence = {
  id: string;
  projectId: string;
  frameRate: number;
  durationFrames: number;
  playheadFrame: number;
  tracks: Array<{ id: string; kind: string; label: string; order: number }>;
  clips: Array<{
    id: string;
    trackId: string;
    assetId: string;
    name?: string;
    startFrame: number;
    durationFrames: number;
    inPoint: number;
    outPoint: number;
  }>;
  markers: Array<{ id: string; frame: number; label: string }>;
  snapEnabled: boolean;
  revision: number;
  updatedAt: string;
  recipeId?: string | null;
};

async function pickProject(request: APIRequestContext): Promise<{ projectId: string } | null> {
  const res = await request.get("/api/projects");
  if (!res.ok()) return null;
  const projects = (await res.json()) as ProjectSummary[] | { projects?: ProjectSummary[] };
  const list = Array.isArray(projects) ? projects : projects.projects || [];
  const existing = list.find((project) => project?.id && !project.archived);
  if (existing?.id) return { projectId: existing.id };
  const createRes = await request.post("/api/projects", { data: { name: `MAGI E2E ${Date.now()}` } });
  if (!createRes.ok()) return null;
  const created = (await createRes.json()) as { id: string };
  return created?.id ? { projectId: created.id } : null;
}

async function mountSequenceRoute(page: Page, projectId: string): Promise<{ clipId: string; state: () => RoutedSequence }> {
  const track = { id: "trk_i1", kind: "image", label: "I1", order: 3 };
  const clipId = `clip_seed_${Date.now()}`;
  let currentSequence: RoutedSequence = {
    id: "seq_test",
    projectId,
    frameRate: 24,
    durationFrames: 24 * 12,
    playheadFrame: 0,
    tracks: [
      { id: "trk_v1", kind: "video", label: "V1", order: 0 },
      { id: "trk_v2", kind: "video", label: "V2", order: 1 },
      { id: "trk_v3", kind: "video", label: "V3", order: 2 },
      track,
      { id: "trk_i2", kind: "image", label: "I2", order: 4 },
      { id: "trk_a1", kind: "audio", label: "A1", order: 5 },
      { id: "trk_a2", kind: "audio", label: "A2", order: 6 },
      { id: "trk_a3", kind: "audio", label: "A3", order: 7 },
      { id: "trk_t1", kind: "text", label: "T1", order: 8 },
      { id: "trk_fx", kind: "fx", label: "FX", order: 9 },
      { id: "trk_m", kind: "mask", label: "M", order: 10 },
      { id: "trk_adj", kind: "adjustment", label: "ADJ", order: 11 },
    ],
    clips: [
      {
        id: clipId,
        trackId: track.id,
        assetId: "magi-seed-asset",
        name: "Seed clip",
        startFrame: 0,
        durationFrames: 24 * 3,
        inPoint: 0,
        outPoint: 24 * 3,
      },
    ],
    markers: [],
    snapEnabled: true,
    revision: 1,
    updatedAt: new Date().toISOString(),
    recipeId: null,
  };
  await page.route(`**/api/magi/projects/${projectId}/sequence`, async (route) => {
    if (route.request().method() === "PUT") {
      const body = route.request().postDataJSON() as { sequence?: RoutedSequence } | RoutedSequence;
      const next = "sequence" in body ? body.sequence : body;
      currentSequence = {
        ...next,
        projectId,
        revision: currentSequence.revision + 1,
        updatedAt: new Date().toISOString(),
      };
      await route.fulfill({ json: { sequence: currentSequence } });
      return;
    }
    await route.fulfill({ json: { sequence: currentSequence } });
  });
  return { clipId, state: () => currentSequence };
}

async function openMagi(page: Page, projectId: string) {
  await page.goto(`/project/${projectId}?workspace=magi`);
  await expect(page.getByTestId("magi-editor")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("magi-focus-root")).toBeVisible();
  await expect(page.getByTestId("magi-sequence-timeline")).toBeVisible();
}

test.describe("M4.12 MAGI Editor NLE", () => {
  test("focus contract blocks keyboard collisions while typing or modal is open", async ({ page, request }) => {
    const picked = await pickProject(request);
    if (!picked) {
      test.skip(true, "No project available for MAGI seed");
      return;
    }
    const seeded = await mountSequenceRoute(page, picked.projectId);
    await openMagi(page, picked.projectId);

    const clip = page.getByTestId(seeded.clipId ? `magi-clip-${seeded.clipId}` : "missing");
    await expect(clip).toBeVisible();
    await clip.click();
    await expect(clip).toBeVisible();

    const frameBeforeTyping = await page.getByTestId("magi-frame-indicator").innerText();
    await page.getByRole("button", { name: /^Command$/i }).click();
    const commandBox = page.locator("[data-accordion-id='command'] textarea");
    await commandBox.click();
    await page.keyboard.type("jkl ");
    await expect(commandBox).toHaveValue(/jkl /);
    await expect(page.getByTestId("magi-focus-root")).toHaveAttribute("data-magi-focus-region", "text_input");
    await expect(page.getByTestId("magi-frame-indicator")).toHaveText(frameBeforeTyping);
    await expect(clip).toBeVisible();

    await page.keyboard.press("Backspace");
    await expect(clip).toBeVisible();

    await page.evaluate(() => {
      const modal = document.createElement("div");
      modal.id = "magi-test-modal";
      modal.setAttribute("role", "dialog");
      modal.setAttribute("aria-modal", "true");
      modal.textContent = "Modal open";
      document.body.appendChild(modal);
    });
    await page.getByTestId("magi-sequence-timeline").click();
    await page.keyboard.press("Delete");
    await expect(clip).toBeVisible();
    await page.evaluate(() => document.getElementById("magi-test-modal")?.remove());

    await clip.click();
    await page.keyboard.press("Delete");
    await expect(clip).toHaveCount(0);
  });

  test("timeline mutations persist playhead and clip state after reload", async ({ page, request }) => {
    const picked = await pickProject(request);
    if (!picked) {
      test.skip(true, "No project available for MAGI seed");
      return;
    }
    const seeded = await mountSequenceRoute(page, picked.projectId);
    await openMagi(page, picked.projectId);

    const clip = page.getByTestId(`magi-clip-${seeded.clipId}`);
    await expect(clip).toBeVisible();
    await clip.click();

    const ruler = page.locator(".magi-sequence-timeline__ruler");
    await ruler.click({ position: { x: 220, y: 12 } });
    await expect(page.getByTestId("magi-frame-indicator")).not.toHaveText("f0");

    const divider = page.getByTestId("timeline-monitor-divider");
    await expect(divider).toBeVisible();
    await divider.focus();
    await page.keyboard.press("End");

    await expect.poll(() => seeded.state().playheadFrame).toBeGreaterThan(0);

    await page.reload();
    await expect(page.getByTestId("magi-editor")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId(`magi-clip-${seeded.clipId}`)).toBeVisible();
    await expect(page.getByTestId("magi-frame-indicator")).not.toHaveText("f0");
  });
});
