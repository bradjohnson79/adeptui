import { test, expect, type APIRequestContext, type Page } from "@playwright/test";
import { API, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import { AuditObserver } from "../helpers/observer";

async function uploadTaggedAsset(
  request: APIRequestContext,
  projectId: string,
  tag: string,
  filename: string,
) {
  const res = await request.post(`${API}/api/projects/${projectId}/assets`, {
    multipart: {
      tag,
      kind: "image",
      file: {
        name: filename,
        mimeType: "image/png",
        buffer: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9sZf0jEAAAAASUVORK5CYII=", "base64"),
      },
    },
  });
  expect(res.ok()).toBeTruthy();
}

async function openBibleWorkspace(page: Page, projectId: string) {
  await page.goto(`/project/${projectId}?workspace=bible`);
  await expect(page.getByRole("heading", { name: "Production Bible" })).toBeVisible({ timeout: 30_000 });
}

test.describe("@critical @isolated production bible creative flow", () => {
  test.beforeEach(async ({ request }) => {
    await waitForAppReady(request);
  });

  test("empty state to version one to character detail and search", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    const project = await createTempProject(request, `Bible Creative ${Date.now()}`);

    try {
      await uploadTaggedAsset(request, project.id, "Korri Character", "korri-front.png");
      await uploadTaggedAsset(request, project.id, "Korri Character", "korri-side.png");
      await uploadTaggedAsset(request, project.id, "Skybridge Rooftop Location", "rooftop.png");

      await openBibleWorkspace(page, project.id);
      await expect(page.getByTestId("bible-empty-state")).toBeVisible();
      await expect(page.getByRole("button", { name: "Create from Project" })).toBeVisible();
      await expect(page.getByRole("button", { name: "Start Manually" })).toBeVisible();

      await page.getByRole("button", { name: "Create from Project" }).click();
      await expect(page.getByRole("heading", { name: "Create Production Bible" })).toBeVisible({
        timeout: 15_000,
      });
      await expect(page.getByText("Review discoveries")).toBeVisible();
      await expect(page.getByText("Characters")).toBeVisible();
      await expect(page.getByText("Locations")).toBeVisible();

      await page.getByRole("button", { name: "Choose what belongs" }).click();
      await expect(page.getByRole("checkbox", { name: /Korri/i })).toBeVisible();
      await expect(page.getByText("2 reference assets", { exact: true })).toBeVisible();
      await page.getByRole("button", { name: "Organize and confirm" }).click();

      await expect(page.getByText("Organize and confirm")).toBeVisible();
      await page.getByTestId("bible-create-version-one").click();

      await expect
        .poll(async () => {
          const res = await request.get(`${API}/api/codirector/projects/${project.id}/bible`);
          if (!res.ok()) return 0;
          const body = await res.json();
          return Number(body.currentVersion?.versionNumber || 0);
        }, { timeout: 15_000 })
        .toBe(1);
      await openBibleWorkspace(page, project.id);
      await expect(page.locator("nav").getByRole("button", { name: "Characters" })).toBeVisible({
        timeout: 15_000,
      });

      await page.locator("nav").getByRole("button", { name: "Characters" }).click();
      await page.getByRole("button", { name: "Korri" }).click();
      await expect(page.getByRole("heading", { name: "Korri" })).toBeVisible();
      await expect(page.getByText("Reference Assets")).toBeVisible();

      await page.getByRole("button", { name: "Back to Characters" }).click();
      await page.locator("nav").getByRole("button", { name: "Locations" }).click();
      await page.getByRole("searchbox", { name: "Search the Bible" }).fill("Skybridge");
      await expect(page.getByRole("button", { name: "Skybridge Rooftop" })).toBeVisible();

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });
});
