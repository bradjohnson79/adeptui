/**
 * Part A live certification — Co-Director foundational listening intelligence.
 *
 * Requires ADEPT_BETA_TARGET=1 / Beta on 8760+8758 with a real selected model.
 * Protected project: The Dreamweaver / fcd7b4b0-7d36-4757-ac82-a701e6e1a50c
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext } from "@playwright/test";
import { API, BETA_TARGET, waitForAppReady } from "../helpers/app";
import { openCoDirectorFullScreen, sendChatTurn } from "./helpers/audit";

const DREAMWEAVER_NAME = "The Dreamweaver";
const DREAMWEAVER_PROJECT_ID = "fcd7b4b0-7d36-4757-ac82-a701e6e1a50c";

const LIVE_FAILURE =
  "I will tell you all about The Dreamweaver as I’d like you to be familiar with the story before we move into production. Sound good?";

const PARAPHRASES = [
  "Before we do anything else, I want to explain the story to you.",
  "Let me give you the background first, and please just listen for now.",
  "Don’t organize this yet—I just want to tell you what it is.",
];

const TITLE_PREMISE_RE =
  /clear project title|one[- ]sentence (?:creative )?premise|what(?:'s| is) (?:the|your) (?:title|premise)/i;

const RUN_ID = `foundational-ai-${new Date().toISOString().replace(/[:.]/g, "-")}`;
const ARTIFACT_DIR = path.join(
  process.cwd(),
  "docs",
  "release-gate",
  "co-director-foundation",
  "artifacts",
  RUN_ID,
);

type StreamEvent = {
  type: string;
  content?: string;
  trace?: Record<string, unknown>;
  state?: Record<string, unknown>;
  model?: string;
  modelId?: string;
  providerId?: string;
  fallbackUsed?: boolean;
  intent?: Record<string, unknown>;
  plan?: Record<string, unknown>;
};

function ensureArtifactDir() {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
}

function writeArtifact(name: string, data: unknown) {
  ensureArtifactDir();
  fs.writeFileSync(path.join(ARTIFACT_DIR, name), JSON.stringify(data, null, 2), "utf8");
}

async function resolveDreamweaver(request: APIRequestContext) {
  const res = await request.get(`${API}/api/projects`);
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  const projects = Array.isArray(body) ? body : body.projects || body.items || [];
  // Prefer exact name (canonical cert project). Known ID is a fallback hint only.
  const byName = projects.find((p: { name?: string }) => p.name === DREAMWEAVER_NAME);
  if (byName) return byName as { id: string; name: string };
  const exact = projects.find((p: { id?: string }) => p.id === DREAMWEAVER_PROJECT_ID);
  expect(exact, "Dreamweaver project must exist for live cert").toBeTruthy();
  return exact as { id: string; name: string };
}

async function streamChat(
  request: APIRequestContext,
  projectId: string,
  messages: { role: string; content: string }[],
  model?: string | null,
): Promise<{ events: StreamEvent[]; reply: string; trace: Record<string, unknown> | null }> {
  const res = await request.post(`${API}/api/codirector/chat/stream`, {
    data: {
      messages,
      project_id: projectId,
      mode: "chat",
      model: model || undefined,
    },
    timeout: 650_000,
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  const text = await res.text();
  const events: StreamEvent[] = [];
  for (const block of text.split("\n")) {
    const line = block.trim();
    if (!line.startsWith("data:")) continue;
    const raw = line.slice(5).trim();
    if (!raw) continue;
    try {
      events.push(JSON.parse(raw) as StreamEvent);
    } catch {
      /* ignore partial */
    }
  }
  const completed = [...events].reverse().find((e) => e.type === "completed");
  const traceEvent = events.find((e) => e.type === "inference_trace");
  return {
    events,
    reply: String(completed?.content || ""),
    trace: (traceEvent?.trace as Record<string, unknown>) || null,
  };
}

test.describe("@critical @beta codirector foundational AI listening cert", () => {
  test.skip(!BETA_TARGET, "Set ADEPT_BETA_TARGET=1 for live Dreamweaver foundational AI certification.");

  test("listening path uses real model; DialoguePlan blocks title/premise intake", async ({
    page,
    request,
  }) => {
    test.setTimeout(900_000);
    await waitForAppReady(request);
    ensureArtifactDir();

    const health = await request.get(`${API}/api/codirector/providers/ollama/health`).catch(() => null);
    const healthBody = health && health.ok() ? await health.json() : null;
    writeArtifact("provider-health.json", healthBody || { error: "health unavailable" });

    const modelsRes = await request.get(`${API}/api/codirector/providers/ollama/models`).catch(() => null);
    const modelsBody = modelsRes && modelsRes.ok() ? await modelsRes.json() : null;
    writeArtifact("models.json", modelsBody || {});

    const project = await resolveDreamweaver(request);
    expect(project.name).toBe(DREAMWEAVER_NAME);

    // Prefer configured/default model from models list when present.
    let selectedModel: string | null =
      (healthBody && (healthBody.selectedModel || healthBody.selected_model)) || null;
    if (!selectedModel && modelsBody) {
      const list = Array.isArray(modelsBody) ? modelsBody : modelsBody.models || [];
      const preferred =
        list.find((m: { id?: string; name?: string }) =>
          /llama|qwen|mistral|gemma|phi/i.test(String(m.id || m.name || "")),
        ) || list[0];
      selectedModel = preferred?.id || preferred?.name || null;
    }
    expect(selectedModel, "A real selected model must be available for GO").toBeTruthy();

    const messages: { role: string; content: string }[] = [{ role: "user", content: LIVE_FAILURE }];
    const live = await streamChat(request, project.id, messages, selectedModel);
    writeArtifact("live-failure-stream.json", {
      selectedModel,
      reply: live.reply,
      trace: live.trace,
      eventTypes: live.events.map((e) => e.type),
      intent: live.events.find((e) => e.type === "intent_analysis")?.intent,
      dialoguePlan: live.events.find((e) => e.type === "dialogue_plan")?.plan,
    });

    expect(live.reply.trim().length).toBeGreaterThan(40);
    expect(live.reply).not.toMatch(TITLE_PREMISE_RE);
    expect(live.trace).toBeTruthy();
    expect(Boolean(live.trace?.fallback_used)).toBe(false);
    const actualModel = String(live.trace?.actual_model || "");
    const selected = String(live.trace?.selected_model || selectedModel || "");
    expect(actualModel.length).toBeGreaterThan(0);
    if (selected) {
      expect(actualModel).toBe(selected);
    }
    expect(String(live.trace?.mode || "")).toMatch(/LISTENING|DISCOVERY/i);

    const transcript: { role: string; content: string }[] = [
      { role: "user", content: LIVE_FAILURE },
      { role: "assistant", content: live.reply },
    ];
    const paraphraseResults = [];
    for (const phrase of PARAPHRASES) {
      const turn = await streamChat(
        request,
        project.id,
        [...transcript, { role: "user", content: phrase }],
        selectedModel,
      );
      paraphraseResults.push({ phrase, reply: turn.reply, trace: turn.trace });
      expect(turn.reply).not.toMatch(TITLE_PREMISE_RE);
      expect(Boolean(turn.trace?.fallback_used)).toBe(false);
      transcript.push({ role: "user", content: phrase }, { role: "assistant", content: turn.reply });
    }
    writeArtifact("paraphrase-results.json", paraphraseResults);

    // Multi-paragraph lore + retention + summarize
    const lore =
      "The Dreamweaver follows a harbor child who hears a lantern call across tide-worn docks. " +
      "The first season stays tactile and mythic — no cyberpunk. Continuity matters: lantern light, salt air, and hand-built boats.";
    const loreTurn = await streamChat(
      request,
      project.id,
      [...transcript, { role: "user", content: lore }],
      selectedModel,
    );
    transcript.push({ role: "user", content: lore }, { role: "assistant", content: loreTurn.reply });

    const hold = "Don’t ask questions yet. Just keep listening.";
    const holdTurn = await streamChat(
      request,
      project.id,
      [...transcript, { role: "user", content: hold }],
      selectedModel,
    );
    expect(holdTurn.reply).not.toMatch(TITLE_PREMISE_RE);
    expect((holdTurn.reply.match(/\?/g) || []).length).toBeLessThanOrEqual(1);
    transcript.push({ role: "user", content: hold }, { role: "assistant", content: holdTurn.reply });

    const summaryAsk = "Summarize what you understand so far. Separate what I confirmed from what is still uncertain.";
    const summaryTurn = await streamChat(
      request,
      project.id,
      [...transcript, { role: "user", content: summaryAsk }],
      selectedModel,
    );
    writeArtifact("summary-turn.json", { reply: summaryTurn.reply, trace: summaryTurn.trace });
    expect(summaryTurn.reply.toLowerCase()).toMatch(/lantern|harbor|dreamweaver|season|mythic|tide/);
    expect(summaryTurn.reply).not.toMatch(/as we already established that the budget/i);

    // UI path: exact failure visible in Dreamweaver
    await openCoDirectorFullScreen(page, project.id);
    const uiReply = await sendChatTurn(page, LIVE_FAILURE);
    expect(uiReply).not.toMatch(TITLE_PREMISE_RE);
    await page.screenshot({ path: path.join(ARTIFACT_DIR, "ui-listening-reply.png"), fullPage: true });

    await page.reload();
    await expect(page.getByTestId("codirector-composer-input")).toBeVisible({ timeout: 30_000 });
    await expect(
      page.locator(".codirector-msg.user .codirector-msg-bubble", { hasText: /I will tell you all about/i }).first(),
    ).toBeVisible({ timeout: 20_000 });

    writeArtifact("verdict-seed.json", {
      runId: RUN_ID,
      projectId: project.id,
      selectedModel: selected || selectedModel,
      actualModel,
      fallbackUsed: live.trace?.fallback_used,
      artifactDir: ARTIFACT_DIR,
    });
  });
});
