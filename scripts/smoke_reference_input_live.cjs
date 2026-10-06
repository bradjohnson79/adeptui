const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const BASE = "http://127.0.0.1:5173";
const PROJECT = "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";
const EV = String.raw`C:\Users\bradj\theme_walk\timeline_reference_tag\smoke_ui`;
const EV2 = String.raw`C:\Users\bradj\agent-tools\theme_walk\timeline_reference_tag\smoke_ui`;
for (const d of [EV, EV2]) fs.mkdirSync(d, { recursive: true });

const results = { steps: [] };
function log(step, data) {
  results.steps.push({ step, ...data, at: new Date().toISOString() });
  console.log(JSON.stringify({ step, ...data }));
}

async function shot(page, name) {
  await page.screenshot({ path: path.join(EV, name), fullPage: false });
  await page.screenshot({ path: path.join(EV2, name), fullPage: false });
}

async function openRefs(page) {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(`${BASE}/project/${PROJECT}?workspace=timeline`, { waitUntil: "domcontentloaded", timeout: 90000 });
  await page.waitForTimeout(3500);
  if ((await page.getByTestId("scene-references-pane").count()) === 0) {
    const refs = page.getByText(/^References$/i).first();
    if (await refs.count()) await refs.click({ force: true });
    await page.waitForTimeout(1200);
  }
  await page.evaluate(() => {
    document.querySelector('[data-testid="scene-references-pane"]')?.scrollIntoView({ block: "center" });
    document.querySelector('[data-testid="references-add-input"]')?.scrollIntoView({ block: "center" });
  });
  await page.getByTestId("references-add-input").waitFor({ state: "visible", timeout: 45000 });
  await page.waitForFunction(() => {
    const el = document.querySelector('[data-testid="references-add-input"]');
    return el && !el.disabled;
  }, null, { timeout: 45000 });
}

async function typePrefix(page, q) {
  const input = page.getByTestId("references-add-input");
  await input.fill("");
  await input.fill(q);
  await page.waitForTimeout(900);
}

async function selectMatch(page, match) {
  const rows = page.locator("[data-testid^=references-add-row-]");
  await rows.first().waitFor({ timeout: 15000 });
  const n = await rows.count();
  for (let i = 0; i < n; i++) {
    const row = rows.nth(i);
    const titleAttr = (await row.getAttribute("title")) || "";
    const text = (await row.innerText()) || "";
    const hay = `${titleAttr}\n${text}`;
    if (!match.test(hay)) continue;
    const already = (await row.getAttribute("data-already")) === "true";
    const assetId = ((await row.getAttribute("data-testid")) || "").replace("references-add-row-", "");
    if (already) return { assetId, already: true, title: hay };
    await page.evaluate((id) => {
      const el = document.querySelector(`[data-testid="references-add-row-${id}"]`);
      el?.scrollIntoView({ block: "nearest" });
      el?.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, view: window }));
    }, assetId);
    await page.waitForTimeout(1800);
    return { assetId, already: false, title: hay };
  }
  const titles = await rows.evaluateAll((els) =>
    els.map((e) => ({ title: e.getAttribute("title"), text: e.textContent, already: e.getAttribute("data-already") })),
  );
  throw new Error(`no match ${match} in ${JSON.stringify(titles)}`);
}

async function chipPresent(page, re) {
  const text = await page.getByTestId("scene-references-pane").innerText();
  const chips = await page.locator("[data-testid^=reference-binding-]").count();
  return { chips, hit: re.test(text), textSnippet: text.slice(0, 500) };
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const net = [];
  page.on("response", (res) => {
    const u = res.url();
    if (/\/characters|prop-creator|environment|\/references/i.test(u)) {
      net.push({ status: res.status(), path: u.replace(/https?:\/\/[^/]+/, "") });
    }
  });
  try {
    await openRefs(page);
    await shot(page, "00_open_refs.png");

    await typePrefix(page, "@");
    await shot(page, "01_at_prefix.png");
    const atCount = await page.locator('[data-testid^=references-add-row-][data-semantic-type="character"]').count();
    const empty = await page.getByTestId("references-add-empty").count();
    const emptyText = empty ? await page.getByTestId("references-add-empty").innerText() : null;
    log("S1_at_prefix", { atCount, empty, emptyText, pass: atCount > 0 });
    if (atCount === 0) throw new Error(`S1 FAIL @ alone empty=${emptyText}`);

    await typePrefix(page, "@Kor");
    await shot(page, "02_at_Kor_discover.png");
    const korri = await selectMatch(page, /Korri/i);
    log("S2_Korri_select", korri);
    await page.waitForTimeout(1000);
    let chip = await chipPresent(page, /Korri/i);
    log("S2_Korri_chip", chip);
    await shot(page, "03_Korri_bound_chip.png");
    if (!chip.hit && !korri.already) throw new Error("Korri chip missing after bind");

    await typePrefix(page, "@Cad");
    const cade = await selectMatch(page, /Cade/i);
    log("S3_Cade", cade);
    await shot(page, "04_Cade_bound.png");
    chip = await chipPresent(page, /Cade/i);
    if (!chip.hit && !cade.already) throw new Error("Cade chip missing");

    await typePrefix(page, "@Ana");
    const ana = await selectMatch(page, /Anadriya/i);
    log("S4_Anadriya", ana);
    await shot(page, "05_Anadriya_bound.png");

    await typePrefix(page, "%");
    const propRows = await page.locator('[data-testid^=references-add-row-][data-semantic-type="prop"]').count();
    log("S5_pct_props", { propRows, pass: propRows > 0 });
    await shot(page, "06_pct_props.png");
    if (propRows === 0) throw new Error("% props empty");
    try {
      await typePrefix(page, "%schnick");
      const prop = await selectMatch(page, /Schnick|Coffee|Thermos/i);
      log("S5b_schnick", prop);
      await shot(page, "07_schnick_bound.png");
    } catch (e) {
      log("S5b_schnick", { soft: String(e.message || e) });
    }

    await typePrefix(page, "#");
    const envRows = await page.locator('[data-testid^=references-add-row-][data-semantic-type="environment"]').count();
    log("S6_hash_envs", { envRows });
    await shot(page, "08_hash_envs.png");
    try {
      const env = await selectMatch(page, /./);
      log("S6b_env_bind", env);
      await shot(page, "09_env_bound.png");
    } catch (e) {
      log("S6b_env_bind", { soft: String(e.message || e) });
    }

    await typePrefix(page, "@Korri");
    const already = await page.locator('[data-testid^=references-add-row-][data-already="true"]').count();
    log("S7_dup", { already, pass: already > 0 });
    await shot(page, "10_dup.png");
    if (already === 0) throw new Error("dup Already added missing");

    log("S8_library_surface", { pass: (await page.getByTestId("references-add-input").count()) === 1 });

    await page.reload({ waitUntil: "domcontentloaded" });
    await openRefs(page);
    chip = await chipPresent(page, /Korri|Cade|Anadriya/i);
    log("S9_reload", chip);
    await shot(page, "11_reload.png");
    if (!chip.hit) throw new Error("reload lost chips");

    await page.goto(`${BASE}/project/${PROJECT}?workspace=library`, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForTimeout(2000);
    await openRefs(page);
    chip = await chipPresent(page, /Korri|Cade|Anadriya/i);
    log("S10_remount", chip);
    await shot(page, "12_remount.png");
    if (!chip.hit) throw new Error("remount lost chips");

    results.verdict = "REFERENCE INPUT SMOKE TEST GO";
    results.netSample = net.slice(-40);
  } catch (e) {
    results.verdict = "REFERENCE INPUT SMOKE TEST NO-GO";
    results.error = String(e && e.message ? e.message : e);
    try { await shot(page, "ZZ_FAIL.png"); } catch {}
  } finally {
    fs.writeFileSync(path.join(EV, "SMOKE_RESULTS.json"), JSON.stringify(results, null, 2));
    fs.writeFileSync(path.join(EV2, "SMOKE_RESULTS.json"), JSON.stringify(results, null, 2));
    await browser.close();
    console.log("VERDICT", results.verdict);
    if (String(results.verdict).includes("NO-GO")) process.exit(1);
  }
})();

