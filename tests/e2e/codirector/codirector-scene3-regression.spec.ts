/**
 * Scene 3 Regression — Co-Director Universal Scene Intelligence (Playwright, live stack).
 *
 * Mission law (Scene 3 regression):
 *   - Scene 3 stayed untouched during active development.
 *   - The ORIGINAL creator request (verbatim from the project chat history,
 *     sequence 50) is handed back to Co-Director through the real UI.
 *   - Co-Director must independently: resolve Cade, resolve Venture Corridor
 *     Scene, extract dialogue, extract reveal gating, extract door-breach
 *     beats, keep runtime settings separate, use canonical tags, write
 *     cinematic ACTION, and prepare the Timeline.
 *   - Cursor (this test) only provides the request and observes. No seeding,
 *     no binding repair, no prompt editing, no project/scene deletion.
 *
 * If CD fails, the fix belongs in CD's intelligence layer — then the scene is
 * re-attempted by CD, never by hand.
 */
import { expect, test, type APIRequestContext } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { API } from "../helpers/app";
import { openCoDirectorFullScreen, sendChatTurn } from "./helpers/audit";

test.use({ extraHTTPHeaders: {} });

const EVIDENCE_DIR = path.join("artifacts", "functional-audit", "universal-scene-samples");

// The real production specimens — read-only targets of the regression.
const CADE_SCENES_PROJECT_ID = "fb24ff0f-8772-4d50-a602-ac69d14b5a6b";
const SCENE_3_ID = "d0162b33-9ba6-4bb9-91b5-512a96ef965d";

// Verbatim original Scene 3 request (project chat history, 2026-09-17 06:50:11).
const ORIGINAL_SCENE_3_REQUEST = `For Scene 3, I would like to  create a Timeline prompt for the Character reference of Cade O'Connor, and using the Venture Corridor Scene environment reference sheet as the setting.

Here is the prompt for the scene:

Cinematic high-quality semi-realistic anime sci-fi scene. Preserve Cade’s exact armor, proportions, helmet, red illuminated circuitry, and red eyes from Image 1. Preserve the Venture Corridor architecture and visual design from Image 2.

CAMERA: Begin with a slow, ominous forward dolly through the Venture Corridor toward a sealed metal door. Keep the camera centered on the door and continuously move closer throughout the sequence.

ACTION: The sealed door suddenly buckles inward as an enormous punching dent violently appears from the opposite side. Cade is NOT yet visible. Hold for one second.
A second brutal impact strikes from behind the door, creating another deep punching dent and further deforming the metal.

Silence.

The damaged center of the door gradually begins glowing red-hot. The metal reaches an intense red-orange temperature.

Suddenly, a concentrated red energy beam blasts through from the opposite side, violently blowing a large jagged hole through the door. Hot fragments and sparks burst into the corridor. Thick white steam and smoke pour through the opening and temporarily obscure everything beyond it.

Continue the slow dolly toward the destroyed doorway.

Through the dense white steam, two glowing red eyes become visible first. Then faint red lights from Cade’s armor appear through the haze, gradually revealing his enormous silhouette.

Cade steps through the mangled doorway.

He is imposing, calm and completely focused. He does not rush. Steam rolls around his black armor as he walks directly toward the approaching camera. His red eyes and red suit circuitry glow through the haze. His movement is deliberate, heavy and intimidating.

Cade keeps his masked face aimed straight ahead and says in a deep, controlled, slightly synthetic/robotic male voice:

CADE: “Where is the Adept?”

After speaking, Cade continues advancing toward camera with unwavering focus.
MOOD: Menacing, ominous, restrained power. Cade should feel like an unstoppable weapon entering the Venture rather than an enraged brute.

IMPORTANT CONTINUITY: Do not reveal Cade before the laser blast. The first two door impacts originate from Cade on the unseen opposite side. Cade remains fully masked for the entire shot. No additional characters. No handheld weapons. No costume changes. No extra dialogue. No subtitles or on-screen text. Maintain the same Venture corridor throughout the shot. Maintain Cade’s exact red-era armor design throughout.

The scene will be 30 seconds long with 2 batches. 21:9, 1.0 MegaPixels using MiniMax H3.`;

// ---------------------------------------------------------------------------
// Observation helpers (same contracts as the universal sample suite)
// ---------------------------------------------------------------------------

type SseEvent = Record<string, any>;

function parseSse(body: string): SseEvent[] {
  const events: SseEvent[] = [];
  for (const line of body.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed.startsWith("data:")) continue;
    const payload = trimmed.slice("data:".length).trim();
    if (!payload) continue;
    try {
      events.push(JSON.parse(payload));
    } catch {
      /* ignore */
    }
  }
  return events;
}

function productionPlan(events: SseEvent[]) {
  const exec = events.find(
    (evt) => evt.type === "execution_status" && evt.execution?.plan_data?.sceneProduction,
  );
  return exec ? { execution: exec.execution, plan: exec.execution.plan_data } : null;
}

function actionSection(prompt: string): string {
  const match = prompt.match(/ACTION\n([\s\S]*?)(?:\n\n[A-Z ]{3,}\n|$)/);
  return (match?.[1] || "").trim();
}

function allActionSections(prompt: string): string {
  // Multi-batch scenes concatenate one windowed prompt per batch; the scene's
  // synthesized ACTION is the union of every batch window's ACTION block.
  const matches = [...prompt.matchAll(/ACTION\n([\s\S]*?)(?=\n\n[A-Z ]{3,}\n|$)/g)];
  return matches.map((m) => (m[1] || "").trim()).join("\n");
}

function expectNoDuplicateActionSentences(prompt: string) {
  // Peer round-6/7 live blocker: the beam sentence was staged TWICE inside
  // batch 1's ACTION — first by a backfill defect, then (after that fix) as
  // an LLM near-duplicate pair differing only by the leading "Suddenly, ".
  // Comparison therefore strips leading discourse markers/adverbs. Within
  // any single ACTION block a duplicate sentence is always a defect
  // (cross-section echoes like MOTION restating an ACTION sentence are by
  // design and are not checked).
  const LEADING_MARKER = /^(?:suddenly|slowly|then|next|finally|meanwhile|afterwards?|gradually|abruptly|quietly|quickly|immediately|instantly)[,\s]+/i;
  const blocks = [...prompt.matchAll(/ACTION\n([\s\S]*?)(?=\n\n[A-Z ]{3,}\n|$)/g)].map((m) => m[1] || "");
  for (const block of blocks) {
    const sentences = block
      .split(/(?<=[.!?])\s+/)
      .map((s) => s.trim().toLowerCase().replace(/\s+/g, " ").replace(LEADING_MARKER, ""))
      .filter((s) => s.length > 12);
    const seen = new Set<string>();
    for (const sentence of sentences) {
      expect(seen.has(sentence), `duplicate ACTION sentence: ${sentence}`).toBeFalsy();
      seen.add(sentence);
    }
  }
}

async function fetchMaster(request: APIRequestContext, projectId: string, sceneId: string) {
  const res = await request.get(`${API}/api/director-timeline/projects/${projectId}/scenes/${sceneId}/master`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return (await res.json()).master;
}

async function fetchSceneRow(request: APIRequestContext, projectId: string, sceneId: string) {
  const res = await request.get(`${API}/api/projects/${projectId}/scenes`);
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  const items = Array.isArray(body) ? body : body.items || body.scenes || [];
  return items.find((row: any) => row.id === sceneId);
}

// ---------------------------------------------------------------------------
// Scene 3 regression — CD processes the original request independently
// ---------------------------------------------------------------------------

test("Scene 3 regression: CD independently prepares the original request", async ({ page, request }) => {
  test.setTimeout(300_000);

  // Baseline (read-only): prove Scene 3 starts untouched by this mission.
  const baselineRow = await fetchSceneRow(request, CADE_SCENES_PROJECT_ID, SCENE_3_ID);
  const baselineMaster = await fetchMaster(request, CADE_SCENES_PROJECT_ID, SCENE_3_ID);
  const baseline = {
    prompt: baselineRow?.prompt || "",
    durationSec: baselineRow?.duration_sec,
    productionBatches: (baselineMaster?.batchBlocks || []).filter(
      (b: any) => b.migrationMetadata?.sourceProductionRequestId,
    ).length,
    totalBatches: (baselineMaster?.batchBlocks || []).length,
  };

  await openCoDirectorFullScreen(page, CADE_SCENES_PROJECT_ID, { workspace: "timeline" });
  const streamResponse = page.waitForResponse(
    (res) => res.url().includes("/api/codirector/chat/stream") && res.request().method() === "POST",
    { timeout: 240_000 },
  );
  await sendChatTurn(page, ORIGINAL_SCENE_3_REQUEST);
  const response = await streamResponse;
  expect(response.ok()).toBeTruthy();
  const events = parseSse(await response.text());
  const found = productionPlan(events);
  expect(found, "sceneProduction execution in chat stream — CD must own this request").toBeTruthy();
  const { plan } = found!;

  // Creator-visible preparation card in the real UI.
  const card = page.getByTestId("scene-production-card");
  await expect(card).toBeVisible({ timeout: 60_000 });
  const cardText = (await card.innerText()).replace(/\s+/g, " ").trim();

  // ---- Scene addressing: the EXISTING Scene 3, not a new scene ------------
  expect(plan.preparationReady, JSON.stringify(plan.error || plan)).toBeTruthy();
  expect(plan.sceneId, "CD must target the existing Scene 3").toBe(SCENE_3_ID);

  // ---- Reference verification: real statuses, canonical tags --------------
  const refs = plan.references || [];
  const tags = refs.map((r: any) => r.canonical_tag);
  expect(tags).toContain("@CadeOConnor");
  expect(tags).toContain("#VentureCorridorScene");
  expect(refs.every((r: any) => r.status === "found")).toBeTruthy();
  // No suffix drift anywhere in the plan.
  expect(JSON.stringify(plan)).not.toMatch(/CadeOConnor\d|VentureCorridorScene\d/);

  // ---- Milestones: grounded preparation visible to the creator ------------
  const milestoneTypes = (plan.events || []).map((evt: any) => evt.type);
  for (const needed of [
    "environment_identified",
    "characters_identified",
    "references_verified",
    "dialogue_detected",
    "reveals_identified",
    "action_synthesized",
    "prompt_compiled",
  ]) {
    expect(milestoneTypes, `milestone ${needed} in ${milestoneTypes.join(",")}`).toContain(needed);
  }

  // ---- Runtime metadata: separate from the creative prompt -----------------
  expect(Number(plan.durationSeconds)).toBe(30);
  expect(Number(plan.batchCount)).toBe(2);
  expect(String(plan.aspectRatio)).toBe("21:9");
  expect(Number(plan.megapixels)).toBe(1.0);
  expect(String(plan.generatorId)).toMatch(/minimax/i);

  const prompt = String(plan.compiledPrompt || "");
  // Beat assertions span every batch window's ACTION block (multi-batch scene).
  const action = allActionSections(prompt) || actionSection(prompt);
  expect(action, `ACTION must not carry runtime metadata: ${action}`).not.toMatch(
    /\b\d+(?:\.\d+)?\s*seconds?\b|21:9|16:9|megapixels?|\b\d+(?:\.\d+)?\s*MP\b|minimax|\bh3\b|batch|batches/i,
  );
  expect(action).not.toMatch(/build a scene|timeline prompt|reference sheet|i would like/i);
  // Runtime metadata stays out of EVERY prompt section (ACTION, CONTINUITY,
  // NEGATIVE) — not just ACTION. ("story seconds 0–15" is narrative time: the
  // regex requires digits before "seconds".)
  expect(prompt, `prompt must not carry runtime metadata: ${prompt}`).not.toMatch(
    /\b\d+(?:\.\d+)?\s*seconds?\b|21:9|16:9|megapixels?|\b\d+(?:\.\d+)?\s*MP\b|\bminimax\b|\bh3\b|\bbatches?\b/i,
  );
  // Internal image labels never leak into prompt-facing identity.
  expect(prompt).not.toMatch(/Image\s*1|Image\s*2/i);
  // No sentence is staged twice inside any ACTION block (round-6 live defect).
  expectNoDuplicateActionSentences(prompt);

  // ---- Canonical tags in the compiled prompt -------------------------------
  expect(prompt).toContain("@CadeOConnor");
  expect(prompt).toContain("#VentureCorridorScene");

  // ---- Dialogue extraction: exact line, attributed, not paraphrased --------
  const dialogue = plan.directorIntent?.dialogue || [];
  expect(dialogue.map((d: any) => d.line)).toContain("Where is the Adept?");
  const cadeLine = dialogue.find((d: any) => d.line === "Where is the Adept?");
  expect(String(cadeLine?.speaker || "").toLowerCase()).toContain("cade");
  expect(prompt).toContain("Where is the Adept?");

  // ---- Reveal gating survives prompt synthesis ------------------------------
  const lower = prompt.toLowerCase();
  expect(lower).toMatch(/do not reveal|remains? hidden|hidden until|not yet visible/);
  const reveals = plan.directorIntent?.reveals || [];
  expect(reveals.length).toBeGreaterThanOrEqual(1);

  // ---- Door-breach beat structure in synthesized ACTION --------------------
  expect(action.toLowerCase()).toMatch(/dent|buckle|impact/);
  expect(action.toLowerCase()).toMatch(/glow|red-hot|red hot/);
  expect(action.toLowerCase()).toMatch(/beam|blast/);
  expect(action.toLowerCase()).toMatch(/steam|smoke/);
  expect(action.toLowerCase()).toMatch(/eyes/);
  expect(action.toLowerCase()).toMatch(/steps through|steps out|emerges/);

  // ---- Beat completeness: no staged on-screen event may be dropped ---------
  // The FIRST impact and the one-second hold are staged before the second
  // impact in the original request; an LLM rewrite that drops them must be
  // caught by the beat-coverage backstop.
  expect(action.toLowerCase()).toMatch(/buckles/);
  // The staged one-second hold must survive (the LLM may phrase the duration
  // as "one second" or "a second"; the beat itself may not be dropped).
  expect(action.toLowerCase()).toMatch(/holds? for (?:one|1|a) second/);
  const firstImpact = action.toLowerCase().search(/buckles/);
  const secondImpact = action.toLowerCase().search(/second brutal impact/);
  expect(
    secondImpact === -1 || firstImpact === -1 || firstImpact < secondImpact,
    `first impact must precede the second impact: ${action}`,
  ).toBeTruthy();

  // ---- Timeline prepared: scene row + two windowed production batches ------
  const sceneRow = await fetchSceneRow(request, CADE_SCENES_PROJECT_ID, SCENE_3_ID);
  expect(sceneRow, "Scene 3 row still exists").toBeTruthy();
  expect(sceneRow.prompt).toBe(prompt);
  expect(Number(sceneRow.duration_sec)).toBe(30);

  const master = await fetchMaster(request, CADE_SCENES_PROJECT_ID, SCENE_3_ID);
  const batches = (master?.batchBlocks || []).filter(
    (b: any) => b.migrationMetadata?.sourceProductionRequestId,
  );
  expect(batches.length).toBe(2);
  expect(batches[0].duration?.plannedDuration).toBe(15);
  expect(batches[1].duration?.plannedDuration).toBe(15);
  const text0 = String(batches[0].promptSegments?.[0]?.text || "");
  const text1 = String(batches[1].promptSegments?.[0]?.text || "");
  expect(text0).not.toBe(text1);
  expect(text0).toContain("@CadeOConnor");
  expect(text1).toContain("@CadeOConnor");
  expect(text0).toMatch(/story seconds 0–15/);
  expect(text1).toMatch(/story seconds 15–30/);
  // Reveal lands after the breach: the closing batch carries the entrance.
  expect(text1.toLowerCase()).toMatch(/steps through|steps out|emerges|advancing|toward/);

  // ---- Reference bindings persisted on the scene ---------------------------
  const bindingsRes = await request.get(
    `${API}/api/projects/${CADE_SCENES_PROJECT_ID}/references?scope_type=scene&scope_id=${SCENE_3_ID}`,
  );
  let bindingCount = 0;
  if (bindingsRes.ok()) {
    const body = await bindingsRes.json();
    const rows = Array.isArray(body) ? body : body.items || body.bindings || [];
    bindingCount = rows.length;
  }
  expect(bindingCount, "scene reference bindings persisted").toBeGreaterThanOrEqual(2);

  // ---- Persistence across reload (data-level re-read after UI reload) ------
  await page.reload();
  const masterAfterReload = await fetchMaster(request, CADE_SCENES_PROJECT_ID, SCENE_3_ID);
  const batchesAfterReload = (masterAfterReload?.batchBlocks || []).filter(
    (b: any) => b.migrationMetadata?.sourceProductionRequestId,
  );
  expect(batchesAfterReload.length).toBe(2);
  expect(String(batchesAfterReload[0].promptSegments?.[0]?.text || "")).toContain("@CadeOConnor");

  // ---- Creator-visible card -------------------------------------------------
  expect(cardText).toMatch(/Scene Prepared/i);
  expect(cardText).toMatch(/MiniMax H3/i);

  // ---- Evidence -------------------------------------------------------------
  const intent = plan.directorIntent || {};
  fs.mkdirSync(EVIDENCE_DIR, { recursive: true });
  fs.writeFileSync(
    path.join(EVIDENCE_DIR, "scene3-regression.json"),
    JSON.stringify(
      {
        sample: "Scene 3 Regression",
        request: ORIGINAL_SCENE_3_REQUEST,
        baseline,
        preparationReady: Boolean(plan.preparationReady),
        sceneId: plan.sceneId,
        expectedSceneId: SCENE_3_ID,
        references: refs.map((ref: any) => ({
          name: ref.display_name,
          type: ref.asset_type,
          status: ref.status,
          verification: ref.verification,
          canonicalTag: ref.canonical_tag,
        })),
        milestoneEvents: milestoneTypes,
        directorIntent: {
          sceneType: intent.scene_type || intent.shot_type || "",
          mood: intent.mood || "",
          beatCount: (intent.scene_beats || intent.timed_beats || []).length,
          dialogue: dialogue.map((line: any) => ({ speaker: line.speaker, line: line.line })),
          reveals: reveals.map((reveal: any) => ({
            subject: reveal.subject,
            hiddenUntil: reveal.hidden_until,
          })),
          camera: intent.camera_plan || null,
        },
        runtimeSettings: {
          generatorId: plan.generatorId,
          durationSeconds: plan.durationSeconds,
          batchCount: plan.batchCount,
          aspectRatio: plan.aspectRatio,
          megapixels: plan.megapixels,
        },
        compiledPrompt: prompt,
        timeline: {
          sceneId: plan.sceneId || "",
          shotId: plan.shotId || "",
          batchCount: (master?.batchBlocks || []).length,
          productionBatches: batches.length,
          batchDurations: batches.map((b: any) => b.duration?.plannedDuration),
          scenePromptMatchesCompiled: sceneRow?.prompt === prompt,
          bindingCount,
        },
        cardText,
      },
      null,
      2,
    ),
  );
});
