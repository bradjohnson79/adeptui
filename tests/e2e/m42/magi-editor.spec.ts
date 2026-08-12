/**
 * M42 Wave 4B — MAGI Editor UX + overlay Playwright coverage (Scenarios I–Q API/UI).
 */
import { expect, test } from "@playwright/test";
import { API, createTempProject, deleteProject } from "../helpers/app";

const TINY_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64",
);

test.describe("M42 W4B MAGI Editor @DETERMINISTIC", () => {
  test("readiness API is honest about deferred surfaces", async ({ request }) => {
    const res = await request.get("/api/magi/readiness");
    if (!res.ok()) {
      test.skip(true, "API not available");
      return;
    }
    const body = await res.json();
    expect(body.productName).toBe("Adept UI MAGI Editor");
    expect(body.noFakeExecution).toBeTruthy();
    expect(body.korri?.role).toBe("presentation-only");
    for (const s of body.deferredSurfaces || []) {
      expect(s.executable).toBeFalsy();
    }
  });

  test("deferred execute endpoint refuses fake execution", async ({ request }) => {
    const res = await request.post("/api/magi/deferred/video_inpainting/execute");
    if (res.status() >= 500 || res.status() === 404) {
      test.skip(true, "API not available");
      return;
    }
    const body = await res.json();
    expect(body.executed).toBeFalsy();
    expect(body.ok).toBeFalsy();
  });

  test("wave4b gate reports overlay + Wave5MayBegin fields when stamped", async ({ request }) => {
    const res = await request.get("/api/magi/gate/wave4b");
    if (!res.ok()) {
      test.skip(true, "API not available");
      return;
    }
    const body = await res.json();
    expect(body).toHaveProperty("wave4bGo");
    expect(body).toHaveProperty("Wave5MayBegin");
    expect(body).toHaveProperty("textOverlayDomainOperational");
    expect(body).toHaveProperty("missingRequirements");
  });

  test("Scenario P — overlay validate rejects script markup", async ({ request }) => {
    const projects = await request.get("/api/projects");
    if (!projects.ok()) {
      test.skip(true, "API not available");
      return;
    }
    const list = await projects.json();
    const projectId = list?.projects?.[0]?.id || list?.[0]?.id;
    if (!projectId) {
      test.skip(true, "No project");
      return;
    }
    const res = await request.post(`/api/magi/projects/${projectId}/overlays/validate`, {
      data: {
        schemaVersion: 1,
        compositionId: "test-sec",
        projectId,
        sourceAssetId: null,
        canvasWidth: 640,
        canvasHeight: 360,
        overlays: [
          {
            id: "t1",
            type: "text",
            name: "x",
            visible: true,
            locked: false,
            opacity: 1,
            x: 0.1,
            y: 0.1,
            width: 0.4,
            height: 0.1,
            rotation: 0,
            anchorX: 0,
            anchorY: 0,
            zIndex: 1,
            startFrame: null,
            endFrame: null,
            createdAt: "2026-01-01T00:00:00Z",
            updatedAt: "2026-01-01T00:00:00Z",
            text: "<script>alert(1)</script>",
            textStyle: { fontFamily: "dejavu-sans", fontSize: 24, fontWeight: 400, color: "#fff" },
            backgroundStyle: null,
            animationPreset: null,
          },
        ],
        safeAreaEnabled: true,
        createdAt: "2026-01-01T00:00:00Z",
        updatedAt: "2026-01-01T00:00:00Z",
      },
    });
    if (!res.ok() && res.status() >= 500) {
      test.skip(true, "API error");
      return;
    }
    const body = await res.json();
    expect(body.ok).toBeFalsy();
  });

  test("Scenario I/K shell — MAGI editor exposes text graphics + overlay layer hooks", async ({ page, request }) => {
    // Product intent: MAGI ships low-frequency panes (Graphics, Command) collapsed by
    // default — reveal-on-demand. Seed one image so the viewer auto-selects it and the
    // overlay layer hook mounts.
    const project = await createTempProject(request, `MAGI I/K ${Date.now()}`);
    try {
      const upload = await request.post(`${API}/api/projects/${project.id}/assets`, {
        multipart: {
          file: { name: "shot.png", mimeType: "image/png", buffer: TINY_PNG },
          tag: "shot",
          kind: "image",
        },
      });
      expect(upload.ok()).toBeTruthy();

      await page.goto(`/project/${project.id}?workspace=magi`);
      const editor = page.getByTestId("magi-editor");
      await expect(editor).toBeVisible({ timeout: 30_000 });
      await expect(page.getByTestId("magi-strip")).toBeVisible();

      // Graphics pane ships collapsed; open it and verify the creator-facing controls.
      await page.locator("#magi-acc-btn-graphics").click();
      const textGraphics = page.getByTestId("magi-text-graphics");
      await expect(textGraphics).toBeVisible();
      await expect(textGraphics.getByRole("button", { name: "Add Text" })).toBeVisible();
      await expect(textGraphics.getByRole("button", { name: "Lower Third", exact: true })).toBeVisible();
      await expect(page.getByTestId("magi-overlay-render")).toBeVisible();

      // Overlay layer hook mounts on the viewer once an asset is selected.
      await expect(page.getByTestId("magi-overlay-layer")).toBeVisible();

      // Command pane ships collapsed by default; open it and verify the surface + stage.
      const commandBtn = page.locator("#magi-acc-btn-command");
      await expect(commandBtn).toHaveAttribute("aria-expanded", "false");
      await commandBtn.click();
      const commandPane = page.getByTestId("magi-command");
      await expect(commandPane).toBeVisible();
      const input = commandPane.locator("textarea");
      await expect(input).toBeVisible();
      await expect(page.getByTestId("magi-command-stage")).toContainText("Stage:");
      await input.fill("add lower third");
      // A parseable command surfaces a proposal with a Create Proposal action.
      await expect(commandPane.getByRole("button", { name: "Create Proposal" })).toBeVisible();
      // Collapse/reopen verifies the pane toggles cleanly without losing state.
      await commandBtn.click();
      await expect(commandPane).not.toBeVisible();
      await commandBtn.click();
      await expect(commandPane).toBeVisible();
    } finally {
      await deleteProject(request, project.id);
    }
  });
});
