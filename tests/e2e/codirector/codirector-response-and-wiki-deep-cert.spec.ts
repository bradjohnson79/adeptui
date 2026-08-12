/**
 * Co-Director Response Experience & Wiki Intelligence deep cert.
 * ADEPT_BETA_TARGET=1, workers=1, retries=0. Cert project: The Dreamweaver (or ADEPT_PROJECT_ID).
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext } from "@playwright/test";
import { API, BETA_TARGET, waitForAppReady } from "../helpers/app";
import { openCoDirectorFullScreen } from "./helpers/audit";

const PROJECT_NAME = "The Dreamweaver";
const ARTIFACT_DIR = path.join(
  process.cwd(),
  "docs/release-gate/co-director-response-wiki/artifacts",
);

type StreamEvent = {
  type: string;
  content?: string;
  replace?: boolean;
  stage?: string;
  jobType?: string;
  status?: string;
  verification?: Record<string, unknown>;
  message?: string;
};

function ensureDir() {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
}
function writeArtifact(name: string, data: unknown) {
  ensureDir();
  fs.writeFileSync(path.join(ARTIFACT_DIR, name), JSON.stringify(data, null, 2), "utf8");
}

async function resolveProject(request: APIRequestContext) {
  const forced = (process.env.ADEPT_PROJECT_ID || "").trim();
  if (forced) {
    const res = await request.get(`${API}/api/projects/${forced}`);
    if (res.ok()) {
      const body = await res.json();
      return { id: String(body.id || forced), name: String(body.name || PROJECT_NAME) };
    }
  }
  const res = await request.get(`${API}/api/projects`);
  expect(res.ok()).toBeTruthy();
  const body = await res.json();
  const projects = Array.isArray(body) ? body : body.projects || body.items || [];
  const named = projects.find((p: { name?: string }) => p.name === PROJECT_NAME);
  expect(named, `${PROJECT_NAME} must exist`).toBeTruthy();
  return named as { id: string; name: string };
}

async function streamChat(projectId: string, content: string) {
  const events: StreamEvent[] = [];
  const controller = new AbortController();
  const kill = setTimeout(() => controller.abort(), 240_000);
  try {
    const res = await fetch(`${API}/api/codirector/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({
        messages: [{ role: "user", content }],
        project_id: projectId,
        mode: "chat",
      }),
      signal: controller.signal,
    });
    expect(res.ok, `HTTP ${res.status}`).toBeTruthy();
    const reader = res.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split(/\r?\n/);
      buffer = parts.pop() || "";
      for (const block of parts) {
        const line = block.trim();
        if (!line.startsWith("data:")) continue;
        const raw = line.slice(5).trim();
        if (!raw || raw === "[DONE]") continue;
        try {
          events.push(JSON.parse(raw) as StreamEvent);
        } catch {
          /* ignore */
        }
      }
    }
  } finally {
    clearTimeout(kill);
  }
  const completed = [...events].reverse().find((e) => e.type === "completed");
  return { events, reply: String(completed?.content || "") };
}

const LEAK_RE =
  /here'?s a thinking process|analyze user input|draft construction|constraint check|question budget|system prompt/i;

test.describe.configure({ mode: "serial", retries: 0 });

test.describe("@critical @beta codirector response and wiki deep cert", () => {
  test.skip(!BETA_TARGET, "Set ADEPT_BETA_TARGET=1");

  test("response isolation + wiki rebuild + UI visibility", async ({ page, request }) => {
    test.setTimeout(900_000);
    await waitForAppReady(request);
    ensureDir();
    const project = await resolveProject(request);
    writeArtifact("project.json", project);

    // Remediate any historical reasoning leaks first.
    const remediate = await request.post(
      `${API}/api/codirector/projects/${project.id}/conversation/remediate-reasoning`,
    );
    expect(remediate.ok()).toBeTruthy();
    const remediateBody = await remediate.json();
    writeArtifact("reasoning_remediation.json", remediateBody);
    expect(remediateBody.gate).toBe("EXISTING_REASONING_LEAK_REMEDIATED");
    expect(remediateBody.pass).toBeTruthy();

    // Multi-domain conversation turns (live model).
    const domains: { name: string; prompt: string }[] = [
      {
        name: "story",
        prompt:
          "Story update: in episode three the anteroom floods with borrowed memories and Korri must choose which one to return. Keep listening — no draft yet.",
      },
      {
        name: "character",
        prompt:
          "Character note: Korri Vale is sarcastic under pressure but protective of strangers who hear the Signal. She never wants to become an archive clerk.",
      },
      {
        name: "world",
        prompt:
          "World rule: Continuum Guild clerks may stamp a past only once per night, and rewriting a living dream without consent is forbidden.",
      },
      {
        name: "treatment",
        prompt:
          "I'd like a short working treatment spine later — for now just acknowledge that the treatment should open on the flooded anteroom and end on Korri refusing the clerk's stamp.",
      },
    ];

    const domainResults: Record<string, unknown>[] = [];
    for (const domain of domains) {
      const turn = await streamChat(project.id, domain.prompt);
      expect(turn.reply.trim().length, `${domain.name} reply`).toBeGreaterThan(20);
      expect(LEAK_RE.test(turn.reply), `${domain.name} must not leak reasoning`).toBeFalsy();
      domainResults.push({
        domain: domain.name,
        replyPreview: turn.reply.slice(0, 400),
        leak: LEAK_RE.test(turn.reply),
        wikiStatus: turn.events.find((e) => e.type === "wiki_status") || null,
      });
      await new Promise((r) => setTimeout(r, 1500));
    }
    writeArtifact("domain_turns.json", domainResults);

    // Generic Rebuild Wiki path (not Dreamweaver-only).
    const rebuild = await request.post(`${API}/api/codirector/projects/${project.id}/wiki/rebuild`);
    expect(rebuild.ok()).toBeTruthy();
    const rebuildBody = await rebuild.json();
    writeArtifact("wiki_rebuild.json", rebuildBody);
    expect(rebuildBody.ok).toBeTruthy();
    const states = rebuildBody.verification?.states || {};
    expect(states.PERSISTED === true || rebuildBody.wikiHasContent === true).toBeTruthy();

    const diagnostic = await request.get(`${API}/api/codirector/projects/${project.id}/wiki/diagnostic`);
    expect(diagnostic.ok()).toBeTruthy();
    const diagnosticBody = await diagnostic.json();
    writeArtifact("wiki_diagnostic.json", diagnosticBody);
    expect(diagnosticBody.ok).toBeTruthy();

    const wikiApi = await request.get(`${API}/api/codirector/projects/${project.id}/wiki`);
    expect(wikiApi.ok()).toBeTruthy();
    const wikiBody = await wikiApi.json();
    writeArtifact("wiki_api.json", {
      hasContent: wikiBody.hasContent,
      toc: wikiBody.toc,
      sourceOfTruth: wikiBody.sourceOfTruth,
      sectionCounts: Object.fromEntries(
        Object.entries(wikiBody.sections || {}).map(([k, v]) => [
          k,
          Array.isArray((v as { entries?: unknown[] }).entries)
            ? (v as { entries: unknown[] }).entries.length
            : 0,
        ]),
      ),
    });
    expect(wikiBody.hasContent).toBeTruthy();
    expect(wikiBody.sourceOfTruth).toContain("knowledgeEntries");
    expect(Array.isArray(wikiBody.toc) ? wikiBody.toc.length : 0).toBeGreaterThan(0);

    // UI: open Co-Director, Wiki tab, rebuild control, TOC, context panel.
    await openCoDirectorFullScreen(page, project.id);
    await page.getByTestId("codirector-content-tab-wiki").click();
    await expect(page.getByTestId("project-wiki-rebuild")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("project-wiki-diagnostic")).toBeVisible();
    const wikiPanel = page.getByTestId("codirector-project-wiki");
    await expect(wikiPanel).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("project-wiki-toc")).toBeVisible();
    await page.screenshot({ path: path.join(ARTIFACT_DIR, "wiki_ui.png") });

    // Click first entry if present for context panel.
    const firstEntry = page.locator(".codirector-project-wiki-list li").first();
    if (await firstEntry.count()) {
      await firstEntry.click();
      await expect(page.getByTestId("project-wiki-context-panel")).toBeVisible({ timeout: 10_000 });
      await page.screenshot({ path: path.join(ARTIFACT_DIR, "wiki_context_panel.png") });
    }

    // Reload survival
    await page.reload();
    await openCoDirectorFullScreen(page, project.id);
    await page.getByTestId("codirector-content-tab-wiki").click();
    await expect(page.getByTestId("codirector-project-wiki")).toBeVisible({ timeout: 30_000 });
    await page.screenshot({ path: path.join(ARTIFACT_DIR, "wiki_reload.png") });

    writeArtifact("cert_summary.json", {
      projectId: project.id,
      remediationGate: remediateBody.gate,
      wikiHasContent: wikiBody.hasContent,
      tocCount: (wikiBody.toc || []).length,
      rebuildStates: states,
      domainsCovered: domains.map((d) => d.name),
      noReasoningLeakInReplies: domainResults.every((r) => !(r as { leak?: boolean }).leak),
    });
  });
});
