import { expect, test } from "@playwright/test";

test.use({ extraHTTPHeaders: {} });

const PROJECT = "c3c20b09-eff1-4b47-b7e7-e889ba768ef0";
const root = `/project/${PROJECT}`;

const visits: { name: string; url: string; testId?: string; text?: string }[] = [
  { name: "Homepage", url: "/", testId: "generation-studio-hero" },
  { name: "Co-Director", url: `/co-director?projectId=${PROJECT}`, testId: "codirector-composer" },
  { name: "Character Creator", url: `${root}?workspace=characters`, text: "Character Creator" },
  { name: "Voice Studio", url: `${root}?workspace=voicestudio`, text: "Voice Studio" },
  { name: "Prop Creator", url: `${root}?workspace=propcreator`, text: "Prop Creator" },
  { name: "Environment Creator", url: `${root}?workspace=environmentcreator`, text: "Environment Creator" },
  { name: "Image Generator", url: `${root}?workspace=imagegen`, testId: "cis-prompt" },
  { name: "Storyboard", url: `${root}?workspace=script`, text: "Storyboard Studio" },
  { name: "Timeline", url: `${root}?workspace=timeline`, text: "Timeline Generator" },
  { name: "MAGI", url: `${root}?workspace=magi`, testId: "magi-viewer" },
  { name: "Library", url: `${root}?workspace=library`, text: "Library" },
  { name: "Scriptwriter", url: `${root}?workspace=scriptwriter`, text: "Scriptwriter" },
  { name: "Setup", url: `${root}?workspace=setup`, text: "Setup" },
  { name: "Comfy Manager", url: `${root}?workspace=setup&setupSection=comfy`, testId: "comfy-manager" },
  { name: "Homepage return", url: "/", testId: "generation-studio-hero" },
];

test("site-wide polish smoke keeps every major workspace available", async ({ page }) => {
  test.setTimeout(240_000);
  const pageErrors: string[] = [];
  const consoleErrors: string[] = [];
  const failed: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    if (/favicon|Download the React DevTools|Failed to load resource: the server responded with a status of 404/i.test(text)) return;
    consoleErrors.push(text);
  });
  page.on("response", (response) => {
    if (response.status() < 400) return;
    const url = response.url();
    if (url.includes("favicon") || url.includes("chrome-extension")) return;
    // Intentional empty state: a project with no Production Bible returns 404.
    if (response.status() === 404 && url.includes("/api/codirector/projects/") && url.endsWith("/bible")) return;
    failed.push(`${response.status()} ${url}`);
  });
  page.on("requestfailed", (request) => {
    const reason = request.failure()?.errorText || "";
    if (reason.includes("ERR_ABORTED") || reason.includes("ERR_BLOCKED_BY_CLIENT")) return;
    failed.push(`${reason} ${request.url()}`);
  });

  for (const visit of visits) {
    await page.goto(visit.url, { waitUntil: "domcontentloaded" });
    if (visit.testId) {
      await expect(page.getByTestId(visit.testId), visit.name).toBeVisible({ timeout: 45_000 });
    } else if (visit.text) {
      await expect(page.getByText(visit.text, { exact: false }).first(), visit.name).toBeVisible({ timeout: 45_000 });
    }
  }

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "ADEPT UI", exact: true })).toBeVisible();
  await expect(page.getByTestId("generation-studio-hero-logo")).toHaveAttribute("src", /adept-ui-emblem\.webp/);
  await expect(page.getByTestId("generation-studio-hero-image")).toHaveCount(0);
  await page.getByRole("searchbox", { name: "Search Adept UI" }).click();
  const palette = page.getByTestId("command-palette");
  await expect(palette).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(palette).toBeHidden();

  expect(failed, failed.join("\n")).toEqual([]);
  expect(pageErrors, pageErrors.join("\n")).toEqual([]);
  expect(consoleErrors, consoleErrors.join("\n")).toEqual([]);
});
