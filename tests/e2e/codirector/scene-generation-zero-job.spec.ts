import { expect, test, type APIRequestContext, type Page } from '@playwright/test';

const API = process.env.STUDIO_API_BASE || 'http://127.0.0.1:8758';
const SCHNICK = '2347bf46-3762-4763-86c5-4a6032522278';

async function startSceneGeneration(request: APIRequestContext, shotText = '') {
  const res = await request.post(`${API}/api/codirector/projects/${SCHNICK}/executions`, {
    data: {
      capability: 'scene.generate',
      context: {
        shot_requests_raw: shotText,
        ers_package_id: 'db095959-5678-4f11-98d1-e93e0810d119',
      },
    },
  });
  expect(res.ok(), `startExecution failed: ${await res.text()}`).toBeTruthy();
  return (await res.json()) as { execution_id: string; status: string; child_jobs: unknown[]; error?: string | null };
}

async function openCoDirector(page: Page) {
  await page.goto(`/co-director?projectId=${SCHNICK}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  // Either the project content pane or the work surface renders — wait for
  // whichever arrives first; the page must not stay blank.
  await expect(page.locator('[data-testid=codirector-project-content], [data-testid=agent-work-surface]').first()).toBeVisible({ timeout: 90000 });
  await page.waitForTimeout(4000);
}

test.describe('Co-Director Scene Generation 0/0 loop (Phase 22)', () => {
  test('ZERO SHOTS: dispatch returns a terminal failed plan — never queued 0/0', async ({ request }) => {
    const plan = await startSceneGeneration(request, '');
    expect(plan.status).not.toBe('queued');
    expect(plan.status).toBe('failed');
    expect(plan.child_jobs).toHaveLength(0);
    expect(plan.error).toContain('No valid scene-generation jobs');
    // advance must stay terminal (no spinner state)
    const adv = await request.post(`${API}/api/codirector/projects/${SCHNICK}/executions/${plan.execution_id}/advance`);
    expect(adv.ok()).toBeTruthy();
    expect((await adv.json()).status).toBe('failed');
  });

  test('VALID SHOTS: dispatch returns real jobs (not 0/0)', async ({ request }) => {
    const plan = await startSceneGeneration(request, '1. Korri behind the counter. 2. The empty café.');
    expect(plan.child_jobs.length).toBeGreaterThan(0);
    expect(plan.status).toBe('queued');
  });

  test('RELOAD: active/latest never rehydrates a zero-job phantom', async ({ request }) => {
    const res = await request.get(`${API}/api/codirector/projects/${SCHNICK}/executions/active/latest`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const exec = body.execution;
    // Either no active execution, or one that has real jobs.
    if (exec) {
      expect(exec.child_jobs.length).toBeGreaterThan(0);
      expect(['completed', 'failed', 'cancelled']).not.toContain(exec.status);
    }
  });

  test('UI: a zero-shot execution never renders a 0/0 spinner on the live Co-Director page', async ({ page, request }) => {
    // Create the phantom-triggering execution FIRST (terminal failed now).
    const plan = await startSceneGeneration(request, '');
    expect(plan.status).toBe('failed');
    await openCoDirector(page);
    // The zero-job execution is terminal — it must never reclaim the right
    // pane as a 0/0 spinner. A legitimately-active REAL execution (from the
    // soak) may show the surface with a real job count — that is fine.
    await page.waitForTimeout(8000);
    const surface = page.locator('[data-testid=agent-work-surface]');
    if (await surface.count()) {
      const text = (await surface.innerText()) || '';
      // ZERO-JOBS LAW: never '0 / 0' with a non-terminal progress line.
      expect(text).not.toMatch(/0 \/ 0/);
    }
  });
});
