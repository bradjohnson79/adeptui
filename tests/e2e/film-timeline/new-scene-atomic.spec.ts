import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

/** New Scene must be atomic: one click creates exactly one hydrated scene with no
 * stale shot tags, no false Studio API Offline banner, and no loss of the old scene. */

async function makeProjectWithScene(request: APIRequestContext, name: string) {
  const created = await request.post("/api/projects", { data: { name: `${name} ${Date.now()}` } });
  expect(created.ok()).toBeTruthy();
  const projectId = String((await created.json()).id || "");
  const scene = await request.post(`/api/projects/${projectId}/scenes`, {
    data: { name: "Opening", engine: "auto", duration_sec: 10, prompt: "" },
  });
  expect(scene.ok()).toBeTruthy();
  const sceneId = String((await scene.json()).id || "");
  return { projectId, sceneId };
}

async function openTimeline(page: Page, projectId: string, sceneId: string) {
  await page.goto(`/project/${projectId}?workspace=timeline&sceneId=${sceneId}`);
  await expect(page.getByTestId("film-timeline-new-scene")).toBeVisible({ timeout: 45_000 });
  // Wait until the scene's canonical film has hydrated (shot tag reflects it).
  await expect(page.getByTestId("film-timeline-shot-tag")).toBeVisible({ timeout: 45_000 });
}

async function sceneCount(request: APIRequestContext, projectId: string): Promise<number> {
  const res = await request.get(`/api/projects/${projectId}`);
  expect(res.ok()).toBeTruthy();
  const body = await res.json();
  return Array.isArray(body?.scenes) ? body.scenes.length : 0;
}

async function shotTag(page: Page): Promise<string> {
  return (await page.getByTestId("film-timeline-shot-tag").textContent()) || "";
}

test("new scene is atomic, clean, and never raises a false offline banner", async ({ page, request }) => {
  test.setTimeout(120_000);
  const { projectId, sceneId } = await makeProjectWithScene(request, "New Scene Atomic");
  await openTimeline(page, projectId, sceneId);

  // Populate the first scene so stale state would be visible if it leaked.
  await page.getByTestId("film-timeline-new-scene").waitFor();
  const tagBefore = await shotTag(page);
  expect(tagBefore).toBe("#Shot1");

  // ---- Test A: one New Scene ----
  const scenesBefore = await sceneCount(request, projectId);
  await page.getByTestId("film-timeline-new-scene").click();
  // Button is single-flight: disabled while creating, with a concise label.
  await expect(page.getByTestId("film-timeline-new-scene")).toBeDisabled();
  // No global offline banner during or after creation.
  await expect(page.getByTestId("studio-api-outage-banner")).toHaveCount(0);
  // Wait for the switch: the scene select now shows the new scene (Scene 2).
  await expect(page.getByTestId("film-timeline-scene")).toHaveValue(/.*/, { timeout: 30_000 });
  await expect.poll(async () => (await page.getByTestId("film-timeline-scene").inputValue()), { timeout: 30_000 }).not.toBe(sceneId);
  // Exactly one new scene was created.
  await expect.poll(() => sceneCount(request, projectId)).toBe(scenesBefore + 1);
  // New scene hydrates clean: first shot tag is #Shot1, no stale Shot N label.
  await expect(page.getByTestId("film-timeline-shot-tag")).toHaveText("#Shot1");
  await expect(page.getByTestId("film-timeline-preview-shot")).toHaveCount(0);
  // Preview is the empty/new-scene state, not a stale frame.
  await expect(page.getByTestId("film-timeline-monitor")).toContainText("Generate a shot to see it here.");
  // No offline banner appeared.
  await expect(page.getByTestId("studio-api-outage-banner")).toHaveCount(0);

  // ---- Test B: repeated scene creation ----
  const beforeB = await sceneCount(request, projectId);
  for (let i = 0; i < 3; i += 1) {
    await page.getByTestId("film-timeline-new-scene").click();
    await expect(page.getByTestId("film-timeline-new-scene")).toBeDisabled();
    await expect.poll(async () => (await page.getByTestId("film-timeline-scene").inputValue()), { timeout: 30_000 }).not.toBe("");
    await expect(page.getByTestId("film-timeline-shot-tag")).toHaveText("#Shot1");
    await expect(page.getByTestId("studio-api-outage-banner")).toHaveCount(0);
  }
  await expect.poll(() => sceneCount(request, projectId)).toBe(beforeB + 3);

  // ---- Test C: switch back to the original scene ----
  await page.getByTestId("film-timeline-scene").selectOption(sceneId);
  await expect(page.getByTestId("film-timeline-shot-tag")).toHaveText("#Shot1");
  await expect(page.getByTestId("studio-api-outage-banner")).toHaveCount(0);

  // ---- Test D: forced backend failure keeps the current scene ----
  const currentScene = await page.getByTestId("film-timeline-scene").inputValue();
  const beforeD = await sceneCount(request, projectId);
  await page.route("**/api/projects/*/scenes", (route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "forced failure" }) });
    }
    return route.continue();
  });
  await page.getByTestId("film-timeline-new-scene").click();
  // Creator-facing error appears, current scene is preserved, no new scene.
  await expect(page.getByTestId("film-timeline-error")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("film-timeline-scene")).toHaveValue(currentScene);
  expect(await sceneCount(request, projectId)).toBe(beforeD);
  // A scene-create validation failure must not raise the global offline banner.
  await expect(page.getByTestId("studio-api-outage-banner")).toHaveCount(0);
  await page.unroute("**/api/projects/*/scenes");
});

test("new scene transition never oscillates scene selection or storms the API", async ({ page, request }) => {
  // Regression for the Priority-One crash: createScene used to commit selection
  // while the URL still carried the old sceneId; ProjectEditor's URL↔selection
  // effects ping-ponged old↔new (~187 flaps in 5s), each flap refetching the
  // W46 master — which 500'd on engine="auto" — and the transport errors from
  // that storm tripped the global Studio API Offline banner.
  test.setTimeout(120_000);
  const { projectId, sceneId } = await makeProjectWithScene(request, "New Scene Race");
  await openTimeline(page, projectId, sceneId);

  const masterFailures: Array<{ status: number; url: string }> = [];
  let requestCount = 0;
  page.on("response", (res) => {
    const url = res.url();
    if (url.includes("/api/director-timeline/") && url.includes("/master") && res.status() >= 400) {
      masterFailures.push({ status: res.status(), url });
    }
  });
  page.on("request", (req) => {
    if (req.url().includes("/api/")) requestCount += 1;
  });

  const scenesBefore = await sceneCount(request, projectId);
  await page.getByTestId("film-timeline-new-scene").click();

  // Sample selection + URL through the whole transition (~6s). Once the new
  // id appears, neither the select nor the URL may ever regress to the old id.
  const samples: Array<{ select: string; urlScene: string }> = [];
  let newSceneId = "";
  const deadline = Date.now() + 6000;
  while (Date.now() < deadline) {
    const select = await page.getByTestId("film-timeline-scene").inputValue().catch(() => "");
    const urlScene = new URL(page.url()).searchParams.get("sceneId") || "";
    samples.push({ select, urlScene });
    if (!newSceneId && select && select !== sceneId) newSceneId = select;
    await page.waitForTimeout(40);
  }
  expect(newSceneId, "transition never selected the new scene").toBeTruthy();
  const seenNew = { select: false, url: false };
  for (const sample of samples) {
    if (sample.select === newSceneId) seenNew.select = true;
    if (sample.urlScene === newSceneId) seenNew.url = true;
    if (seenNew.select) expect(sample.select, "select regressed to old scene mid-transition").not.toBe(sceneId);
    if (seenNew.url) expect(sample.urlScene, "URL sceneId regressed to old scene mid-transition").not.toBe(sceneId);
  }

  // Converged: select and URL agree on the new scene.
  await expect.poll(async () => new URL(page.url()).searchParams.get("sceneId"), { timeout: 15_000 }).toBe(newSceneId);
  await expect(page.getByTestId("film-timeline-scene")).toHaveValue(newSceneId);

  // Exactly one scene created; no master 5xx; request volume bounded (no storm).
  await expect.poll(() => sceneCount(request, projectId)).toBe(scenesBefore + 1);
  expect(masterFailures, `master read failures: ${JSON.stringify(masterFailures.slice(0, 5))}`).toHaveLength(0);
  expect(requestCount, `request storm suspected: ${requestCount} api requests in ~6s`).toBeLessThan(150);
  await expect(page.getByTestId("studio-api-outage-banner")).toHaveCount(0);
  await expect(page.getByTestId("film-timeline-shot-tag")).toHaveText("#Shot1");
});
