/**
 * Video Generator readiness honesty on Jacob.
 * Reuses SenseNova Integration Lab. Never POST /api/projects.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "0ffe56e2-0d58-4926-91bf-0f947898d02e";
const SCENE_ID = "f0b97b96-3456-4ceb-96ce-56bbece7e5b7";

async function waitApiReady(request: APIRequestContext) {
  await expect
    .poll(
      async () => {
        try {
          const res = await request.get(`${API}/api/healthz`, { timeout: 8_000 });
          return res.ok();
        } catch {
          return false;
        }
      },
      { timeout: 90_000 },
    )
    .toBeTruthy();
}

async function openJacobTimeline(page: Page) {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`/project/${PROJECT_ID}?workspace=timeline&scene=${SCENE_ID}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
  const leftToggle = page.getByTestId("timeline-drawer-left-toggle");
  if ((await leftToggle.getAttribute("aria-expanded")) !== "true") {
    await leftToggle.click();
  }
}

test.describe.configure({ mode: "serial", retries: 0 });

test.describe("timeline video generator readiness", () => {
  test("dropdown matches the join; only Ready rows are enabled", async ({ page, request }) => {
    test.setTimeout(180_000);
    await waitApiReady(request);
    const pc = await request.get(`${API}/api/production-control/models?modality=video`, { timeout: 90_000 });
    expect(pc.ok()).toBeTruthy();
    const pcBody = await pc.json();
    const pcModels = ((pcBody.models || []) as Array<{ id: string; readiness?: string; executable?: boolean }>);
    const join = await request.get(`${API}/api/director-timeline/generators`, { timeout: 90_000 });
    expect(join.ok()).toBeTruthy();
    const joinBody = await join.json();
    const gens = ((joinBody.generators || []) as Array<{
      id: string;
      executable?: boolean;
      readiness?: string;
      disabledReason?: string;
    }>).filter((row) => row.id !== "cert-stub-local");

    const ids = gens.map((row) => row.id);
    expect(ids).toContain("ltx-2.5-distilled");
    expect(ids).toContain("ltx-2.5-full");
    expect(ids).toContain("minimax-h3");
    expect(ids).toContain("minimax-h3-i2v-local");
    expect(ids).not.toContain("minimax-h3-t2v-local");
    expect(ids.filter((id) => id === "kling-kie").length).toBeLessThanOrEqual(1);

    // Retired local generators must not be listed.
    for (const retired of ["ltx-local", "wan-local", "hunyuan-video-1.5-local", "hunyuan-video-13b-local"]) {
      expect(ids).not.toContain(retired);
    }

    for (const row of gens) {
      if (row.executable) {
        expect(row.readiness, `${row.id} executable without Ready`).toBe("Ready");
      } else {
        expect(row.readiness, `${row.id} missing readiness`).toBeTruthy();
        expect(row.readiness).not.toBe("Ready");
      }
    }
    const ltx25 = gens.find((row) => row.id === "ltx-2.5-full");
    expect(ltx25?.executable).toBeFalsy();
    const seedanceKie = gens.find((row) => row.id === "seedance-kie");
    if (seedanceKie) {
      expect(seedanceKie.executable).toBeFalsy();
      expect(String(seedanceKie.disabledReason || "")).not.toMatch(/fal\.ai/i);
    }

    await openJacobTimeline(page);
    const select = page.getByTestId("timeline-video-generator-select");
    await expect(select).toBeVisible({ timeout: 60_000 });
    await expect
      .poll(async () => select.locator('option[value="ltx-2.5-distilled"]').count(), { timeout: 45_000 })
      .toBeGreaterThan(0);
    const optionState = await select.locator("option").evaluateAll((opts) =>
      opts
        .map((opt) => {
          const el = opt as HTMLOptionElement;
          return { value: el.value, disabled: el.disabled, label: el.textContent || "" };
        })
        .filter((row) => row.value),
    );
    const optionIds = optionState.map((row) => row.value);
    for (const id of ids) {
      expect(optionIds, `dropdown missing ${id}`).toContain(id);
    }
    for (const row of optionState) {
      const gen = gens.find((item) => item.id === row.value);
      if (!gen) continue;
      expect(row.disabled, `${row.value} enabled state`).toBe(!gen.executable);
      if (!gen.executable) {
        expect(row.label, `${row.value} shows a reason`).toMatch(/Requires Setup|Runtime Offline|Testing|Unsupported|Provider Not Configured/);
      } else {
        expect(row.label, `${row.value} Ready line`).toMatch(/Ready/);
      }
    }

    const pcById = new Map(pcModels.map((model) => [model.id, model]));
    for (const row of gens) {
      const pcRow = pcById.get(row.id);
      if (!pcRow) continue;
      expect(Boolean(pcRow.executable), `${row.id} PC vs Timeline executable`).toBe(Boolean(row.executable));
    }
  });
});
