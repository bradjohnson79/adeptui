import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { inflateRawSync } from "node:zlib";
import { API, waitForAppReady } from "../helpers/app";
import { AuditObserver } from "../helpers/observer";

const ARTIFACT_DIR = path.join(
  "docs",
  "release-gate",
  "codirector-final",
  "artifacts",
  "prebeta-closure",
);
const FIXTURE_DIR = path.join("tests", "e2e", "fixtures", "codirector-prebeta");
const DREAMWEAVER_NAME = "The Dreamweaver";
const DREAMWEAVER_PROJECT_ID = "fcd7b4b0-7d36-4757-ac82-a701e6e1a50c";

type ProjectSummary = {
  id: string;
  name: string;
};

type ConversationAttachment = {
  assetId?: string;
  asset_id?: string;
  name?: string;
  mimeType?: string;
  mime_type?: string;
  kind?: string;
  source?: string;
};

type ConversationMessage = {
  id?: string;
  role: string;
  content: string;
  created_at?: string;
  attachmentIds?: string[];
  attachment_ids?: string[];
  attachments?: ConversationAttachment[];
};

type ZipEntry = {
  name: string;
  data: Buffer;
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

function listProjectsFromBody(body: unknown): ProjectSummary[] {
  return Array.isArray(body)
    ? (body as ProjectSummary[])
    : Array.isArray((body as { value?: unknown[] })?.value)
      ? ((body as { value: ProjectSummary[] }).value || [])
      : [];
}

async function listProjects(request: APIRequestContext): Promise<ProjectSummary[]> {
  const res = await request.get(`${API}/api/projects`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return listProjectsFromBody(await res.json());
}

async function ensureDreamweaverProject(request: APIRequestContext) {
  const projects = await listProjects(request);
  const exact = projects.find((project) => project.id === DREAMWEAVER_PROJECT_ID);
  if (exact) return { project: exact, created: false };
  const byName = projects.find((project) => project.name === DREAMWEAVER_NAME);
  if (byName) return { project: byName, created: false };
  const created = await request.post(`${API}/api/projects`, {
    data: { name: DREAMWEAVER_NAME },
  });
  expect(created.ok(), await created.text()).toBeTruthy();
  const project = (await created.json()) as ProjectSummary;
  return { project, created: true };
}

async function ensureBible(request: APIRequestContext, projectId: string) {
  const existing = await request.get(`${API}/api/codirector/projects/${projectId}/bible`);
  if (existing.ok()) return;
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
  const requestId = `prebeta-closure-plan-${Date.now()}`;
  const res = await request.post(`${API}/api/codirector/projects/${projectId}/tools/audited`, {
    data: {
      toolId: "production_plan.create_draft",
      requestId,
      arguments: {
        title,
        objective: "Pre-beta closure verification",
        stepsJson: JSON.stringify([
          { stepId: "inspect", title: "Inspect attached references", category: "research" },
          {
            stepId: "respond",
            title: "Prepare a grounded creator response",
            category: "director",
            dependsOn: ["inspect"],
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
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.body();
  const out = artifactPath(`${name}.${ext}`);
  fs.writeFileSync(out, body);
  return out;
}

async function getConversation(request: APIRequestContext, projectId: string) {
  const res = await request.get(`${API}/api/codirector/conversations/${projectId}`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return (await res.json()) as { messages: ConversationMessage[] };
}

function parseZipEntries(zipBuffer: Buffer): ZipEntry[] {
  const eocdSignature = 0x06054b50;
  let eocdOffset = -1;
  for (let index = zipBuffer.length - 22; index >= Math.max(0, zipBuffer.length - 65557); index -= 1) {
    if (zipBuffer.readUInt32LE(index) === eocdSignature) {
      eocdOffset = index;
      break;
    }
  }
  if (eocdOffset < 0) {
    throw new Error("Could not locate ZIP end-of-central-directory record.");
  }
  const entryCount = zipBuffer.readUInt16LE(eocdOffset + 10);
  const centralDirectoryOffset = zipBuffer.readUInt32LE(eocdOffset + 16);
  const entries: ZipEntry[] = [];
  let cursor = centralDirectoryOffset;
  for (let i = 0; i < entryCount; i += 1) {
    const centralSignature = zipBuffer.readUInt32LE(cursor);
    if (centralSignature !== 0x02014b50) {
      throw new Error(`Invalid central directory header at offset ${cursor}.`);
    }
    const compressionMethod = zipBuffer.readUInt16LE(cursor + 10);
    const compressedSize = zipBuffer.readUInt32LE(cursor + 20);
    const fileNameLength = zipBuffer.readUInt16LE(cursor + 28);
    const extraLength = zipBuffer.readUInt16LE(cursor + 30);
    const commentLength = zipBuffer.readUInt16LE(cursor + 32);
    const localHeaderOffset = zipBuffer.readUInt32LE(cursor + 42);
    const name = zipBuffer.toString("utf8", cursor + 46, cursor + 46 + fileNameLength);

    const localSignature = zipBuffer.readUInt32LE(localHeaderOffset);
    if (localSignature !== 0x04034b50) {
      throw new Error(`Invalid local header for ZIP member ${name}.`);
    }
    const localNameLength = zipBuffer.readUInt16LE(localHeaderOffset + 26);
    const localExtraLength = zipBuffer.readUInt16LE(localHeaderOffset + 28);
    const dataOffset = localHeaderOffset + 30 + localNameLength + localExtraLength;
    const compressed = zipBuffer.subarray(dataOffset, dataOffset + compressedSize);
    const data =
      compressionMethod === 0
        ? Buffer.from(compressed)
        : compressionMethod === 8
          ? inflateRawSync(compressed)
          : (() => {
              throw new Error(`Unsupported ZIP compression method ${compressionMethod} for ${name}.`);
            })();
    entries.push({ name, data });
    cursor += 46 + fileNameLength + extraLength + commentLength;
  }
  return entries;
}

function extractZipEntries(entries: ZipEntry[], targetDir: string) {
  for (const entry of entries) {
    const outPath = path.join(targetDir, ...entry.name.split("/"));
    if (entry.name.endsWith("/")) {
      fs.mkdirSync(outPath, { recursive: true });
      continue;
    }
    fs.mkdirSync(path.dirname(outPath), { recursive: true });
    fs.writeFileSync(outPath, entry.data);
  }
}

function detectPdfImageNote(pdfBytes: Buffer) {
  const text = pdfBytes.toString("latin1");
  if (/Image omitted from PDF because it could not be embedded safely\./i.test(text)) {
    return "PDF noted that an image was omitted because it could not be embedded safely.";
  }
  if (/Image omitted from PDF because the file bytes were not included in the export\./i.test(text)) {
    return "PDF noted that an image was omitted because the file bytes were not included.";
  }
  if (/metadata only in PDF\. Use the offline HTML export for the local file\./i.test(text)) {
    return "PDF included a metadata-only note for at least one media asset.";
  }
  return "No PDF omission marker was detected; binary inspection suggests the image was embedded or rasterized, but this is not definitive.";
}

test.describe("@critical codirector prebeta closure", () => {
  test.describe.configure({ mode: "serial" });

  test.beforeAll(() => {
    ensureArtifactDir();
  });

  test("direct upload, export hygiene, offline package, plans, and activity stay honest on live Beta", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();

    await waitForAppReady(request);
    await page.setViewportSize({ width: 1440, height: 900 });

    const runId = `PB-CLOSURE-${Date.now()}`;
    const planTitle = `${runId} Durable Closure Plan`;
    const prompt = `Plan the opening mood for ${runId} from the attached reference, explain it in creator-friendly language, and do not change project records.`;
    const exportStem = `${runId}-dreamweaver-closure`;
    const networkFailures: Array<{ url: string; status: number }> = [];
    const consoleFailures: string[] = [];

    page.on("response", (response) => {
      const url = response.url();
      if (url.includes("/api/codirector/m214/plan") && response.status() >= 400) {
        networkFailures.push({ url, status: response.status() });
      }
    });
    page.on("console", (msg) => {
      const text = msg.text();
      if (/project\.get_summary|project\.list_blockers|tool-registry|isn't a Co-Director tool|m214\/plan/i.test(text)) {
        consoleFailures.push(text);
      }
    });

    const { project, created } = await ensureDreamweaverProject(request);
    await ensureBible(request, project.id);
    const plan = await createPlanDraft(request, project.id, planTitle);

    await openFullScreen(page, project.id);
    await expect(page.getByTestId("codirector-header-project")).toContainText(DREAMWEAVER_NAME);

    await openContentTab(page, "plans");
    await expect(page.getByTestId("codirector-content-plans")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("codirector-plan-workspace")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("codirector-plan-workspace")).toContainText(planTitle);
    await page.screenshot({ path: artifactPath(`${runId}-01-plans.png`), fullPage: true });

    const uniqueUploadPath = artifactPath(`${runId}-closure-upload.png`);
    fs.copyFileSync(fixturePath("closure-upload.png"), uniqueUploadPath);
    const uploadName = path.basename(uniqueUploadPath);
    await page.getByTestId("codirector-file-input").setInputFiles(uniqueUploadPath);
    const tray = page.getByTestId("codirector-attachment-tray");
    await expect(tray).toBeVisible({ timeout: 15_000 });
    await expect(tray).toContainText(uploadName);
    await page.screenshot({ path: artifactPath(`${runId}-02-attachment-tray.png`), fullPage: true });

    await page.getByLabel("Message Co-Director").fill(prompt);
    const assistantCountBefore = await page.locator(".codirector-msg.assistant").count();
    await page.getByRole("button", { name: "Send message" }).click();
    const activityPanel = page.getByTestId("codirector-activity-panel");
    await expect(activityPanel).toBeVisible({ timeout: 20_000 });
    await expect(activityPanel).toContainText(/Understanding/i, { timeout: 20_000 });
    await expect(page.locator(".codirector-msg.user .codirector-msg-bubble").last()).toContainText(
      new RegExp(`Attached: ${runId}-closure-upload\\.png`, "i"),
      { timeout: 20_000 },
    );
    await expect
      .poll(async () => page.locator(".codirector-msg.assistant").count(), { timeout: 120_000 })
      .toBeGreaterThan(assistantCountBefore);
    await expect(activityPanel.getByRole("button", { name: "View activity" })).toBeVisible({ timeout: 30_000 });
    await page.screenshot({ path: artifactPath(`${runId}-03-post-send.png`), fullPage: true });

    await expect(activityPanel.locator(".codirector-activity-list")).toHaveCount(0);
    await activityPanel.getByRole("button", { name: "View activity" }).click();
    await expect(activityPanel.locator(".codirector-activity-list")).toBeVisible();
    const activityText = await activityPanel.innerText();
    expect(activityText).not.toMatch(/\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/i);
    expect(activityText).not.toMatch(/project\.get_summary|project\.list_blockers|record_production_decision|toolId/i);
    expect(activityText).not.toMatch(/^\s*[{[]/m);
    await activityPanel.getByRole("button", { name: "What Co-Director considered" }).click();
    await expect(activityPanel).toContainText(/Worked from the current conversation|Used the current project context/i);
    await page.screenshot({ path: artifactPath(`${runId}-04-activity.png`), fullPage: true });

    const conversation = await getConversation(request, project.id);
    const persistedUserMessage = [...conversation.messages]
      .reverse()
      .find((message) => message.role === "user" && message.content.includes(runId));
    expect(persistedUserMessage, `Expected a persisted user message for ${runId}.`).toBeTruthy();
    const persistedAttachments = persistedUserMessage?.attachments || [];
    expect(persistedAttachments.length).toBeGreaterThan(0);
    const persistedAttachment = persistedAttachments.find((item) => item.name === uploadName) || persistedAttachments[0];
    const assetId = String(persistedAttachment.assetId || persistedAttachment.asset_id || "").trim();
    expect(assetId).toBeTruthy();
    const assetFile = await request.get(`${API}/api/assets/${assetId}/file`);
    expect(assetFile.ok(), await assetFile.text()).toBeTruthy();

    await openContentTab(page, "wiki");
    await expect(page.getByTestId("codirector-project-wiki")).toBeVisible({ timeout: 30_000 });
    await runUiExport(page, "pdf");
    await runUiExport(page, "html");
    const pdfArtifact = await saveExportArtifact(request, project.id, exportStem, "pdf");
    const htmlArtifact = await saveExportArtifact(request, project.id, exportStem, "html");

    const pdfBytes = fs.readFileSync(pdfArtifact);
    expect(pdfBytes.subarray(0, 4).toString()).toBe("%PDF");
    const pdfImageNote = detectPdfImageNote(pdfBytes);

    const zipEntries = parseZipEntries(fs.readFileSync(htmlArtifact));
    expect(zipEntries.length).toBeGreaterThan(0);
    const wikiJsonEntry = zipEntries.find((entry) => entry.name.endsWith("/data/wiki.json"));
    expect(wikiJsonEntry, "Offline HTML export is missing data/wiki.json.").toBeTruthy();
    const payload = JSON.parse((wikiJsonEntry as ZipEntry).data.toString("utf-8")) as {
      assets?: Array<Record<string, unknown>>;
      warnings?: string[];
    };
    const assets = Array.isArray(payload.assets) ? payload.assets : [];
    expect(assets.length).toBeGreaterThan(0);
    const runAsset =
      assets.find((asset) => String(asset.title || asset.caption || "").includes(runId)) ||
      assets.find((asset) => String(asset.relativePath || "").includes(runId));
    expect(runAsset, `Expected an exported asset scoped to ${runId}.`).toBeTruthy();
    for (const asset of assets) {
      const relativePath = String(asset.relativePath || "");
      if (!relativePath) continue;
      expect(
        zipEntries.some((entry) => entry.name.endsWith(relativePath)),
        `Expected offline HTML archive member for ${relativePath}.`,
      ).toBeTruthy();
    }

    const scannedText = zipEntries
      .filter((entry) => /\.(css|html|js|json|md|txt)$/i.test(entry.name))
      .map((entry) => entry.data.toString("utf-8"))
      .join("\n");
    const scannedNames = zipEntries.map((entry) => entry.name).join("\n");
    const exportScan = `${scannedNames}\n${scannedText}`;
    const forbiddenPatterns: Array<{ label: string; pattern: RegExp }> = [
      { label: "Windows user path", pattern: /C:\\Users\\/i },
      { label: "Absolute Windows path", pattern: /\b[A-Z]:\\(?:[^\\\r\n]+\\)+[^\\\r\n]*/i },
      { label: "Absolute macOS path", pattern: /\/Users\/[^\s"'<>]+/i },
      { label: "UUID", pattern: /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/i },
      { label: "Raw tool id", pattern: /\bproject\.(get_summary|list_blockers)\b/i },
      { label: "Decision tool id", pattern: /\brecord_production_decision\b/i },
      { label: "Tool registry leak", pattern: /\btool-registry\b/i },
    ];
    for (const { label, pattern } of forbiddenPatterns) {
      expect(exportScan, `Forbidden export text detected: ${label}`).not.toMatch(pattern);
    }

    const extractRoot = artifactPath(`${runId}-offline`);
    fs.rmSync(extractRoot, { recursive: true, force: true });
    extractZipEntries(zipEntries, extractRoot);
    const archiveRootName = (wikiJsonEntry as ZipEntry).name.split("/")[0];
    const offlineRoot = path.join(extractRoot, archiveRootName);
    const offlinePage = await page.context().newPage();
    const offlineHttpRequests: string[] = [];
    offlinePage.on("request", (req) => {
      if (/^https?:/i.test(req.url())) {
        offlineHttpRequests.push(req.url());
      }
    });
    await offlinePage.goto(pathToFileURL(path.join(offlineRoot, "index.html")).href);
    await expect(offlinePage.locator("#media-section")).toBeVisible({ timeout: 30_000 });
    const runAssetAlt = String((runAsset as Record<string, unknown>).alt || "");
    const offlineImage = runAssetAlt
      ? offlinePage.getByRole("img", { name: runAssetAlt })
      : offlinePage.locator("#media-grid img").first();
    await expect(offlineImage).toBeVisible({ timeout: 30_000 });
    const imageState = await offlineImage.evaluate((node: HTMLImageElement) => ({
      complete: node.complete,
      naturalWidth: node.naturalWidth,
      naturalHeight: node.naturalHeight,
    }));
    expect(imageState.complete).toBeTruthy();
    expect(imageState.naturalWidth).toBeGreaterThan(0);
    expect(imageState.naturalHeight).toBeGreaterThan(0);
    expect(offlineHttpRequests).toEqual([]);
    await offlinePage.screenshot({ path: artifactPath(`${runId}-05-offline-html.png`), fullPage: true });
    await offlinePage.close();

    await page.reload();
    await expect(page.getByTestId("codirector-header-project")).toContainText(DREAMWEAVER_NAME, { timeout: 30_000 });
    const latestUserBubble = page.locator(".codirector-msg.user .codirector-msg-bubble").last();
    await expect(latestUserBubble).toContainText(new RegExp(runId));
    await expect(latestUserBubble).toContainText(new RegExp(`Attached: ${runId}-closure-upload\\.png`, "i"));
    await openContentTab(page, "plans");
    await expect(page.getByTestId("codirector-plan-workspace")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("codirector-plan-workspace")).toContainText(planTitle);
    await page.screenshot({ path: artifactPath(`${runId}-06-reload.png`), fullPage: true });

    expect(networkFailures).toEqual([]);
    expect(consoleFailures).toEqual([]);
    observer.assertHealthyBrowser();
    observer.flush();

    fs.writeFileSync(
      artifactPath(`${runId}-summary.json`),
      JSON.stringify(
        {
          runId,
          projectId: project.id,
          projectName: project.name,
          dreamweaverCreatedThisRun: created,
          planId: plan.planId,
          directUploadAssetId: assetId,
          uploadName,
          persistedAttachmentNames: persistedAttachments.map((attachment) => attachment.name || null),
          htmlArtifact,
          pdfArtifact,
          htmlAssetsCount: assets.length,
          htmlWarnings: Array.isArray(payload.warnings) ? payload.warnings : [],
          pdfImageNote,
          runAssetTitle: runAsset ? String((runAsset as Record<string, unknown>).title || "") : null,
        },
        null,
        2,
      ),
    );
  });
});
