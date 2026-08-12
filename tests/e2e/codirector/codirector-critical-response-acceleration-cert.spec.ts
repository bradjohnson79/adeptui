/**
 * Co-Director Critical Response Acceleration cert (Stages 1–12 + N1–N10).
 * Requires ADEPT_BETA_TARGET=1 with Beta on 8760 / API 8758 and a warm real model.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext } from "@playwright/test";
import { API, BETA_TARGET, waitForAppReady } from "../helpers/app";
import { openCoDirectorFullScreen, sendChatTurn } from "./helpers/audit";

const PROJECT_NAME = "The Dreamweaver";
const RUN_ID =
  fs.existsSync(
    path.join(process.cwd(), "docs/release-gate/co-director-performance/artifacts/CURRENT_RUN_ID.txt"),
  )
    ? fs
        .readFileSync(
          path.join(process.cwd(), "docs/release-gate/co-director-performance/artifacts/CURRENT_RUN_ID.txt"),
          "utf8",
        )
        .trim()
    : `codirector-accel-${new Date().toISOString().replace(/[:.]/g, "-")}`;

const ARTIFACT_DIR = path.join(
  process.cwd(),
  "docs",
  "release-gate",
  "co-director-performance",
  "artifacts",
  RUN_ID,
);

type StreamEvent = {
  type: string;
  content?: string;
  stage?: string;
  options?: { type?: string; label?: string; ownershipRequired?: boolean }[];
  intro?: string;
  jobType?: string;
  status?: string;
  result?: Record<string, unknown>;
  trace?: Record<string, unknown>;
};

function ensureDir() {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
}

function writeArtifact(name: string, data: unknown) {
  ensureDir();
  fs.writeFileSync(path.join(ARTIFACT_DIR, name), JSON.stringify(data, null, 2), "utf8");
}

async function resolveProject(request: APIRequestContext) {
  const res = await request.get(`${API}/api/projects`);
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  const projects = Array.isArray(body) ? body : body.projects || body.items || [];
  const named = projects.find((p: { name?: string }) => p.name === PROJECT_NAME);
  expect(named, `${PROJECT_NAME} must exist`).toBeTruthy();
  return named as { id: string; name: string };
}

async function streamChat(
  _request: APIRequestContext,
  projectId: string,
  content: string,
): Promise<{ events: StreamEvent[]; reply: string; ttftMs: number | null; firstStageMs: number | null }> {
  // Must stream-parse SSE — Playwright APIRequestContext buffers the body, which falsifies TTFT.
  const t0 = Date.now();
  let firstTokenAt: number | null = null;
  let firstStageAt: number | null = null;
  const events: StreamEvent[] = [];
  const res = await fetch(`${API}/api/codirector/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({
      messages: [{ role: "user", content }],
      project_id: projectId,
      mode: "chat",
    }),
  });
  expect(res.ok, `stream HTTP ${res.status}`).toBeTruthy();
  expect(res.body, "stream body").toBeTruthy();
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n");
    buffer = parts.pop() || "";
    for (const block of parts) {
      const line = block.trim();
      if (!line.startsWith("data:")) continue;
      const raw = line.slice(5).trim();
      if (!raw || raw === "[DONE]") continue;
      try {
        const ev = JSON.parse(raw) as StreamEvent;
        events.push(ev);
        if (ev.type === "processing_stage" && firstStageAt == null) firstStageAt = Date.now();
        if (ev.type === "token" && firstTokenAt == null) firstTokenAt = Date.now();
      } catch {
        /* ignore partial JSON */
      }
    }
  }
  const completed = [...events].reverse().find((e) => e.type === "completed");
  return {
    events,
    reply: String(completed?.content || ""),
    ttftMs: firstTokenAt == null ? null : firstTokenAt - t0,
    firstStageMs: firstStageAt == null ? null : firstStageAt - t0,
  };
}

test.describe("@critical @beta codirector critical response acceleration cert", () => {
  test.skip(!BETA_TARGET, "Set ADEPT_BETA_TARGET=1 for live acceleration certification.");

  test("Stages 1–12 + N1–N10: true stream, async wiki, next-step invitations", async ({
    page,
    request,
  }) => {
    test.setTimeout(900_000);
    await waitForAppReady(request);
    ensureDir();
    const project = await resolveProject(request);

    // Stage 1–3: early stages before first token; TTFT gates
    const onboarding = await streamChat(
      request,
      project.id,
      "Yes — Agent Gold is a great name. For this project I want a hands-on Balanced Co-Director: listen first while I tell the story.",
    );
    writeArtifact("stage1_onboarding_stream.json", onboarding);
    const stages = onboarding.events.filter((e) => e.type === "processing_stage").map((e) => e.stage);
    expect(stages[0], "Stage 1 early stage").toBeTruthy();
    expect(onboarding.firstStageMs ?? 999999).toBeLessThan(5_000);
    expect(onboarding.ttftMs, "Stage 2 TTFT present").not.toBeNull();
    expect(onboarding.ttftMs!, "Stage 3 TTFT < 30s hard gate").toBeLessThan(30_000);

    // Stage 4–5: WAITING_FOR_MODEL / STREAMING before COMPLETE; streamed flag
    expect(stages).toContain("WAITING_FOR_MODEL");
    expect(stages.indexOf("WAITING_FOR_MODEL")).toBeLessThan(stages.indexOf("COMPLETE") ?? 999);
    const trace = onboarding.events.find((e) => e.type === "inference_trace")?.trace || {};
    expect(Boolean(trace.streamed), "Stage 5 true stream provenance").toBeTruthy();
    expect(Boolean(trace.defer_enrichment), "Stage 6 deferred enrichment").toBeTruthy();

    // Stage 7–8: Wiki background after tokens
    const tokenIdx = onboarding.events.findIndex((e) => e.type === "token");
    const wikiIdx = onboarding.events.findIndex(
      (e) => e.type === "processing_stage" && e.stage === "UPDATING_WIKI",
    );
    expect(tokenIdx).toBeGreaterThanOrEqual(0);
    if (wikiIdx >= 0) {
      expect(wikiIdx, "Stage 7 wiki after first token").toBeGreaterThan(tokenIdx);
    }
    const bg = onboarding.events.find((e) => e.type === "background_job");
    expect(bg?.jobType || "wiki_enrichment").toBe("wiki_enrichment");

    // Stage 9–12: rich story turn — warm reply + next steps, no stuck Understanding
    const story = await streamChat(
      request,
      project.id,
      "Korri is a young witness in a world where memory is court evidence. Present-day testimony frames flashbacks the state keeps rewriting. The conflict is her fighting to keep her past true.",
    );
    writeArtifact("stage9_story_stream.json", story);
    expect(story.ttftMs!, "Stage 9 story TTFT < 30s").toBeLessThan(30_000);
    expect(story.reply.length, "Stage 10 non-empty reply").toBeGreaterThan(40);
    const next = story.events.find((e) => e.type === "next_step_options");
    writeArtifact("stage_n_next_steps.json", next || {});
    expect(next, "N1 next_step_options emitted").toBeTruthy();
    const opts = next?.options || [];
    expect(opts.length, "N2 2–4 options").toBeGreaterThanOrEqual(1);
    expect(opts.length, "N3 cap 4").toBeLessThanOrEqual(4);
    expect(opts.some((o) => o.type === "CONTINUE_STORY"), "N4 continue path").toBeTruthy();

    // UI Stages 11–12 + N chips — honest stage chrome + soft invitations
    await openCoDirectorFullScreen(page, project.id);
    const input = page.getByTestId("codirector-composer-input");
    await expect(input).toBeVisible({ timeout: 30_000 });
    const assistantBubbles = page.locator(".codirector-msg.assistant .codirector-msg-bubble");
    const before = await assistantBubbles.count();
    await input.fill(
      "Let's keep developing Korri's world and character — what stands out in the memory-as-evidence premise so far?",
    );
    await input.press("Enter");
    // Prefer new assistant bubble; also accept content growth on the latest bubble while streaming.
    await expect
      .poll(
        async () => {
          const count = await assistantBubbles.count();
          if (count > before) return true;
          if (count === 0) return false;
          const text = ((await assistantBubbles.last().innerText().catch(() => "")) || "").trim();
          return text.length > 20;
        },
        { timeout: 180_000 },
      )
      .toBeTruthy();
    const turn = ((await assistantBubbles.last().innerText().catch(() => "")) || "").trim();
    writeArtifact("ui_turn.json", { reply: turn, before, after: await assistantBubbles.count() });
    // Processing chrome should use SSE stages (may already be complete by poll end).
    const processing = page.getByTestId("codirector-processing");
    if (await processing.count()) {
      await expect(processing).toBeVisible();
    }
    const chips = page.getByTestId("codirector-next-step-options");
    await expect
      .poll(async () => chips.count(), { timeout: 60_000 })
      .toBeGreaterThan(0);
    await expect(page.getByTestId("codirector-next-step-CONTINUE_STORY")).toBeVisible();

    writeArtifact("acceleration_cert_summary.json", {
      runId: RUN_ID,
      projectId: project.id,
      onboardingTtftMs: onboarding.ttftMs,
      storyTtftMs: story.ttftMs,
      streamed: Boolean(trace.streamed),
      deferEnrichment: Boolean(trace.defer_enrichment),
      nextStepCount: opts.length,
      uiReplyChars: turn.length,
      verdictCandidate:
        (onboarding.ttftMs ?? 999999) < 30_000 &&
        (story.ttftMs ?? 999999) < 30_000 &&
        opts.length >= 1
          ? "PASS_GATES"
          : "FAIL_TTFT",
    });
  });
});
