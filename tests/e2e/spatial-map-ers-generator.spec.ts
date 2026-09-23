/**
 * Spatial Map ERS provider contract — GPT Image 2 only.
 * Named Korri project + Venture Corridor Walk. Never creates a project.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { API } from "./helpers/app";

const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";
const MAP_TITLE = /venture corridor walk/i;

test.setTimeout(8 * 60 * 1000);

async function resolveVentureMap(request: APIRequestContext): Promise<string> {
  const res = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps`);
  expect(res.ok(), "list Spatial Maps").toBeTruthy();
  const body = await res.json();
  const maps = (body.documents || body.maps || body.items || []) as Array<{ id?: string; title?: string }>;
  const venture = maps.find((m) => MAP_TITLE.test(String(m.title || "")));
  expect(venture?.id, "Venture Corridor Walk must exist").toBeTruthy();
  return String(venture!.id);
}

async function openStandardSpatial(page: Page, mapId: string) {
  await page.goto(`/project/${PROJECT_ID}?workspace=spatial`, {
    waitUntil: "domcontentloaded",
    timeout: 60_000,
  });
  await expect(page.getByTestId("spatial-map-panel")).toBeVisible({ timeout: 45_000 });
  const select = page.locator("#spatial-map-select");
  if ((await select.count()) && (await select.isVisible().catch(() => false))) {
    await select.selectOption(mapId);
  }
  await expect(page.getByTestId("spatial-map-grid")).toBeVisible({ timeout: 20_000 });
}

test.describe("Spatial Map ERS generator contract", () => {
  test("ERS Generator is GPT Image 2 only — no Qwen dropdown or fallback", async ({
    page,
    request,
  }) => {
    const mapId = await resolveVentureMap(request);
    await openStandardSpatial(page, mapId);

    const fixed = page.getByTestId("ers-generator-fixed");
    await expect(fixed).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("ers-generator-select")).toHaveCount(0);
    await expect(page.getByTestId("ers-generator")).not.toContainText(/Qwen/i);

    const label = (await fixed.innerText()).trim();
    expect(label === "GPT Image 2 — API" || label === "GPT Image 2 — Requires Setup").toBeTruthy();

    if (label === "GPT Image 2 — Requires Setup") {
      const reason = page.getByTestId("ers-generator-reason");
      if (await reason.count()) {
        await expect(reason).not.toContainText(/I'll use Qwen|choose Qwen/i);
      }
      const generate = page.getByRole("button", {
        name: /Generate Environment Reference Sheet|Regenerate Environment Reference Sheet/i,
      });
      await expect(generate).toBeDisabled();
    }
  });

  test("Regenerate Environment Reference Sheet uses GPT Image 2, never Qwen", async ({
    page,
    request,
  }) => {
    const mapId = await resolveVentureMap(request);
    await openStandardSpatial(page, mapId);
    const fixed = page.getByTestId("ers-generator-fixed");
    await expect(fixed).toBeVisible({ timeout: 20_000 });
    const label = (await fixed.innerText()).trim();
    if (label !== "GPT Image 2 — API") {
      test.info().annotations.push({
        type: "ers-provider",
        description: label,
      });
      await expect(fixed).toHaveText("GPT Image 2 — Requires Setup");
      await expect(page.getByTestId("ers-generator")).not.toContainText(/Qwen/i);
      return;
    }

    const generate = page.getByRole("button", {
      name: /Generate Environment Reference Sheet|Regenerate Environment Reference Sheet/i,
    });
    await expect(generate).toBeEnabled();
    const posted: string[] = [];
    page.on("request", (req) => {
      if (req.method() !== "POST") return;
      const url = req.url();
      const body = `${req.postData() || ""}`;
      if (url.includes("/executions") && /ers\.generate/i.test(body)) {
        posted.push(body);
      }
    });
    await generate.click();
    await expect.poll(() => posted.length, { timeout: 30_000 }).toBeGreaterThan(0);
    expect(posted.join(" ")).toMatch(/gpt-image-2/i);
    expect(posted.join(" ")).not.toMatch(/qwen2512/i);

    const model = page.getByTestId("ers-generation-model");
    await expect(model).toContainText(/GPT Image 2/i, { timeout: 30_000 });
    await expect(model).not.toContainText(/Qwen/i);

    await expect(page.getByTestId("ers-generation-monitor")).toBeVisible({ timeout: 15_000 });
    await expect
      .poll(
        async () => {
          const stage = (await page.getByTestId("ers-generation-stage").innerText().catch(() => "")).toLowerCase();
          const err = await page.getByTestId("ers-generation-retry").isVisible().catch(() => false);
          if (err) return "failed";
          if (stage.includes("complete") || stage.includes("ready") || stage.includes("saved")) return "complete";
          return stage || "running";
        },
        { timeout: 6 * 60 * 1000 },
      )
      .toMatch(/complete|failed/);

    const sheets = await request.get(`${API}/api/environment-reference-sheets/projects/${PROJECT_ID}/sheets`);
    if (sheets.ok()) {
      const body = await sheets.json();
      const text = JSON.stringify(body);
      expect(text).not.toMatch(/I'll use Qwen/i);
    }
  });
});
