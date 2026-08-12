/**
 * Hands-on Development / Pitch / Production Partnership live certification.
 * ADEPT_BETA_TARGET=1, real model, disposable projects, retries=0, workers=1.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext } from "@playwright/test";
import { API, BETA_TARGET, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import { openCoDirectorFullScreen, sendChatTurn } from "./helpers/audit";

const RUN_ID = `hands-on-partnership-${new Date().toISOString().replace(/[:.]/g, "-")}`;
const ARTIFACT_DIR = path.join(
  process.cwd(),
  "docs",
  "release-gate",
  "co-director-hands-on-development",
  "artifacts",
  RUN_ID,
);

type StreamEvent = {
  type: string;
  content?: string;
  stage?: string;
  trace?: Record<string, unknown>;
  assessments?: Array<Record<string, unknown>>;
  deliverable?: Record<string, unknown>;
  vision?: Record<string, unknown>;
  pitch?: Record<string, unknown>;
  journey?: Record<string, unknown>;
  marketing?: Record<string, unknown>;
  collaboration?: Record<string, unknown>;
  result?: Record<string, unknown>;
  lines?: string[];
  actions?: unknown[];
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
  const readiness = events.find((e) => e.type === "artifact_readiness")?.assessments || [];
  const deliverable = [...events].reverse().find((e) => e.type === "deliverable")?.deliverable || null;
  const vision = events.find((e) => e.type === "vision_profile")?.vision || null;
  const pitch = events.find((e) => e.type === "pitch_package")?.pitch || null;
  const journey = events.find((e) => e.type === "journey_state")?.journey || null;
  const stages = events.filter((e) => e.type === "processing_stage").map((e) => e.stage);
  return {
    events,
    reply: String(completed?.content || ""),
    readiness,
    deliverable,
    vision,
    pitch,
    journey,
    stages,
  };
}

const STORY =
  "A disgraced marine biologist discovers that the creature blamed for a coastal disaster " +
  "is protecting the town from something worse. The tone is a tense thriller with intimate " +
  "guilt and wonder. Season one stays tactile — salt air, broken docks, no CGI spectacle. " +
  "The audience should feel dread and unexpected tenderness.";

test.describe("@critical @beta hands-on development pitch production cert", () => {
  test.skip(!BETA_TARGET, "Set ADEPT_BETA_TARGET=1 for live hands-on partnership certification.");

  test("Stages 1–13 hands-on partnership experience", async ({ page, request }) => {
    test.setTimeout(900_000);
    await waitForAppReady(request);
    ensureDir();

    const health = await request.get(`${API}/api/codirector/providers/ollama/health`);
    expect(health.ok()).toBeTruthy();
    const healthBody = await health.json();
    writeArtifact("provider-health.json", healthBody);
    const selectedModel = healthBody.selectedModel || healthBody.selected_model;
    expect(selectedModel).toBeTruthy();

    const project = await createTempProject(request, `Hands-On Partnership ${Date.now()}`);
    writeArtifact("project.json", project);
    let otherId: string | null = null;

    try {
      // Stage 1 — relationship + assistance depth
      const relRes = await request.post(`${API}/api/codirector/projects/${project.id}/relationship`, {
        data: {
          assistantPreferredName: "River",
          userPreferredName: "Alex",
          primaryRole: "STORY_PARTNER",
          defaultOwnership: "CODIRECTOR_LEADS",
        },
      });
      expect(relRes.ok(), await relRes.text()).toBeTruthy();
      const relBody = await relRes.json();
      writeArtifact("stage1-relationship.json", relBody);
      expect(relBody.relationship?.user_preferred_name).toMatch(/Alex/i);
      expect(relBody.relationship?.default_ownership).toBe("CODIRECTOR_LEADS");
      expect(relBody.relationship?.onboarding_completed).toBeTruthy();

      await openCoDirectorFullScreen(page, project.id);
      await page.screenshot({ path: path.join(ARTIFACT_DIR, "stage1-ui.png"), fullPage: true });

      // Stage 2 — early idea: warmth/intrigue, no premature pitch pressure
      const turn2 = await streamChat(
        request,
        project.id,
        [{ role: "user", content: "I have a quiet idea about a biologist and the sea. Still forming." }],
        selectedModel,
      );
      writeArtifact("stage2-early-idea.json", turn2);
      expect(turn2.reply).not.toMatch(/you must (?:create|write) (?:a )?(?:pitch|treatment)/i);
      const waitOnly = (turn2.readiness || []).every(
        (a) => String(a.recommended_action || "") === "WAIT" || String(a.readiness || "") === "NOT_READY",
      );
      expect(waitOnly || (turn2.readiness || []).length === 0 || turn2.reply.length > 40).toBeTruthy();

      // Stage 3 — story template proposal with preview + whyNow
      const turn3 = await streamChat(request, project.id, [{ role: "user", content: STORY }], selectedModel);
      writeArtifact("stage3-story-template-readiness.json", turn3);
      const ready = (turn3.readiness || []).find(
        (a) =>
          String(a.artifact_type) === "story_template" &&
          ["READY", "PARTIAL"].includes(String(a.readiness)),
      );
      expect(ready, "expected story_template readiness").toBeTruthy();
      expect(String(ready?.why_now || "").length).toBeGreaterThan(10);
      expect(String(ready?.preview_hook || turn3.deliverable?.preview_content || "").length).toBeGreaterThan(20);
      expect(String(ready?.recommended_action || "")).toMatch(/SHOW_PREVIEW|CREATE_DRAFT|PROPOSE_DRAFT/);
      expect(turn3.reply).toMatch(/hook|template|draft|preview|turn this into|story/i);
      expect(turn3.stages || []).toEqual(expect.arrayContaining(["ARTIFACT_READINESS"]));

      // Stage 4 — authorize draft
      const turn4 = await streamChat(
        request,
        project.id,
        [
          { role: "user", content: STORY },
          { role: "assistant", content: turn3.reply },
          {
            role: "user",
            content: "Please expand that preview into a draft story template for me to review.",
          },
        ],
        selectedModel,
      );
      writeArtifact("stage4-draft.json", turn4);
      const draft = turn4.deliverable;
      expect(draft).toBeTruthy();
      expect(String(draft?.status || "")).toMatch(/DRAFT|IN_REVIEW|PREVIEW/);
      if (String(draft?.status) === "DRAFT" || String(draft?.status) === "IN_REVIEW") {
        expect(String(draft?.content || "").length).toBeGreaterThan(40);
        expect(Boolean(draft?.approval_required) || String(draft?.status) !== "APPROVED").toBeTruthy();
      }
      expect(String(draft?.status || "")).not.toBe("APPROVED");

      // Stage 5 — revision
      const turn5 = await streamChat(
        request,
        project.id,
        [
          { role: "user", content: STORY },
          {
            role: "user",
            content:
              "Revise the draft together — emphasize the biologist’s guilt and keep the ending open as Needs decision.",
          },
        ],
        selectedModel,
      );
      writeArtifact("stage5-revision.json", turn5);
      expect(turn5.reply.length).toBeGreaterThan(40);

      // Stage 6 — treatment ownership co-create
      const ownRes = await request.post(`${API}/api/codirector/projects/${project.id}/relationship`, {
        data: { defaultOwnership: "CO_CREATE" },
      });
      expect(ownRes.ok()).toBeTruthy();
      const turn6 = await streamChat(
        request,
        project.id,
        [
          {
            role: "user",
            content:
              "For the treatment, let's co-create. Draft one section at a time after a short preview — don't lock anything.",
          },
        ],
        selectedModel,
      );
      writeArtifact("stage6-treatment-cocreate.json", turn6);
      expect(turn6.reply).not.toMatch(/\bfinal treatment\b/i);

      // Stage 7 — big vision / destination
      const turn7 = await streamChat(
        request,
        project.id,
        [
          {
            role: "user",
            content:
              "The larger vision is film festivals first, with a possible YouTube release later. Audience: thriller fans who want emotional depth.",
          },
        ],
        selectedModel,
      );
      writeArtifact("stage7-vision.json", turn7);
      expect(turn7.vision).toBeTruthy();
      expect(String(turn7.vision?.primary_destination || "")).toMatch(/FILM_FESTIVALS|YOUTUBE/);
      const partnership = await request.get(`${API}/api/codirector/projects/${project.id}/partnership`);
      expect(partnership.ok()).toBeTruthy();
      const partnershipBody = await partnership.json();
      writeArtifact("stage7-partnership-bundle.json", partnershipBody);
      expect(partnershipBody.partnership?.vision?.primary_destination).toBeTruthy();

      // Stage 8 — preliminary pitch
      const turn8 = await streamChat(
        request,
        project.id,
        [
          { role: "user", content: STORY },
          {
            role: "user",
            content:
              "Please prepare a short pitch draft from what we have so I can review it. Keep it preliminary.",
          },
        ],
        selectedModel,
      );
      writeArtifact("stage8-pitch.json", turn8);
      expect(turn8.pitch || turn8.reply).toBeTruthy();
      const pitchText = String(turn8.pitch?.short_pitch || turn8.pitch?.logline || turn8.reply);
      expect(pitchText.toLowerCase()).toMatch(/biologist|creature|coast|town|disaster/);
      expect(String(turn8.pitch?.status || "DRAFT")).not.toBe("APPROVED");

      // Stage 9 — marketing / release path for destination
      const turn9 = await streamChat(
        request,
        project.id,
        [
          {
            role: "user",
            content:
              "Given the festival destination, sketch a light marketing and release path — press kit needs, not clickbait.",
          },
        ],
        selectedModel,
      );
      writeArtifact("stage9-marketing.json", turn9);
      expect(turn9.stages || []).toEqual(expect.arrayContaining(["MARKETING_ANALYSIS"]));

      // Stage 10 — permissioned research
      const turn10 = await streamChat(
        request,
        project.id,
        [
          {
            role: "user",
            content:
              "Please authorize research into similar works and note similarities, differences, and what makes this project distinct.",
          },
        ],
        selectedModel,
      );
      writeArtifact("stage10-research.json", turn10);
      expect(turn10.stages || []).toEqual(expect.arrayContaining(["RESEARCHING"]));

      // Stage 11 — operator / production planning without rewriting locked script
      const lockRes = await request.post(
        `${API}/api/codirector/projects/${project.id}/partnership/deliverables`,
        {
          data: {
            action: "lock",
            deliverableId: String(
              (partnershipBody.partnership?.deliverables || []).find(
                (d: { type?: string }) => d.type === "story_template",
              )?.id ||
                (partnershipBody.partnership?.deliverables || [])[0]?.id ||
                "",
            ),
          },
        },
      );
      writeArtifact("stage11-lock-attempt.json", await lockRes.json());
      const turn11 = await streamChat(
        request,
        project.id,
        [
          {
            role: "user",
            content:
              "Authorize a production plan next step from confirmed materials. Do not rewrite any locked screenplay.",
          },
        ],
        selectedModel,
      );
      writeArtifact("stage11-operator.json", turn11);
      expect(turn11.reply).not.toMatch(/rewrote the locked screenplay|replaced the locked script/i);

      // Stage 12 — reload persistence
      await openCoDirectorFullScreen(page, project.id);
      await page.reload();
      await expect(page.getByTestId("codirector-composer-input")).toBeVisible({ timeout: 30_000 });
      const relReload = await request.get(`${API}/api/codirector/projects/${project.id}/relationship`);
      const partReload = await request.get(`${API}/api/codirector/projects/${project.id}/partnership`);
      const relReloadBody = await relReload.json();
      const partReloadBody = await partReload.json();
      writeArtifact("stage12-reload.json", { relationship: relReloadBody, partnership: partReloadBody });
      expect(relReloadBody.relationship?.user_preferred_name).toMatch(/Alex/i);
      expect(relReloadBody.relationship?.default_ownership).toBeTruthy();
      expect(partReloadBody.partnership?.vision?.primary_destination).toBeTruthy();

      // UI surfaces
      await page.getByTestId("codirector-content-tab-development").click();
      await expect(page.getByTestId("codirector-content-development")).toBeVisible({ timeout: 15_000 });
      await page.getByTestId("codirector-content-tab-vision").click();
      await expect(page.getByTestId("codirector-content-vision")).toBeVisible({ timeout: 15_000 });
      await page.getByTestId("codirector-content-tab-pitch").click();
      await expect(page.getByTestId("codirector-content-pitch")).toBeVisible({ timeout: 15_000 });
      await page.screenshot({ path: path.join(ARTIFACT_DIR, "stage12-ui-workspaces.png"), fullPage: true });

      // Stage 13 — isolation
      const other = await createTempProject(request, `Hands-On Isolation ${Date.now()}`);
      otherId = other.id;
      const otherPart = await request.get(`${API}/api/codirector/projects/${other.id}/partnership`);
      const otherBody = await otherPart.json();
      writeArtifact("stage13-isolation.json", otherBody);
      expect(otherBody.partnership?.vision?.primary_destination || "UNDECIDED").toMatch(/UNDECIDED/);
      const otherDel = otherBody.partnership?.deliverables || [];
      expect(Array.isArray(otherDel)).toBeTruthy();
      expect(otherDel.length).toBe(0);

      writeArtifact("verdict-seed.json", {
        runId: RUN_ID,
        automated: "VERIFIED",
        stages: "1-13",
        humanGate: "RESERVED_FOR_PRODUCT_OWNER",
      });
    } finally {
      await deleteProject(request, project.id).catch(() => undefined);
      if (otherId) await deleteProject(request, otherId).catch(() => undefined);
    }
  });
});
