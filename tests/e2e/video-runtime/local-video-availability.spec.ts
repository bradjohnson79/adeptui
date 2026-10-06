import { expect, test } from "@playwright/test";

const PROJECT =
  process.env.ADEPT_PROJECT_ID?.trim() || "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";
const SCENE =
  process.env.ADEPT_SCENE_ID?.trim() || "1f46b621-46f9-4b7e-8273-202a49e1ca7c";

const RETIRED_CREATE = ["ltx", "wan", "hunyuan15", "hunyuan13b", "fal_seedance"] as const;

test.describe("local video generator availability", () => {
  test("Text to Video lists LTX 2.5, MiniMax H3, and versioned Seedance", async ({ page }) => {
    await page.goto(`/project/${PROJECT}?workspace=txt2vid`);
    const engine = page.locator("#txt2vid-engine");
    await expect(engine).toBeVisible({ timeout: 45_000 });
    await expect(engine.locator("option[value=auto]")).toBeAttached({ timeout: 45_000 });
    await expect(engine.locator("option[value='ltx-2.5']")).toBeAttached();
    await expect(engine.locator("option[value='minimax-h3']")).toBeAttached();
    await expect(engine.locator("option[value='seedance-2.0']")).toBeAttached();
    await expect(engine.locator("option[value='seedance-2.5']")).toBeAttached();
    const options = await engine.locator("option").evaluateAll((opts) =>
      (opts as HTMLOptionElement[]).map((opt) => ({
        value: opt.value,
        text: opt.textContent || "",
        disabled: opt.disabled,
      })),
    );
    const values = options.map((opt) => opt.value);
    expect(values).toContain("auto");
    expect(values).toContain("ltx-2.5");
    expect(values).toContain("minimax-h3");
    expect(values).toContain("seedance-2.0");
    expect(values).toContain("seedance-2.5");
    for (const forbidden of RETIRED_CREATE) {
      expect(values).not.toContain(forbidden);
    }
    const blob = options.map((opt) => `${opt.value} ${opt.text}`).join("\n");
    expect(blob).toMatch(/Seedance 2\.0/);
    expect(blob).toMatch(/Seedance 2\.5/);
    expect(blob).not.toMatch(/(^|\n)[^\n]*\bSeedance\b(?! 2\.)/);
  });

  test("1 Frame keeps LTX 2.5 and MiniMax selectable; WAN is not a CREATE default", async ({ page }) => {
    await page.goto(`/project/${PROJECT}?workspace=one&sceneId=${SCENE}`);
    await expect(page.getByTestId("one-frame-panel")).toBeVisible({ timeout: 45_000 });
    const engine = page.locator("select").filter({ has: page.locator("option[value='ltx-2.5']") }).first();
    await expect(engine).toBeAttached({ timeout: 45_000 });
    await expect(engine.locator("option[value='ltx-2.5']")).toBeEnabled();
    await expect(engine.locator("option[value='minimax-h3']")).toBeEnabled();
    await expect(engine.locator("option[value=ltx]")).toHaveCount(0);
    await expect(engine.locator("option[value=wan]")).toHaveCount(0);
    await expect(engine.locator("option[value='seedance-2.0']")).toBeAttached();
    await expect(engine.locator("option[value='seedance-2.5']")).toBeAttached();
  });

  test("3 Frame lists LTX 2.5 and hides MiniMax / Seedance three-still rows", async ({ page }) => {
    await page.goto(`/project/${PROJECT}?workspace=three&sceneId=${SCENE}`);
    const engine = page.locator("select").filter({ has: page.locator("option[value='ltx-2.5']") }).first();
    await expect(engine).toBeAttached({ timeout: 45_000 });
    await expect(engine.locator("option[value='ltx-2.5']")).toBeAttached();
    await expect(engine.locator("option[value='ltx-2.5']")).toBeEnabled();
    const h3 = engine.locator("option[value='minimax-h3']");
    if (await h3.count()) {
      await expect(h3).toBeDisabled();
    }
    await expect(engine.locator("option[value='seedance-2.0']")).toHaveCount(0);
    await expect(engine.locator("option[value='seedance-2.5']")).toHaveCount(0);
  });

  test("1 Frame Generate posts the scene engine", async ({ page }) => {
    let renderBody: Record<string, unknown> | null = null;
    await page.route("**/api/projects/*/render", async (route) => {
      if (route.request().method() !== "POST") {
        await route.continue();
        return;
      }
      renderBody = route.request().postDataJSON() as Record<string, unknown>;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "00000000-0000-4000-8000-000000000001",
          status: "queued",
          kind: "render_scene",
          progress: 0,
          message: "queued",
        }),
      });
    });
    await page.goto(`/project/${PROJECT}?workspace=one&sceneId=${SCENE}`);
    const generate = page.getByRole("button", { name: "Generate from 1 frame" });
    await expect(generate).toBeEnabled({ timeout: 45_000 });
    await generate.click();
    await expect.poll(() => renderBody).not.toBeNull();
    expect(renderBody?.action_scope).toBe("exploration");
    expect(String(renderBody?.engine || "")).toMatch(/ltx-2\.5|minimax-h3|seedance-2\.[05]/i);
  });

  test("Timeline shows versioned Seedance and local families without generic Seedance", async ({ page }) => {
    await page.goto(`/project/${PROJECT}?workspace=timeline&sceneId=${SCENE}`);
    const select = page.getByTestId("timeline-video-generator-select");
    await expect(select).toBeVisible({ timeout: 45_000 });
    const blob = await select.locator("option").evaluateAll((opts) =>
      (opts as HTMLOptionElement[]).map((opt) => `${opt.value} ${opt.textContent || ""}`).join("\n"),
    );
    expect(blob).toMatch(/ltx-2\.5|LTX 2\.5/);
    expect(blob).toMatch(/minimax-h3|MiniMax H3/);
    expect(blob.toLowerCase()).not.toMatch(/^seedance-fal\b/m);
    if (blob.includes("Seedance")) {
      expect(blob).toMatch(/Seedance 2\.[05]/);
    }
  });
});
