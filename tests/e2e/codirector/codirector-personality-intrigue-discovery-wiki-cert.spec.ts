/**
 * Personality / Relationship / Intrigue / Discovery / Wiki live certification.
 * ADEPT_BETA_TARGET=1, real model, disposable projects, retries=0, workers=1.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext } from "@playwright/test";
import { API, BETA_TARGET, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import { openCoDirectorFullScreen, sendChatTurn } from "./helpers/audit";

const RUN_ID = `personality-discovery-${new Date().toISOString().replace(/[:.]/g, "-")}`;
const ARTIFACT_DIR = path.join(
  process.cwd(),
  "docs",
  "release-gate",
  "co-director-personality-discovery",
  "artifacts",
  RUN_ID,
);

type StreamEvent = {
  type: string;
  content?: string;
  stage?: string;
  trace?: Record<string, unknown>;
  evidence?: Record<string, unknown>;
  result?: Record<string, unknown>;
  lines?: string[];
  questions?: unknown[];
  actions?: unknown[];
  state?: Record<string, unknown>;
};

function ensureDir() {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
}
function writeArtifact(name: string, data: unknown) {
  ensureDir();
  fs.writeFileSync(path.join(ARTIFACT_DIR, name), JSON.stringify(data, null, 2), "utf8");
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
  const evidence =
    events.find((e) => e.type === "response_evidence")?.evidence ||
    (trace?.response_evidence as Record<string, unknown> | undefined) ||
    null;
  const documentation = events.find((e) => e.type === "documentation_result")?.result || null;
  return { events, reply: String(completed?.content || ""), trace, evidence, documentation };
}

test.describe("@critical @beta personality intrigue discovery wiki cert", () => {
  test.skip(!BETA_TARGET, "Set ADEPT_BETA_TARGET=1 for live personality-discovery certification.");

  test("Stages 1–12 personality discovery experience", async ({ page, request }) => {
    test.setTimeout(900_000);
    await waitForAppReady(request);
    ensureDir();

    const health = await request.get(`${API}/api/codirector/providers/ollama/health`);
    expect(health.ok()).toBeTruthy();
    const healthBody = await health.json();
    writeArtifact("provider-health.json", healthBody);
    const selectedModel = healthBody.selectedModel || healthBody.selected_model;
    expect(selectedModel).toBeTruthy();

    const project = await createTempProject(request, `Personality Discovery ${Date.now()}`);
    writeArtifact("project.json", project);
    let otherId: string | null = null;

    try {
      // Stage 1 — onboarding via API + UI card
      const skipRes = await request.post(`${API}/api/codirector/projects/${project.id}/relationship`, {
        data: {
          assistantPreferredName: "Scout",
          userPreferredName: "Sam",
          primaryRole: "STORY_PARTNER",
        },
      });
      expect(skipRes.ok(), await skipRes.text()).toBeTruthy();
      const relBody = await skipRes.json();
      writeArtifact("stage1-relationship.json", relBody);
      expect(relBody.relationship?.user_preferred_name).toMatch(/Sam/i);
      expect(relBody.relationship?.assistant_preferred_name).toMatch(/Scout/i);
      expect(relBody.relationship?.primary_role).toBe("STORY_PARTNER");
      expect(relBody.relationship?.onboarding_completed).toBeTruthy();

      await openCoDirectorFullScreen(page, project.id);
      await page.screenshot({ path: path.join(ARTIFACT_DIR, "stage1-ui.png"), fullPage: true });

      // Stage 2 — persistence after reload
      await page.reload();
      await expect(page.getByTestId("codirector-composer-input")).toBeVisible({ timeout: 30_000 });
      const relReload = await request.get(`${API}/api/codirector/projects/${project.id}/relationship`);
      expect(relReload.ok()).toBeTruthy();
      const relReloadBody = await relReload.json();
      writeArtifact("stage2-reload-relationship.json", relReloadBody);
      expect(relReloadBody.relationship?.user_preferred_name).toMatch(/Sam/i);
      expect(relReloadBody.relationship?.primary_role).toBe("STORY_PARTNER");

      // Stage 3 — early project description with response evidence ≥ 2
      const story =
        "Samira charts a harbor where tide marks remember lost sailors. " +
        "When a lantern entity answers her sketches, anyone who hears the call begins to forget which shoreline is home. " +
        "Season one stays tactile and mythic — salt air, hand-built boats, no cyberpunk. " +
        "The emotional hook is longing that feels both intimate and irreversible.";
      const turn3 = await streamChat(
        request,
        project.id,
        [{ role: "user", content: story }],
        selectedModel,
      );
      writeArtifact("stage3-emergence.json", turn3);
      expect(turn3.reply).not.toMatch(/you(?:'re| are) a genius|groundbreaking/i);
      expect(turn3.reply).not.toMatch(/too ambitious|feasibility concern/i);
      const evidenceCount = Number(turn3.evidence?.count || 0);
      expect(evidenceCount).toBeGreaterThanOrEqual(2);
      expect(Boolean(turn3.evidence?.ok)).toBe(true);

      // Stage 4 — Wiki capture or explicit reason
      writeArtifact("stage4-documentation.json", turn3.documentation);
      const candidateCount = Number(turn3.documentation?.candidate_count || 0);
      const reason = String(turn3.documentation?.reason || "");
      expect(candidateCount > 0 || Boolean(reason)).toBeTruthy();
      if (candidateCount === 0) {
        expect(reason).toMatch(
          /NO_PROJECT_FACTS_FOUND|AMBIGUOUS_CONTENT|DOCUMENTATION_DISABLED|EXTRACTION_FAILED|NOT_SUBSTANTIVE/,
        );
      } else {
        expect(reason).toBe("OK");
      }
      const relAfter = await request.get(`${API}/api/codirector/projects/${project.id}/relationship`);
      const relAfterBody = await relAfter.json();
      writeArtifact("stage4-wiki-pulse.json", relAfterBody);
      expect(Number(relAfterBody.wikiCandidateCount || 0)).toBeGreaterThan(0);

      // Stage 5 — What Changed card / documentation summary after rich UI turn
      await openCoDirectorFullScreen(page, project.id);
      await sendChatTurn(
        page,
        "Also, the lantern must never resolve into a digital hologram — keep it hand-lit and tidal as Samira keeps charting.",
      );
      await page.screenshot({ path: path.join(ARTIFACT_DIR, "stage5-what-changed.png"), fullPage: true });
      const whatChanged = page
        .getByTestId("codirector-what-changed")
        .or(page.getByTestId("codirector-change-review"))
        .or(page.getByTestId("codirector-project-pulse"));
      await expect(whatChanged.first()).toBeVisible({ timeout: 30_000 });

      // Stage 6 — adaptive questions present in relationship/discovery payload
      expect(Array.isArray(relAfterBody.discoveryQuestions)).toBeTruthy();

      // Stage 7 — continue explaining without forced questionnaire
      const continueTurn = await streamChat(
        request,
        project.id,
        [
          { role: "user", content: story },
          { role: "assistant", content: turn3.reply },
          { role: "user", content: "I’d like to continue explaining freely for a bit." },
        ],
        selectedModel,
      );
      writeArtifact("stage7-continue.json", continueTurn);
      expect(continueTurn.reply).not.toMatch(/answer these questions|fill (?:in|out)/i);

      // Stage 8 — research with authorization
      const researchTurn = await streamChat(
        request,
        project.id,
        [
          { role: "user", content: story },
          {
            role: "user",
            content:
              "Please authorize research into similar works and note similarities, differences, and what makes this project distinct.",
          },
        ],
        selectedModel,
      );
      writeArtifact("stage8-research.json", researchTurn);
      const stages = researchTurn.events.filter((e) => e.type === "processing_stage").map((e) => e.stage);
      // RESEARCHING may appear when permission allows; never invent if offline
      expect(stages.length).toBeGreaterThan(0);

      // Stage 9 — support / uncertainty
      const supportTurn = await streamChat(
        request,
        project.id,
        [{ role: "user", content: "I’m beginning to wonder whether this story works at all." }],
        selectedModel,
      );
      writeArtifact("stage9-support.json", supportTurn);
      expect(supportTurn.reply).not.toMatch(/you(?:'re| are) a genius|never give up|believe in yourself/i);

      // Stage 10 — role change
      const roleRes = await request.post(`${API}/api/codirector/projects/${project.id}/relationship`, {
        data: { primaryRole: "PRODUCER" },
      });
      expect(roleRes.ok()).toBeTruthy();
      const roleBody = await roleRes.json();
      writeArtifact("stage10-role.json", roleBody);
      expect(roleBody.relationship?.primary_role).toBe("PRODUCER");

      // Stage 11 — reload persistence
      await page.reload();
      await expect(page.getByTestId("codirector-composer-input")).toBeVisible({ timeout: 30_000 });
      const persisted = await request.get(`${API}/api/codirector/projects/${project.id}/relationship`);
      const persistedBody = await persisted.json();
      writeArtifact("stage11-reload.json", persistedBody);
      expect(persistedBody.relationship?.primary_role).toBe("PRODUCER");
      expect(Number(persistedBody.wikiCandidateCount || 0)).toBeGreaterThan(0);

      // Stage 12 — isolation
      const other = await createTempProject(request, `Discovery Isolation ${Date.now()}`);
      otherId = other.id;
      const iso = await streamChat(
        request,
        other.id,
        [{ role: "user", content: "What do you already know about my story?" }],
        selectedModel,
      );
      writeArtifact("stage12-isolation.json", { otherId: other.id, reply: iso.reply });
      expect(iso.reply.toLowerCase()).not.toMatch(/lantern entity answers her sketches|salt-marsh|samira charts/);

      writeArtifact("verdict-seed.json", {
        runId: RUN_ID,
        projectId: project.id,
        selectedModel,
        actualModel: turn3.trace?.actual_model,
        fallbackUsed: turn3.trace?.fallback_used,
        evidenceCount,
        documentationReason: reason,
        candidateCount,
        artifactDir: ARTIFACT_DIR,
        humanGate: "FINAL HUMAN EXPERIENCE GATE RESERVED FOR PRODUCT OWNER",
      });
    } finally {
      if (otherId) await deleteProject(request, otherId);
      await deleteProject(request, project.id);
    }
  });
});
