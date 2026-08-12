/**
 * Complete Companion & Production Intelligence live certification.
 * ADEPT_BETA_TARGET=1, real model, Dreamweaver by exact name, retries=0, workers=1.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext } from "@playwright/test";
import { API, BETA_TARGET, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import { openCoDirectorFullScreen, sendChatTurn } from "./helpers/audit";

const DREAMWEAVER_NAME = "The Dreamweaver";
const LIVE_FAILURE =
  "I will tell you all about The Dreamweaver as I’d like you to be familiar with the story before we move into production. Sound good?";
const TITLE_PREMISE_RE =
  /clear project title|one[- ]sentence (?:creative )?premise|what(?:'s| is) (?:the|your) (?:title|premise)/i;

const RUN_ID = `complete-companion-${new Date().toISOString().replace(/[:.]/g, "-")}`;
const ARTIFACT_DIR = path.join(
  process.cwd(),
  "docs",
  "release-gate",
  "co-director-companion",
  "artifacts",
  RUN_ID,
);

type StreamEvent = {
  type: string;
  content?: string;
  trace?: Record<string, unknown>;
  state?: Record<string, unknown>;
  support?: Record<string, unknown>;
  deviation?: Record<string, unknown>;
  advisory?: Record<string, unknown>;
  plan?: Record<string, unknown>;
};

function ensureDir() {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
}
function writeArtifact(name: string, data: unknown) {
  ensureDir();
  fs.writeFileSync(path.join(ARTIFACT_DIR, name), JSON.stringify(data, null, 2), "utf8");
}

async function resolveDreamweaver(request: APIRequestContext) {
  const res = await request.get(`${API}/api/projects`);
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  const projects = Array.isArray(body) ? body : body.projects || body.items || [];
  const byName = projects.find((p: { name?: string }) => p.name === DREAMWEAVER_NAME);
  expect(byName, "Dreamweaver project must exist").toBeTruthy();
  return byName as { id: string; name: string };
}

async function streamChat(
  request: APIRequestContext,
  projectId: string,
  messages: { role: string; content: string }[],
  model?: string | null,
) {
  const res = await request.post(`${API}/api/codirector/chat/stream`, {
    data: { messages, project_id: projectId, mode: "chat", model: model || undefined },
    timeout: 650_000,
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  const text = await res.text();
  const events: StreamEvent[] = [];
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed.startsWith("data:")) continue;
    const raw = trimmed.slice(5).trim();
    if (!raw) continue;
    try {
      events.push(JSON.parse(raw) as StreamEvent);
    } catch {
      /* ignore */
    }
  }
  const completed = [...events].reverse().find((e) => e.type === "completed");
  const trace = events.find((e) => e.type === "inference_trace")?.trace || null;
  return { events, reply: String(completed?.content || ""), trace };
}

test.describe("@critical @beta complete companion production intelligence cert", () => {
  test.skip(!BETA_TARGET, "Set ADEPT_BETA_TARGET=1 for live companion certification.");

  test("Stages 1–11 companion + operator + isolation", async ({ page, request }) => {
    test.setTimeout(900_000);
    await waitForAppReady(request);
    ensureDir();

    const health = await request.get(`${API}/api/codirector/providers/ollama/health`);
    expect(health.ok()).toBeTruthy();
    const healthBody = await health.json();
    writeArtifact("provider-health.json", healthBody);
    const selectedModel = healthBody.selectedModel || healthBody.selected_model;
    expect(selectedModel).toBeTruthy();

    const project = await resolveDreamweaver(request);
    expect(project.name).toBe(DREAMWEAVER_NAME);
    writeArtifact("project.json", project);

    const transcript: { role: string; content: string }[] = [];

    // Stage 1 — Part A regression
    let turn = await streamChat(
      request,
      project.id,
      [{ role: "user", content: LIVE_FAILURE }],
      selectedModel,
    );
    writeArtifact("stage1-listening.json", turn);
    expect(turn.reply).not.toMatch(TITLE_PREMISE_RE);
    expect(Boolean(turn.trace?.fallback_used)).toBe(false);
    expect(String(turn.trace?.actual_model)).toBe(String(selectedModel));
    expect(String(turn.trace?.mode || "")).toMatch(/LISTENING|DISCOVERY/i);
    transcript.push({ role: "user", content: LIVE_FAILURE }, { role: "assistant", content: turn.reply });

    const lore =
      "The Dreamweaver follows a harbor child who hears a lantern call across tide-worn docks. " +
      "Season one stays tactile and mythic — no cyberpunk. Continuity matters: lantern light, salt air, and hand-built boats. " +
      "The central encounter with the lantern call is the emotional engine of the early arc.";
    turn = await streamChat(request, project.id, [...transcript, { role: "user", content: lore }], selectedModel);
    transcript.push({ role: "user", content: lore }, { role: "assistant", content: turn.reply });
    writeArtifact("stage1b-lore.json", { reply: turn.reply, trace: turn.trace });
    expect(turn.reply.toLowerCase()).toMatch(/harbor|lantern|mythic|tide|encounter|continuity|dock/);
    expect(turn.reply).not.toMatch(/Tell me about it in whatever order feels natural/i);

    // Stage 2 — strengths
    const strengthAsk = "Based on what you currently understand, what makes this story work?";
    turn = await streamChat(request, project.id, [...transcript, { role: "user", content: strengthAsk }], selectedModel);
    writeArtifact("stage2-strengths.json", turn);
    expect(turn.reply.toLowerCase()).toMatch(/story|tone|character|harbor|lantern|mythic|continuity|strength|work/);
    expect(turn.reply).not.toMatch(/you(?:'re| are) a genius|everything .+ excellent/i);
    transcript.push({ role: "user", content: strengthAsk }, { role: "assistant", content: turn.reply });

    // Stage 3 — discouragement
    const discouraged = "I’m beginning to wonder whether the story works at all.";
    turn = await streamChat(request, project.id, [...transcript, { role: "user", content: discouraged }], selectedModel);
    writeArtifact("stage3-discouragement.json", turn);
    expect(turn.reply).not.toMatch(/you(?:'re| are) a genius|believe in yourself/i);
    const supportEvt = turn.events.find((e) => e.type === "creative_support");
    expect(supportEvt?.support?.support_needed || turn.trace?.companion_need).toBeTruthy();
    transcript.push({ role: "user", content: discouraged }, { role: "assistant", content: turn.reply });

    // Stage 4 — local vs foundation
    const local =
      "One of the early scenes is moving too slowly, and I’m considering removing the central Dreamweaver encounter entirely.";
    turn = await streamChat(request, project.id, [...transcript, { role: "user", content: local }], selectedModel);
    writeArtifact("stage4-deviation.json", turn);
    expect(turn.reply).not.toMatch(TITLE_PREMISE_RE);
    const dev = turn.events.find((e) => e.type === "story_deviation")?.deviation;
    expect(dev?.triggered || turn.trace?.advisory_triggered).toBeTruthy();
    transcript.push({ role: "user", content: local }, { role: "assistant", content: turn.reply });

    // Stage 5 — exploration
    const explore = "I still want to explore the version without it.";
    turn = await streamChat(request, project.id, [...transcript, { role: "user", content: explore }], selectedModel);
    writeArtifact("stage5-explore.json", turn);
    expect(turn.reply.toLowerCase()).toMatch(/explor|variant|without|gain|loss|canon|not (?:yet )?chang/);
    const exploreState = String(turn.events.find((e) => e.type === "advisory_state")?.state || turn.trace?.decision_state || "");
    expect(exploreState).toMatch(/EXPLORATORY|ADVISED|TEST_VARIANT/i);
    expect(exploreState).not.toMatch(/USER_CONFIRMED_CHANGE|CANON_UPDATED/i);
    const exploreAdvisory = turn.events.find((e) => e.type === "advisory_state")?.advisory || turn.events.find((e) => e.type === "dialogue_plan")?.plan?.advisory;
    expect(Boolean(exploreAdvisory?.canon_write_allowed)).toBe(false);
    transcript.push({ role: "user", content: explore }, { role: "assistant", content: turn.reply });

    // Stage 6 — confirm keep original
    const confirm = "Keep the original encounter. Change the pacing and staging instead.";
    turn = await streamChat(request, project.id, [...transcript, { role: "user", content: confirm }], selectedModel);
    writeArtifact("stage6-confirm.json", turn);
    expect(turn.reply.toLowerCase()).toMatch(/pacing|staging|keep|original|encounter|collaborat|next/);
    transcript.push({ role: "user", content: confirm }, { role: "assistant", content: turn.reply });

    // Stage 7 — writer's block
    const stuck = "I’m stuck on how to make that revised scene move.";
    turn = await streamChat(request, project.id, [...transcript, { role: "user", content: stuck }], selectedModel);
    writeArtifact("stage7-block.json", turn);
    expect(turn.reply).not.toMatch(/here are ten ideas|1\)|2\)|3\)|4\)|5\)/i);
    transcript.push({ role: "user", content: stuck }, { role: "assistant", content: turn.reply });

    // Stage 8 — honest critique
    const critique = "Don’t encourage me in this answer. Be direct about what is weak in the current version.";
    turn = await streamChat(request, project.id, [...transcript, { role: "user", content: critique }], selectedModel);
    writeArtifact("stage8-critique.json", turn);
    expect(turn.reply).not.toMatch(/you(?:'re| are) doing (?:great|amazing)|don['’]?t worry/i);
    transcript.push({ role: "user", content: critique }, { role: "assistant", content: turn.reply });

    // Stage 9 — production operator transition
    const planAsk =
      "Draft a focused production plan for improving pacing and staging of that encounter — do not remove it. Ask before generating media.";
    turn = await streamChat(request, project.id, [...transcript, { role: "user", content: planAsk }], selectedModel);
    writeArtifact("stage9-operator.json", turn);
    expect(Boolean(turn.trace?.fallback_used)).toBe(false);
    expect(String(turn.trace?.mode || "")).toMatch(/PLANNING|EXECUTION|REVIEW/i);
    expect(String(turn.trace?.workflow_advance_policy || "")).toMatch(/ADVANCE|SUGGEST/i);
    expect(turn.reply).not.toMatch(/Absolutely — that is the right place to begin/i);
    expect(turn.reply.toLowerCase()).toMatch(/plan|pacing|staging|step|scene|approval|review/);
    transcript.push({ role: "user", content: planAsk }, { role: "assistant", content: turn.reply });

    // Stage 10 — UI reload (UI-sent turn must survive; API-only turns are not the UI transcript source)
    const uiReloadAsk = "Summarize the confirmed direction in one short paragraph.";
    await openCoDirectorFullScreen(page, project.id);
    const uiReloadReply = await sendChatTurn(page, uiReloadAsk);
    writeArtifact("stage10-ui-turn.json", { ask: uiReloadAsk, reply: uiReloadReply });
    await page.screenshot({ path: path.join(ARTIFACT_DIR, "ui-companion.png"), fullPage: true });
    await page.reload();
    await expect(page.getByTestId("codirector-composer-input")).toBeVisible({ timeout: 30_000 });
    await expect(
      page.locator(".codirector-msg.user .codirector-msg-bubble", { hasText: /Summarize the confirmed direction/i }).first(),
    ).toBeVisible({ timeout: 25_000 });

    // Durable companion memory must remain project-scoped after the live turns.
    const projectRes = await request.get(`${API}/api/projects/${project.id}`);
    expect(projectRes.ok(), await projectRes.text()).toBeTruthy();
    const projectBody = await projectRes.json();
    let companionSettings: Record<string, unknown> | null = null;
    try {
      const settings =
        typeof projectBody.settings_json === "string"
          ? JSON.parse(projectBody.settings_json || "{}")
          : projectBody.settings || projectBody.settings_json || {};
      companionSettings =
        settings && typeof settings === "object" ? (settings.companionIntelligence as Record<string, unknown>) : null;
    } catch {
      companionSettings = null;
    }
    writeArtifact("stage10-companion-settings.json", {
      hasCompanionIntelligence: Boolean(companionSettings),
      companionKeys: companionSettings ? Object.keys(companionSettings) : [],
      advisoryDecision: companionSettings?.advisoryDecision ?? null,
    });
    expect(companionSettings, "companionIntelligence must persist on Dreamweaver settings").toBeTruthy();

    // Stage 11 — isolation
    const other = await createTempProject(request, `Companion Isolation ${Date.now()}`);
    try {
      const iso = await streamChat(
        request,
        other.id,
        [{ role: "user", content: "What do you already know about my story?" }],
        selectedModel,
      );
      writeArtifact("stage11-isolation.json", { otherId: other.id, reply: iso.reply });
      expect(iso.reply.toLowerCase()).not.toMatch(/lantern call across tide-worn docks/);
    } finally {
      await deleteProject(request, other.id);
    }

    writeArtifact("verdict-seed.json", {
      runId: RUN_ID,
      projectId: project.id,
      selectedModel,
      actualModel: turn.trace?.actual_model,
      fallbackUsed: turn.trace?.fallback_used,
      artifactDir: ARTIFACT_DIR,
    });
  });
});
