import { chromium } from "playwright";

const TARGET = "https://adeptui.vercel.app";
const API_BASE = "https://api-beta.adeptui.org";

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
  const page = await context.newPage();

  const consoleErrors = [];
  const requestFailures = [];
  const corsErrors = [];

  page.on("console", (msg) => {
    if (msg.type() === "error") {
      const text = msg.text();
      consoleErrors.push(text);
      if (text.includes("CORS") || text.includes("Access-Control")) corsErrors.push(text);
    }
  });
  page.on("pageerror", (err) => consoleErrors.push(`pageerror: ${err.message}`));
  page.on("requestfailed", (req) => {
    if (req.url().includes("/api/")) requestFailures.push(`${req.url()}: ${req.failure()?.errorText}`);
  });

  console.log("=== FOUR PILLARS LIVE CERTIFICATION ===\n");
  console.log("Opening", TARGET);
  await page.goto(TARGET, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(3000);

  // Check projects exist
  const bodyText = await page.textContent("body").catch(() => "");
  const hasProjects = !bodyText?.includes("No Projects Yet");
  console.log("Projects visible:", hasProjects);

  // Find Schnick Coffee project and open it
  console.log("\n--- FLOW A: PROJECT BUILDING ---");

  // Click on Schnick Coffee project
  const schnickLink = page.locator("text=Schnick Coffee").first();
  if (await schnickLink.count() > 0) {
    await schnickLink.click({ timeout: 10000 });
    await page.waitForTimeout(3000);
    console.log("Opened Schnick Coffee project");
  } else {
    // Try clicking first project
    const firstProject = page.locator("[data-testid*='project'], .project-card, .project-library-grid > *").first();
    if (await firstProject.count() > 0) {
      await firstProject.click({ timeout: 10000 });
      await page.waitForTimeout(3000);
      console.log("Opened first project");
    }
  }

  // Open Co-Director
  console.log("\nOpening Co-Director...");
  const coDirectorBtn = page.locator("text=Co-Director").first();
  if (await coDirectorBtn.count() > 0) {
    await coDirectorBtn.click({ timeout: 10000 });
    await page.waitForTimeout(3000);
    console.log("Co-Director opened");
  }

  // Check for Project Building pane tabs
  const wikiTab = page.getByText("Wiki", { exact: true }).first();
  const notesTab = page.getByText("Notes", { exact: true }).first();
  const storyTab = page.getByText("Story", { exact: true }).first();
  const scriptTab = page.getByText("Script Writer", { exact: true }).first();
  const storyboardTab = page.getByText("Storyboard", { exact: true }).first();
  const characterTab = page.getByText("Character Creator", { exact: true }).first();
  const libraryTab = page.getByText("Library", { exact: true }).first();

  console.log("Tab checks:", {
    wiki: await wikiTab.count() > 0,
    notes: await notesTab.count() > 0,
    story: await storyTab.count() > 0,
    scriptWriter: await scriptTab.count() > 0,
    storyboard: await storyboardTab.count() > 0,
    characterCreator: await characterTab.count() > 0,
    library: await libraryTab.count() > 0,
  });

  // Check for Foundation Status Bar
  const foundationStatus = page.locator("[data-testid='codirector-foundation-status']").count();
  console.log("FoundationStatusBar:", foundationStatus > 0 ? "FOUND" : "NOT FOUND");

  // Test Story tab
  console.log("\n--- STORY TAB ---");
  if (await storyTab.count() > 0) {
    await storyTab.click({ timeout: 5000 });
    await page.waitForTimeout(2000);
    const storyEditor = page.locator("[data-testid='story-editor']").count();
    const storyTitle = page.locator("[data-testid='story-title']").count();
    const storyContent = page.locator("[data-testid='story-content']").count();
    const storySaveState = page.locator("[data-testid='story-save-state']").count();
    console.log("Story editor found:", storyEditor > 0);
    console.log("Story title input:", storyTitle > 0);
    console.log("Story content area:", storyContent > 0);
    console.log("Story save state:", storySaveState > 0);

    // Check for toolbar buttons
    const boldBtn = page.locator("[data-testid='story-btn-bold']").count();
    const italicBtn = page.locator("[data-testid='story-btn-italic']").count();
    const undoBtn = page.locator("[data-testid='story-btn-undo']").count();
    console.log("Toolbar buttons:", { bold: boldBtn > 0, italic: italicBtn > 0, undo: undoBtn > 0 });
  }

  // Test Wiki tab (should show FoundationStatusBar)
  console.log("\n--- WIKI TAB ---");
  if (await wikiTab.count() > 0) {
    await wikiTab.click({ timeout: 5000 });
    await page.waitForTimeout(2000);
    const wikiPanel = page.locator(".project-wiki-panel, [data-testid*='wiki-panel']").count();
    console.log("Wiki panel:", wikiPanel > 0);
    const foundationBar = page.locator("[data-testid='codirector-foundation-status']").count();
    console.log("FoundationStatusBar in Wiki:", foundationBar > 0);
  }

  // Check Script Writer toolbar (should NOT have Storyboard or Timeline buttons)
  console.log("\n--- SCRIPT WRITER TOOLBAR ---");
  if (await scriptTab.count() > 0) {
    await scriptTab.click({ timeout: 5000 });
    await page.waitForTimeout(2000);
    const toolbar = page.locator("[data-testid='scriptwriter-toolbar']").count();
    console.log("Script Writer toolbar:", toolbar > 0);
    // The Storyboard and Timeline buttons should be GONE
    const sbButton = page.locator("[data-testid='scriptwriter-toolbar'] button:has-text('Storyboard')").count();
    const tlButton = page.locator("[data-testid='scriptwriter-toolbar'] button:has-text('Timeline')").count();
    console.log("Storyboard button removed:", sbButton === 0);
    console.log("Timeline button removed:", tlButton === 0);
  }

  // API endpoint verification
  console.log("\n--- API ENDPOINT VERIFICATION ---");
  const projectId = "2347bf46-3762-4763-86c5-4a6032522278";

  // Foundation status
  try {
    const r = await page.request.get(`${API_BASE}/api/projects/${projectId}/foundation`);
    const f = await r.json();
    console.log("Foundation API:", `story=${f.story.status} script=${f.script.status} storyboard=${f.storyboard.status} characters=${f.characters.status}`);
  } catch (e) { console.log("Foundation API: FAILED", e.message); }

  // Context retriever (foundation)
  try {
    const r = await page.request.get(`${API_BASE}/api/codirector/projects/${projectId}/context?pillars=foundation`);
    const c = await r.json();
    console.log("Context foundation:", c.foundation ? `ready=${c.foundation.ready_for_timeline}` : "null");
  } catch (e) { console.log("Context API: FAILED", e.message); }

  // Context retriever (all pillars)
  try {
    const r = await page.request.get(`${API_BASE}/api/codirector/projects/${projectId}/context`);
    const c = await r.json();
    console.log("Context all:", `story=${c.story ? "yes" : "no"} script=${c.script ? "yes" : "no"} storyboard=${c.storyboard ? "yes" : "no"} characters=${c.characters ? "yes" : "no"}`);
  } catch (e) { console.log("Context all API: FAILED", e.message); }

  // Story endpoint
  try {
    const r = await page.request.get(`${API_BASE}/api/projects/${projectId}/story`);
    const s = await r.json();
    console.log("Story API:", `title="${s.title}" words=${s.wordCount}`);
  } catch (e) { console.log("Story API: FAILED", e.message); }

  // Persistence test — save story, reload, verify
  console.log("\n--- PERSISTENCE TEST ---");
  const testContent = `<h2>Test Heading</h2><p>This is a <strong>persistence test</strong> at ${Date.now()}.</p>`;
  try {
    const r = await page.request.put(`${API_BASE}/api/projects/${projectId}/story`, {
      data: { content: testContent, title: "Persistence Test" },
      headers: { "Content-Type": "application/json" },
    });
    const saved = await r.json();
    console.log("Story saved:", `words=${saved.wordCount}`);
  } catch (e) { console.log("Story save: FAILED", e.message); }

  // Reload story and verify
  try {
    const r = await page.request.get(`${API_BASE}/api/projects/${projectId}/story`);
    const loaded = await r.json();
    const matches = loaded.content === testContent;
    console.log("Story persistence:", matches ? "PASS" : "FAIL");
    if (!matches) console.log("  Expected:", testContent.substring(0, 80), "Got:", loaded.content?.substring(0, 80));
  } catch (e) { console.log("Story reload: FAILED", e.message); }

  // Refresh browser and verify project still visible
  console.log("\n--- REFRESH PERSISTENCE ---");
  await page.reload({ waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(3000);
  const afterReload = await page.textContent("body").catch(() => "");
  const projectsAfterReload = !afterReload?.includes("No Projects Yet");
  console.log("Projects after reload:", projectsAfterReload ? "PASS" : "FAIL");

  // 2-minute stability soak
  console.log("\n--- 2-MINUTE STABILITY SOAK ---");
  let apiCount = 0;
  page.on("request", (req) => { if (req.url().includes("/api/")) apiCount++; });
  await page.waitForTimeout(120000);
  console.log("API requests in 2 min:", apiCount);

  // Final summary
  console.log("\n=== CERTIFICATION SUMMARY ===");
  console.log("Console errors:", consoleErrors.length);
  console.log("CORS errors:", corsErrors.length);
  console.log("Request failures:", requestFailures.length);
  if (consoleErrors.length > 0) console.log("First 5 errors:", consoleErrors.slice(0, 5));
  if (requestFailures.length > 0) console.log("First 5 failures:", requestFailures.slice(0, 5));

  const result = {
    projectsVisible: hasProjects,
    projectsAfterReload,
    consoleErrors: consoleErrors.length,
    corsErrors: corsErrors.length,
    requestFailures: requestFailures.length,
    apiCountIn2Min: apiCount,
  };
  console.log("\nRESULT_JSON:", JSON.stringify(result));

  await page.close();
  await browser.close();
})();
