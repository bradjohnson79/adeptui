import AxeBuilder from "@axe-core/playwright";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { API, waitForAppReady } from "../helpers/app";
import { AuditObserver } from "../helpers/observer";

const ARTIFACT_DIR = path.join(
  "docs",
  "release-gate",
  "codirector-final",
  "artifacts",
  "prebeta-playwright",
);
const FIXTURE_DIR = path.join("tests", "e2e", "fixtures", "codirector-prebeta");
const DREAMWEAVER_NAME = "The Dreamweaver";

type ProjectSummary = {
  id: string;
  name: string;
  scenes?: Array<{ id: string; name: string }>;
};

type ProposalSummary = {
  id: string;
  status: string;
  title?: string;
  summary?: string;
};

function ensureArtifactDir() {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
}

function fixturePath(name: string) {
  return path.resolve(FIXTURE_DIR, name);
}

function artifactPath(name: string) {
  return path.join(ARTIFACT_DIR, name);
}

function timestampedIso(seed: number) {
  return new Date(seed).toISOString();
}

async function listProjects(request: APIRequestContext): Promise<ProjectSummary[]> {
  const res = await request.get(`${API}/api/projects`);
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  return Array.isArray(body) ? body : body.value || [];
}

async function deleteProject(request: APIRequestContext, projectId: string) {
  const res = await request.delete(`${API}/api/projects/${projectId}`);
  expect(res.ok(), await res.text()).toBeTruthy();
}

async function ensureSingleDreamweaverProject(request: APIRequestContext) {
  const before = await listProjects(request);
  const dreamweavers = before.filter((project) => project.name === DREAMWEAVER_NAME);
  expect(dreamweavers, `Expected exactly one ${DREAMWEAVER_NAME} project before certification.`).toHaveLength(1);
  for (const extra of before.filter((project) => project.name !== DREAMWEAVER_NAME)) {
    await deleteProject(request, extra.id);
  }
  const after = await listProjects(request);
  expect(after.map((project) => project.name)).toEqual([DREAMWEAVER_NAME]);
  return after[0];
}

async function saveConversation(
  request: APIRequestContext,
  projectId: string,
  messages: Array<{ role: "user" | "assistant"; content: string; created_at: string }>,
) {
  const res = await request.post(`${API}/api/codirector/conversations/${projectId}`, {
    data: {
      messages,
      model: "live-prebeta-cert",
      provider_id: "playwright-cert",
    },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
}

async function ensureBible(request: APIRequestContext, projectId: string) {
  const existing = await request.get(`${API}/api/codirector/projects/${projectId}/bible`);
  if (existing.ok()) {
    return;
  }
  expect(existing.status()).toBe(404);
  const previewRes = await request.post(`${API}/api/codirector/projects/${projectId}/bible/import/preview`, {
    data: {},
  });
  expect(previewRes.ok(), await previewRes.text()).toBeTruthy();
  const preview = await previewRes.json();
  const confirmRes = await request.post(`${API}/api/codirector/projects/${projectId}/bible/import/confirm`, {
    data: {
      entities: preview.entities,
      facts: preview.facts,
      summary: preview.summary,
    },
  });
  expect(confirmRes.ok(), await confirmRes.text()).toBeTruthy();
}

async function createPlanDraft(request: APIRequestContext, projectId: string, title: string) {
  const requestId = `prebeta-plan-${Date.now()}`;
  const res = await request.post(`${API}/api/codirector/projects/${projectId}/tools/audited`, {
    data: {
      toolId: "production_plan.create_draft",
      requestId,
      arguments: {
        title,
        objective: "Pre-beta certification flow",
        stepsJson: JSON.stringify([
          { stepId: "prep", title: "Verify project grounding", category: "research" },
          {
            stepId: "review",
            title: "Review approvals and exports",
            category: "director",
            dependsOn: ["prep"],
          },
        ]),
        requestId,
      },
    },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  expect(body.status).toBe("succeeded");
  return body.result?.plan || body.result;
}

async function createDecisionProposal(
  request: APIRequestContext,
  projectId: string,
  args: { decision: string; rationale: string; projectTitle?: string },
) {
  const res = await request.post(`${API}/api/codirector/projects/${projectId}/tools/proposals`, {
    data: {
      toolId: "record_production_decision",
      arguments: args,
      requestId: `prebeta-proposal-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      createdBy: "user",
    },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  return (await res.json()) as { id: string };
}

async function listProposals(request: APIRequestContext, projectId: string): Promise<ProposalSummary[]> {
  const res = await request.get(`${API}/api/codirector/projects/${projectId}/proposals`);
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  return body.proposals || [];
}

async function getProposalStatus(request: APIRequestContext, projectId: string, proposalId: string) {
  const proposals = await listProposals(request, projectId);
  const proposal = proposals.find((entry) => entry.id === proposalId);
  expect(proposal, `Proposal ${proposalId} not found.`).toBeTruthy();
  return proposal!.status;
}

async function uploadFixtureAsset(
  request: APIRequestContext,
  projectId: string,
  opts: { fixtureName: string; tag: string; kind: string; mimeType: string },
) {
  const buffer = fs.readFileSync(fixturePath(opts.fixtureName));
  const res = await request.post(`${API}/api/projects/${projectId}/assets`, {
    multipart: {
      file: {
        name: opts.fixtureName,
        mimeType: opts.mimeType,
        buffer,
      },
      tag: opts.tag,
      kind: opts.kind,
    },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  return res.json() as Promise<{ id: string; tag?: string; filename?: string }>;
}

async function saveExportArtifact(
  request: APIRequestContext,
  projectId: string,
  name: string,
  format: "pdf" | "html",
) {
  const route = format === "pdf" ? "pdf" : "html";
  const ext = format === "pdf" ? "pdf" : "zip";
  const res = await request.post(`${API}/api/codirector/projects/${projectId}/wiki/export/${route}`, {
    data: {
      exportTitle: name,
      includeCover: true,
      includeToc: true,
      includeOpenQuestions: true,
      includeUnresolved: true,
      includeImages: true,
      includeAudioVideo: true,
      includeProductionMetadata: true,
      sectionsMode: "selected",
      selectedSections: ["knownDetails", "creativeFoundation", "productionDecisions", "openQuestions"],
      sizeMode: "optimized",
    },
  });
  expect(res.ok()).toBeTruthy();
  const body = await res.body();
  const out = artifactPath(`${name}.${ext}`);
  fs.writeFileSync(out, body);
  return out;
}

async function openFullScreen(page: Page, projectId: string) {
  await page.goto(`/co-director?projectId=${encodeURIComponent(projectId)}`);
  await expect(
    page.getByTestId("codirector-fullscreen-shell").or(page.getByTestId("codirector-workspace")).first(),
  ).toBeVisible({ timeout: 45_000 });
  await expect(page.getByLabel("Message Co-Director")).toBeVisible({ timeout: 30_000 });
}

async function openContentTab(page: Page, tab: "wiki" | "library" | "plans" | "bible" | "approvals") {
  await page.getByTestId(`codirector-content-tab-${tab}`).click();
}

async function measureShell(page: Page) {
  return page.getByTestId("codirector-fullscreen-shell").evaluate((node) => {
    const rect = node.getBoundingClientRect();
    return {
      left: rect.left,
      right: window.innerWidth - rect.right,
      width: rect.width,
      viewportWidth: window.innerWidth,
      scrollWidth: document.documentElement.scrollWidth,
    };
  });
}

async function expectNinetyPercentLayout(page: Page) {
  const metrics = await measureShell(page);
  const widthRatio = metrics.width / metrics.viewportWidth;
  expect(widthRatio).toBeGreaterThanOrEqual(0.88);
  expect(widthRatio).toBeLessThanOrEqual(0.92);
  expect(metrics.left / metrics.viewportWidth).toBeGreaterThanOrEqual(0.04);
  expect(metrics.right / metrics.viewportWidth).toBeGreaterThanOrEqual(0.04);
  expect(metrics.scrollWidth).toBeLessThanOrEqual(metrics.viewportWidth + 2);
}

async function attachLibraryAssets(page: Page, query: string, tags: string[]) {
  await page.getByRole("button", { name: "Choose from Library" }).click();
  await expect(page.getByRole("dialog", { name: "Select Library assets" })).toBeVisible({ timeout: 20_000 });
  await page.getByLabel("Search assets").fill(query);
  for (const tag of tags) {
    const card = page.locator(".codirector-picker-card").filter({ hasText: tag }).first();
    await expect(card).toBeVisible({ timeout: 20_000 });
    await card.click();
    await expect(card.locator('input[type="checkbox"]')).toBeChecked();
  }
  await page.getByRole("button", { name: /Add .* selected/i }).click();
  await expect(page.getByRole("dialog", { name: "Select Library assets" })).toHaveCount(0);
  for (const tag of tags) {
    await expect(page.getByLabel("Attachments")).toContainText(tag);
  }
}

async function runUiExport(page: Page, format: "pdf" | "html") {
  await page.getByTestId("project-wiki-export-trigger").click();
  const dialog = page.getByTestId("project-wiki-export-dialog");
  await expect(dialog).toBeVisible({ timeout: 15_000 });
  if (format === "pdf") {
    await page.getByTestId("project-wiki-export-pdf").click();
    await page.getByTestId("project-wiki-run-export-pdf").click();
  } else {
    await page.getByTestId("project-wiki-export-html").click();
    await page.getByTestId("project-wiki-run-export-html").click();
  }
  await expect(dialog).toBeHidden({ timeout: 30_000 });
}

async function waitForAssistantTurn(page: Page) {
  await expect(page.locator(".codirector-msg.assistant .codirector-msg-bubble").last()).toContainText(/\S/, {
    timeout: 120_000,
  });
}

test.describe("@critical codirector prebeta live certification", () => {
  test.describe.configure({ mode: "serial" });

  test.beforeAll(async () => {
    ensureArtifactDir();
  });

  test("Dreamweaver pre-beta certification covers live creator workflow", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();

    await waitForAppReady(request);
    await page.setViewportSize({ width: 1440, height: 900 });

    const runId = `PB-${Date.now()}`;
    const markerA = `[${runId}] Conversation A - creator sets mythic tone.`;
    const markerB = `[${runId}] Conversation B - Co-Director reflects grounded notes.`;
    const markerC = `[${runId}] Conversation C - creator corrects a detail.`;
    const markerD = `[${runId}] Conversation D - creator confirms the next practical step.`;
    const approvedDecision = `[${runId}] Approved decision: the lantern call begins the opening movement.`;
    const rejectedDecision = `[${runId}] Rejected decision: the ending is already locked.`;
    const ambiguousDecision = `[${runId}] Ambiguous decision: either a cave or a watchtower can host the reveal.`;
    const clarifiedDecision = `[${runId}] Clarified decision: the reveal happens in a watchtower above the harbor.`;
    const planTitle = `${runId} Pre-Beta Certification Plan`;
    const imageTag = `${runId}-image`;
    const audioTag = `${runId}-audio`;
    const photoTag = `${runId}-photo`;
    const m214PlanFailures: Array<{ url: string; status: number }> = [];
    const codirectorHardApiFailures: Array<{ url: string; status: number }> = [];
    const codirectorHardConsoleFailures: string[] = [];
    let planWorkspaceLoaded = false;

    page.on("response", (response) => {
      const url = response.url();
      const status = response.status();
      if (url.includes("/api/codirector/m214/plan") && status >= 400) {
        m214PlanFailures.push({ url, status });
      }
      if (url.includes("/api/codirector/") && status >= 500) {
        codirectorHardApiFailures.push({ url, status });
      }
    });
    page.on("console", (msg) => {
      const text = msg.text();
      if (
        /project\.get_summary|project\.list_blockers|isn't a Co-Director tool|tool-registry|record_production_decision/i.test(
          text,
        )
      ) {
        codirectorHardConsoleFailures.push(text);
      }
    });

    const project = await ensureSingleDreamweaverProject(request);
    await ensureBible(request, project.id);
    const plan = await createPlanDraft(request, project.id, planTitle);
    const imageAsset = await uploadFixtureAsset(request, project.id, {
      fixtureName: "cert-image.png",
      tag: imageTag,
      kind: "image",
      mimeType: "image/png",
    });
    await uploadFixtureAsset(request, project.id, {
      fixtureName: "cert-photo.jpg",
      tag: photoTag,
      kind: "image",
      mimeType: "image/jpeg",
    });
    const audioAsset = await uploadFixtureAsset(request, project.id, {
      fixtureName: "cert-tone.wav",
      tag: audioTag,
      kind: "audio",
      mimeType: "audio/wav",
    });

    const seededAt = Date.now();
    await saveConversation(request, project.id, [
      { role: "user", content: markerA, created_at: timestampedIso(seededAt) },
      { role: "assistant", content: markerB, created_at: timestampedIso(seededAt + 1000) },
      { role: "user", content: markerC, created_at: timestampedIso(seededAt + 2000) },
      { role: "assistant", content: markerD, created_at: timestampedIso(seededAt + 3000) },
    ]);

    await openFullScreen(page, project.id);
    await expect(page.getByTestId("codirector-header-project")).toContainText(DREAMWEAVER_NAME);
    await expect(page.getByTestId("codirector-runtime-chip")).toBeVisible();
    await expect(page.getByTestId("codirector-no-project-banner")).toHaveCount(0);
    await expectNinetyPercentLayout(page);
    await page.screenshot({ path: artifactPath(`${runId}-01-fullscreen-shell.png`), fullPage: true });

    const chatText = await page.locator("body").innerText();
    expect(chatText).toContain(markerA);
    expect(chatText).toContain(markerB);
    expect(chatText).toContain(markerC);
    expect(chatText).toContain(markerD);

    await openContentTab(page, "wiki");
    await expect(page.getByTestId("codirector-project-wiki")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("codirector-project-wiki")).toContainText("Known Details");
    await expect(page.getByTestId("codirector-project-wiki")).toContainText("Creative Foundation");
    await page.screenshot({ path: artifactPath(`${runId}-02-wiki.png`), fullPage: true });

    await openContentTab(page, "library");
    await expect(page.getByTestId("codirector-retrieval-library")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("codirector-retrieval-library")).toContainText(/asset/i);
    await page.screenshot({ path: artifactPath(`${runId}-03-library.png`), fullPage: true });

    await openContentTab(page, "plans");
    await expect(page.getByTestId("codirector-content-plans")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("codirector-retrieval-plans")).toBeVisible({ timeout: 30_000 });
    planWorkspaceLoaded = await page
      .getByTestId("codirector-plan-workspace")
      .isVisible({ timeout: 20_000 })
      .catch(() => false);
    await page.screenshot({ path: artifactPath(`${runId}-04-plans.png`), fullPage: true });

    await openContentTab(page, "bible");
    await expect(page.locator("body")).toContainText(/Production Bible|Version 1 of/i, { timeout: 30_000 });
    await page.screenshot({ path: artifactPath(`${runId}-05-bible.png`), fullPage: true });

    await attachLibraryAssets(page, runId, [imageTag, audioTag]);
    await page.getByLabel("Message Co-Director").fill(`Please acknowledge the attached certification references for ${runId}.`);
    await page.getByRole("button", { name: "Send message" }).click();
    await expect(page.locator(".codirector-msg.user .codirector-msg-bubble").last()).toContainText(/\[Attached:/, {
      timeout: 20_000,
    });
    await waitForAssistantTurn(page);
    await page.screenshot({ path: artifactPath(`${runId}-06-attachments-and-chat.png`), fullPage: true });

    const approvedProposal = await createDecisionProposal(request, project.id, {
      decision: approvedDecision,
      rationale: "Certification approval path should persist a grounded production note.",
    });
    await openContentTab(page, "approvals");
    await page.reload();
    await openContentTab(page, "approvals");
    const approvedCard = page
      .getByTestId("codirector-approvals-panel")
      .getByTestId(`codirector-proposal-card-${approvedProposal.id}`);
    await expect(approvedCard).toBeVisible({ timeout: 30_000 });
    await approvedCard.getByRole("button", { name: "Approve" }).click();
    await expect.poll(async () => getProposalStatus(request, project.id, approvedProposal.id), { timeout: 30_000 }).toBe(
      "completed",
    );

    await openContentTab(page, "wiki");
    await expect(page.getByTestId("codirector-project-wiki")).toContainText(approvedDecision, { timeout: 30_000 });

    const rejectedProposal = await createDecisionProposal(request, project.id, {
      decision: rejectedDecision,
      rationale: "Certification rejection path should not leak wrong canon into the wiki.",
    });
    await page.reload();
    await openContentTab(page, "approvals");
    const rejectedCard = page
      .getByTestId("codirector-approvals-panel")
      .getByTestId(`codirector-proposal-card-${rejectedProposal.id}`);
    await expect(rejectedCard).toBeVisible({ timeout: 30_000 });
    await rejectedCard.getByRole("button", { name: "Reject" }).click();
    await expect.poll(async () => getProposalStatus(request, project.id, rejectedProposal.id), { timeout: 30_000 }).toBe(
      "rejected",
    );
    await openContentTab(page, "wiki");
    await expect(page.getByTestId("codirector-project-wiki")).not.toContainText(rejectedDecision);

    const ambiguousProposal = await createDecisionProposal(request, project.id, {
      decision: ambiguousDecision,
      rationale: "Certification ambiguity path should support request revision without applying.",
    });
    await page.reload();
    await openContentTab(page, "approvals");
    const ambiguousCard = page
      .getByTestId("codirector-approvals-panel")
      .getByTestId(`codirector-proposal-card-${ambiguousProposal.id}`);
    await expect(ambiguousCard).toBeVisible({ timeout: 30_000 });
    await ambiguousCard.locator("textarea").fill("Please pick one final location and remove the ambiguity.");
    await ambiguousCard.getByRole("button", { name: "Request Revision" }).click();
    await expect.poll(async () => getProposalStatus(request, project.id, ambiguousProposal.id), { timeout: 30_000 }).toBe(
      "revision_requested",
    );

    const clarifiedProposal = await createDecisionProposal(request, project.id, {
      decision: clarifiedDecision,
      rationale: "Certification correction path should persist the clarified version only.",
    });
    await page.reload();
    await openContentTab(page, "approvals");
    const clarifiedCard = page
      .getByTestId("codirector-approvals-panel")
      .getByTestId(`codirector-proposal-card-${clarifiedProposal.id}`);
    await expect(clarifiedCard).toBeVisible({ timeout: 30_000 });
    await clarifiedCard.getByRole("button", { name: "Approve" }).click();
    await expect.poll(async () => getProposalStatus(request, project.id, clarifiedProposal.id), { timeout: 30_000 }).toBe(
      "completed",
    );

    await openContentTab(page, "wiki");
    await expect(page.getByTestId("codirector-project-wiki")).toContainText(clarifiedDecision, { timeout: 30_000 });
    await expect(page.getByTestId("codirector-project-wiki")).not.toContainText(ambiguousDecision);
    await page.screenshot({ path: artifactPath(`${runId}-07-wiki-after-approvals.png`), fullPage: true });

    await runUiExport(page, "pdf");
    await runUiExport(page, "html");
    const pdfArtifact = await saveExportArtifact(request, project.id, `${runId}-dreamweaver-wiki`, "pdf");
    const htmlArtifact = await saveExportArtifact(request, project.id, `${runId}-dreamweaver-wiki`, "html");

    const axe = await new AxeBuilder({ page }).include('[data-testid="codirector-fullscreen-shell"]').analyze();
    const seriousOrCritical = axe.violations.filter((violation) => ["serious", "critical"].includes(violation.impact || ""));
    expect(seriousOrCritical, "Serious or critical Co-Director accessibility violations detected.").toEqual([]);

    await page.reload();
    await expect(page.getByTestId("codirector-header-project")).toContainText(DREAMWEAVER_NAME, { timeout: 30_000 });
    await expect(page.locator("body")).toContainText(markerA);
    await openContentTab(page, "wiki");
    await expect(page.getByTestId("codirector-project-wiki")).toContainText(approvedDecision);
    await expect(page.getByTestId("codirector-project-wiki")).toContainText(clarifiedDecision);
    await page.screenshot({ path: artifactPath(`${runId}-08-reload-persistence.png`), fullPage: true });

    expect(m214PlanFailures).toEqual([]);
    expect(codirectorHardApiFailures).toEqual([]);
    expect(codirectorHardConsoleFailures).toEqual([]);
    observer.assertHealthyBrowser();
    observer.flush();

    fs.writeFileSync(
      artifactPath(`${runId}-summary.json`),
      JSON.stringify(
        {
          runId,
          projectId: project.id,
          projectName: project.name,
          planId: plan.planId,
          planWorkspaceLoaded,
          uploadedAssets: [imageAsset.id, audioAsset.id],
          exports: {
            pdfArtifact,
            htmlArtifact,
          },
          approvals: {
            approvedProposal: approvedProposal.id,
            rejectedProposal: rejectedProposal.id,
            ambiguousProposal: ambiguousProposal.id,
            clarifiedProposal: clarifiedProposal.id,
          },
        },
        null,
        2,
      ),
    );
  });
});
