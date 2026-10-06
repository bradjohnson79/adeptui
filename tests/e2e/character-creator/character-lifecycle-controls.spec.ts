/**
 * Playwright A–E — Character Creator Save / Reset / Delete on a disposable project.
 * Never writes Schnick Coffee (2347bf46). Never clicks Generate.
 */
import { expect, test } from "@playwright/test";
import { createTempProject, deleteProject } from "../helpers/app";

const BASE = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173";
const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const SCHNICK_ID = "2347bf46-3762-4763-86c5-4a6032522278";

test.setTimeout(180_000);

test.describe("Character Creator lifecycle controls", () => {
  test("A–E save persist, reset snapshot, delete disposable", async ({ page, request }) => {
    const project = await createTempProject(request, `Lifecycle ${Date.now()}`);
    expect(project.id).not.toBe(SCHNICK_ID);
    const name = `Lifecycle ${Date.now()}`;
    const original = "Disposable lifecycle fixture with enough description for a valid profile.";
    try {
      const created = await request.post(`${API}/api/projects/${project.id}/characters`, {
        data: { name, description: original },
      });
      expect(created.ok(), await created.text()).toBeTruthy();
      const body = await created.json();
      const id = String(body.id || body.characterId);

      const patches: string[] = [];
      page.on("request", (req) => {
        if (req.method() === "PATCH" && req.url().includes(`/characters/${id}`)) {
          patches.push(req.url());
        }
      });

      await page.goto(`${BASE}/project/${project.id}?workspace=characters&characterId=${id}`, {
        waitUntil: "domcontentloaded",
      });
      await expect(page.getByTestId("character-core")).toBeVisible({ timeout: 30_000 });

      const description = page.getByTestId("character-field-profile");
      await expect(description).toBeVisible();
      await description.fill("Changed locally and should reset.");
      await expect(page.getByTestId("character-reset")).toBeEnabled();
      await page.getByTestId("character-reset").click();
      await expect(description).toHaveValue(original);
      expect(patches).toEqual([]);

      await description.fill("Saved through the only persist path.");
      await page.getByTestId("character-save").click();
      await expect(page.getByTestId("character-core-notice")).toContainText(/saved/i, { timeout: 15_000 });
      await page.reload({ waitUntil: "domcontentloaded" });
      await expect(page.getByTestId("character-core")).toBeVisible({ timeout: 30_000 });
      await expect(page.getByTestId("character-field-profile")).toHaveValue("Saved through the only persist path.");

      page.once("dialog", (d) => d.accept());
      await page.getByTestId("character-delete").click();
      await expect
        .poll(async () => {
          const res = await request.get(`${API}/api/projects/${project.id}/characters/${id}`);
          return res.status();
        }, { timeout: 20_000 })
        .toBe(404);
    } finally {
      await deleteProject(request, project.id);
    }
  });
});
