import { chromium } from "@playwright/test";

const projectId = process.env.ADEPT_PROJECT_ID || "fcd7b4b0-7d36-4757-ac82-a701e6e1a50c";
const baseUrl = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:8760";
const apiBase = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

const consoleMessages = [];
const blockedFailures = [];
page.on("console", (msg) => {
  const text = msg.text();
  consoleMessages.push({ type: msg.type(), text });
  if (/record_production_decision.+isn't a Co-Director tool|m214\/plan|404/i.test(text)) {
    blockedFailures.push({ source: "console", text });
  }
});
page.on("response", async (res) => {
  const url = res.url();
  if (/\/api\/codirector\/m214\/plan/i.test(url) && res.status() >= 400) {
    blockedFailures.push({ source: "network", status: res.status(), url });
  }
});

await page.goto(`${baseUrl}/co-director?projectId=${projectId}`, { waitUntil: "domcontentloaded" });
await page.getByTestId("codirector-fullscreen-shell").waitFor({ state: "visible", timeout: 30_000 });
const toggle = page.getByTestId("codirector-toggle-content");
if ((await toggle.getAttribute("aria-pressed").catch(() => null)) === "false") {
  await toggle.click();
}
await page.getByTestId("codirector-content-tab-wiki").waitFor({ state: "attached" });
if (await page.getByTestId("codirector-content-tab-wiki").isVisible().catch(() => false)) {
  await page.getByTestId("codirector-content-tab-wiki").click();
}
const wikiReady = async () => {
  if (await page.getByTestId("codirector-project-wiki").isVisible().catch(() => false)) return "full";
  if (await page.getByTestId("project-wiki-empty").isVisible().catch(() => false)) return "empty";
  return null;
};
let wikiState = await wikiReady();
const wikiDeadline = Date.now() + 30_000;
while (!wikiState && Date.now() < wikiDeadline) {
  await page.waitForTimeout(500);
  wikiState = await wikiReady();
}
if (!wikiState) {
  const diag = {
    projectContentVisible: await page.getByTestId("codirector-project-content").isVisible().catch(() => false),
    wikiTabVisible: await page.getByTestId("codirector-content-tab-wiki").isVisible().catch(() => false),
    wikiTabPressed: await page.getByTestId("codirector-content-tab-wiki").getAttribute("aria-pressed").catch(() => null),
    togglePressed: await page.getByTestId("codirector-toggle-content").getAttribute("aria-pressed").catch(() => null),
    body: await page.locator("body").innerText().catch(() => ""),
  };
  console.error(JSON.stringify(diag, null, 2));
  throw new Error("Project Wiki did not appear in either empty or populated state.");
}

const shellBox = await page.getByTestId("codirector-fullscreen-shell").boundingBox();
const viewport = page.viewportSize();
const widthRatio = shellBox && viewport ? shellBox.width / viewport.width : null;

const initialWikiText = wikiState === "full"
  ? await page.getByTestId("codirector-project-wiki").innerText()
  : await page.getByTestId("project-wiki-empty").innerText();
const overviewTabCount = await page.locator('[data-testid="codirector-content-tab-overview"]').count();

await page.getByLabel("Message Co-Director").fill(
  "Please rename this project to The Dreamweaver and save that title. Start the Project Wiki from this first message, keep Wiki as the default Project Focus tab, and avoid any repository diagnostics."
);
await page.getByTestId("codirector-send-button").click();

let approved = false;
const approveButton = page.getByTestId("codirector-proposal-approve").first();
try {
  await approveButton.waitFor({ state: "visible", timeout: 45_000 });
  await approveButton.click();
  approved = true;
} catch {
  // Some model runs may complete without a visible approval card; continue to title checks.
}

await page.getByTestId("codirector-header-project").waitFor({ state: "visible", timeout: 45_000 });
await page.waitForTimeout(4000);
const sendErrorVisible = await page.getByTestId("codirector-send-error").count();
const sendErrorText = sendErrorVisible ? await page.getByTestId("codirector-send-error").innerText() : "";

const headerTitle = await page.getByTestId("codirector-header-project").innerText();
const wikiTitle = await page.locator("[data-testid='codirector-project-wiki'] h3").first().innerText();
const wikiText = await page.getByTestId("codirector-project-wiki").innerText();

await page.reload({ waitUntil: "domcontentloaded" });
await page.getByTestId("codirector-fullscreen-shell").waitFor({ state: "visible", timeout: 30_000 });
if (await page.getByTestId("project-wiki-empty").isVisible().catch(() => false)) {
  throw new Error("Project Wiki regressed to empty after the first Dreamweaver message.");
}
await page.getByTestId("codirector-project-wiki").waitFor({ state: "visible", timeout: 30_000 });
const reloadedHeaderTitle = await page.getByTestId("codirector-header-project").innerText();
const reloadedWikiTitle = await page.locator("[data-testid='codirector-project-wiki'] h3").first().innerText();

await page.goto(`${baseUrl}/project/${projectId}`, { waitUntil: "domcontentloaded" });
const projectPageText = await page.locator("body").innerText();

await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
await page.getByTestId("create-project-open").waitFor({ state: "visible", timeout: 30_000 });
const homeText = await page.locator("body").innerText();

const projects = await (await page.request.get(`${apiBase}/api/projects`)).json();

const evidence = {
  ok: true,
  projectId,
  approved,
  widthRatio,
  overviewTabCount,
  initialWikiDiagnosticsClean: !/project\.get_summary|project\.list_blockers|project_service|session_context/i.test(initialWikiText),
  finalWikiDiagnosticsClean: !/project\.get_summary|project\.list_blockers|project_service|session_context/i.test(wikiText),
  blockedFailures,
  sendErrorText,
  headerTitle,
  wikiTitle,
  reloadedHeaderTitle,
  reloadedWikiTitle,
  projectPageShowsDreamweaver: /The Dreamweaver/.test(projectPageText),
  homeShowsDreamweaver: /The Dreamweaver/.test(homeText),
  apiProjects: projects.map((p) => ({ id: p.id, name: p.name })),
};

console.log(JSON.stringify(evidence, null, 2));
await browser.close();
