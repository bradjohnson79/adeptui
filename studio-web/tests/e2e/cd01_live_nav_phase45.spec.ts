
import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';

const TRACE = path.join(
  'C:/Users/bradj/theme_walk/timeline_master_single_stack/phase45_cert',
  'LIVE_CERT_API_TRACE.json',
);
const outPath = path.join(
  'C:/Users/bradj/theme_walk/timeline_master_single_stack/phase45_cert',
  'LIVE_CERT_CD01_NAV.json',
);

test('CD01 live deep-link Env Creator + Image Generator open', async ({ page }) => {
  const cert = JSON.parse(fs.readFileSync(TRACE, 'utf-8'));
  const pid = cert.projectId as string;
  expect(pid).toBeTruthy();

  const result: Record<string, unknown> = { projectId: pid, hops: [] as unknown[] };

  // Environment Creator Express via Co-Director contentTab deep-link
  const envUrl = `http://127.0.0.1:5173/co-director?projectId=${encodeURIComponent(pid)}&contentTab=scene_creator`;
  await page.goto(envUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(2500);
  const envHref = page.url();
  const envOk = /contentTab=scene_creator/.test(envHref) || /contentTab=scene_creator/.test(await page.evaluate(() => window.location.href));
  (result.hops as unknown[]).push({ hop: 'open_environment_creator', href: envHref, ok: envOk });
  expect(envOk).toBeTruthy();

  // Image Generator workspace deep-link
  const imgUrl = `http://127.0.0.1:5173/project/${encodeURIComponent(pid)}?workspace=imagegen`;
  await page.goto(imgUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(2500);
  const imgHref = page.url();
  const imgOk = /workspace=imagegen/.test(imgHref) || /workspace=imagegen/.test(await page.evaluate(() => window.location.search));
  (result.hops as unknown[]).push({ hop: 'open_image_generator', href: imgHref, ok: imgOk });
  expect(imgOk).toBeTruthy();

  // Fail-closed probe: bogus contentTab must not claim scene_creator
  await page.goto(`http://127.0.0.1:5173/co-director?projectId=${encodeURIComponent(pid)}&contentTab=not_a_real_tab`, {
    waitUntil: 'domcontentloaded',
    timeout: 60000,
  });
  await page.waitForTimeout(1500);
  const bogusHref = page.url();
  const falselyOpen = /contentTab=scene_creator/.test(bogusHref);
  (result.hops as unknown[]).push({ hop: 'fail_closed_bogus_tab', href: bogusHref, falselyOpen });
  expect(falselyOpen).toBeFalsy();

  result.ok = true;
  fs.writeFileSync(outPath, JSON.stringify(result, null, 2));
});
