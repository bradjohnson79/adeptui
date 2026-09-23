/**
 * Co-Director Universal Scene Intelligence — Sample Scenes A–F (Playwright, live stack).
 *
 * Mission law: every sample is driven through the ACTUAL Co-Director UI chat.
 * No mocks. No manual Timeline repair. Cursor (the test) only:
 *   1. seeds FIXTURE reference sheets via public APIs (environment/character/prop
 *      records — never scene bindings; resolving them is Co-Director's job),
 *   2. types the natural-language request into the real composer,
 *   3. observes the creator-visible preparation card,
 *   4. inspects persisted output (Timeline master, scene row, bindings),
 *   5. records evidence JSON per sample.
 *
 * If CD fails a sample, the test fails — the fix belongs in CD's intelligence
 * layer, not in the scene.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { API, createTempProject, deleteProject } from "../helpers/app";
import { openCoDirectorFullScreen, sendChatTurn, TINY_PNG, uploadProjectAsset } from "./helpers/audit";

test.use({ extraHTTPHeaders: {} });

const EVIDENCE_DIR = path.join("artifacts", "functional-audit", "universal-scene-samples");

// ---------------------------------------------------------------------------
// Fixture seeding (public product APIs — reference records only, no bindings)
// ---------------------------------------------------------------------------

async function seedEnvironment(request: APIRequestContext, projectId: string, name: string, tag: string) {
  const asset = await uploadProjectAsset(request, projectId, {
    name: `${tag}.png`,
    mimeType: "image/png",
    kind: "image",
    buffer: TINY_PNG,
    tag,
  });
  const save = await request.post(`${API}/api/environment-reference-sheets/projects/${projectId}/save`, {
    data: { name, environmentPrompt: `${name} test environment`, referenceImageAssetId: asset.id },
  });
  expect(save.ok(), await save.text()).toBeTruthy();
  const sheetId = (await save.json()).sheet.sheetId as string;
  const approve = await request.post(
    `${API}/api/environment-reference-sheets/projects/${projectId}/${sheetId}/approve-reference`,
    { data: { assetId: asset.id } },
  );
  expect(approve.ok(), await approve.text()).toBeTruthy();
}

async function seedCharacter(request: APIRequestContext, projectId: string, name: string, slug: string) {
  const asset = await uploadProjectAsset(request, projectId, {
    name: `${slug}.png`,
    mimeType: "image/png",
    kind: "image",
    buffer: TINY_PNG,
    tag: slug,
  });
  const create = await request.post(`${API}/api/projects/${projectId}/characters`, {
    data: { name, slug, role: "lead" },
  });
  expect(create.ok(), await create.text()).toBeTruthy();
  const characterId = (await create.json()).id as string;
  const approve = await request.post(`${API}/api/projects/${projectId}/characters/${characterId}/approve-candidate`, {
    data: { assetId: asset.id, referenceRole: "hero_identity", sourceType: "upload", ownerConfirmed: true },
  });
  expect(approve.ok(), await approve.text()).toBeTruthy();
}

async function seedProp(request: APIRequestContext, projectId: string, name: string, tag: string) {
  const asset = await uploadProjectAsset(request, projectId, {
    name: `${tag}.png`,
    mimeType: "image/png",
    kind: "image",
    buffer: TINY_PNG,
    tag,
  });
  const create = await request.post(`${API}/api/prop-creator/projects/${projectId}/props`, {
    data: { name },
  });
  expect(create.ok(), await create.text()).toBeTruthy();
  const propId = (await create.json()).prop.id as string;
  const identity = await request.post(`${API}/api/prop-creator/projects/${projectId}/props/${propId}/use-as-identity`, {
    data: { asset_id: asset.id },
  });
  expect(identity.ok(), await identity.text()).toBeTruthy();
}

// ---------------------------------------------------------------------------
// Observation helpers
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

function promptSection(prompt: string, name: string): string {
  const match = prompt.match(new RegExp(`${name}\\n([\\s\\S]*?)(?:\\n\\n[A-Z /]{3,}\\n|$)`));
  return (match?.[1] || "").trim();
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

function writeEvidence(sample: string, evidence: Record<string, unknown>) {
  fs.mkdirSync(EVIDENCE_DIR, { recursive: true });
  fs.writeFileSync(path.join(EVIDENCE_DIR, `sample-${sample}.json`), JSON.stringify(evidence, null, 2));
}

type SampleRun = {
  plan: any;
  cardText: string;
  master: any;
  sceneRow: any;
};

async function runSampleThroughUi(
  page: Page,
  request: APIRequestContext,
  projectId: string,
  message: string,
): Promise<SampleRun> {
  await openCoDirectorFullScreen(page, projectId, { workspace: "timeline" });
  const streamResponse = page.waitForResponse(
    (res) => res.url().includes("/api/codirector/chat/stream") && res.request().method() === "POST",
    { timeout: 180_000 },
  );
  await sendChatTurn(page, message);
  const response = await streamResponse;
  expect(response.ok()).toBeTruthy();
  const events = parseSse(await response.text());
  const found = productionPlan(events);
  expect(found, "sceneProduction execution in chat stream").toBeTruthy();
  const { plan } = found!;

  // Creator-visible card in the real UI.
  const card = page.getByTestId("scene-production-card");
  await expect(card).toBeVisible({ timeout: 60_000 });
  const cardText = (await card.innerText()).replace(/\s+/g, " ").trim();

  const master = plan.sceneId ? await fetchMaster(request, projectId, plan.sceneId) : null;
  const sceneRow = plan.sceneId ? await fetchSceneRow(request, projectId, plan.sceneId) : null;
  return { plan, cardText, master, sceneRow };
}

function baseEvidence(sample: string, requestText: string, run: SampleRun) {
  const intent = run.plan.directorIntent || {};
  return {
    sample,
    request: requestText,
    preparationReady: Boolean(run.plan.preparationReady),
    references: (run.plan.references || []).map((ref: any) => ({
      name: ref.display_name,
      type: ref.asset_type,
      status: ref.status,
      verification: ref.verification,
      canonicalTag: ref.canonical_tag,
    })),
    milestoneEvents: (run.plan.events || []).map((evt: any) => evt.type),
    directorIntent: {
      sceneType: intent.scene_type || intent.shot_type || "",
      mood: intent.mood || "",
      beatCount: (intent.scene_beats || intent.timed_beats || []).length,
      dialogue: (intent.dialogue || []).map((line: any) => ({ speaker: line.speaker, line: line.line })),
      reveals: (intent.reveals || []).map((reveal: any) => ({
        subject: reveal.subject,
        hiddenUntil: reveal.hidden_until,
      })),
      camera: intent.camera_plan || null,
      actionText: intent.action_text || "",
    },
    runtimeSettings: {
      generatorId: run.plan.generatorId,
      durationSeconds: run.plan.durationSeconds,
      batchCount: run.plan.batchCount,
      aspectRatio: run.plan.aspectRatio,
      megapixels: run.plan.megapixels,
    },
    compiledPrompt: run.plan.compiledPrompt || "",
    timeline: {
      sceneId: run.plan.sceneId || "",
      shotId: run.plan.shotId || "",
      batchCount: (run.master?.batchBlocks || []).length,
      batchDurations: (run.master?.batchBlocks || []).map((b: any) => b.duration?.plannedDuration),
      scenePromptMatchesCompiled: Boolean(run.sceneRow && run.sceneRow.prompt === run.plan.compiledPrompt),
    },
    cardText: run.cardText,
  };
}

function expectNoDuplicateActionSentences(prompt: string) {
  // Peer round-6/7 live blocker: the same event was staged TWICE inside one
  // ACTION block — first by a backfill defect, then (after that fix) as an
  // LLM near-duplicate pair differing only by a leading adverb. Comparison
  // therefore strips leading discourse markers/adverbs. Within any single
  // ACTION block a duplicate sentence is always a defect (cross-section
  // echoes like MOTION restating an ACTION sentence are by design and are
  // not checked).
  const LEADING_MARKER = /^(?:suddenly|slowly|then|next|finally|meanwhile|afterwards?|gradually|abruptly|quietly|quickly|immediately|instantly)[,\s]+/i;
  // Reveal gates and camera-continuity language intentionally persist across
  // batch windows; discrete event sentences must not (peer round-8: a
  // boundary-spanning beat was staged in BOTH batches' ACTION).
  const CROSS_BATCH_EXEMPT = /hidden|remains?|do not reveal|not yet visible|stays|keeps?|continu|preserve|maintain|segment covers/i;
  const blocks = [...prompt.matchAll(/ACTION\n([\s\S]*?)(?=\n\n[A-Z ]{3,}\n|$)/g)].map((m) => m[1] || "");
  const blockSentences: string[][] = blocks.map((block) =>
    block
      .split(/(?<=[.!?]["'”’]?)\s+/)
      .map((s) => s.trim().toLowerCase().replace(/\s+/g, " ").replace(LEADING_MARKER, ""))
      .filter((s) => s.length > 12),
  );
  const globalSeen = new Map<string, number>();
  blockSentences.forEach((sentences, blockIndex) => {
    const seen = new Set<string>();
    for (const sentence of sentences) {
      expect(seen.has(sentence), `duplicate ACTION sentence: ${sentence}`).toBeFalsy();
      seen.add(sentence);
      if (!CROSS_BATCH_EXEMPT.test(sentence)) {
        const prior = globalSeen.get(sentence);
        expect(
          prior,
          `event sentence staged in multiple batches (blocks ${prior} and ${blockIndex}): ${sentence}`,
        ).toBeUndefined();
        globalSeen.set(sentence, blockIndex);
      }
    }
  });
}

function expectRuntimeSeparated(prompt: string) {
  // Runtime metadata must not appear ANYWHERE in the compiled creative
  // prompt — not in ACTION, CONTINUITY, or NEGATIVE sections. (The batch
  // window note "story seconds 0–15" is narrative time, not a runtime token:
  // the regex requires digits BEFORE "seconds".)
  expect(prompt, `prompt must not carry runtime metadata: ${prompt}`).not.toMatch(
    /\b\d+(?:\.\d+)?\s*seconds?\b|21:9|16:9|megapixels?|\b\d+(?:\.\d+)?\s*MP\b|\bminimax\b|\bh3\b|\bbatches?\b/i,
  );
  const action = actionSection(prompt);
  expect(action).not.toMatch(/build a scene|timeline prompt|reference sheet|i would like/i);
  // Every sample is also duplicate-sentence clean (round-6 live defect guard).
  expectNoDuplicateActionSentences(prompt);
}

function expectMilestones(plan: any, required: string[]) {
  const types = (plan.events || []).map((evt: any) => evt.type);
  for (const needed of required) {
    expect(types, `milestone ${needed} in ${types.join(",")}`).toContain(needed);
  }
}

// ---------------------------------------------------------------------------
// Sample A — environment-only establishing shot
// ---------------------------------------------------------------------------

test("Sample A: environment-only establishing shot", async ({ page, request }) => {
  test.setTimeout(240_000);
  const project = await createTempProject(request, "Universal Sample A");
  try {
    await seedEnvironment(request, project.id, "Salt Flats", "salt_flats");
    // Phrasing family: "Create a Timeline scene …" (Timeline-first).
    const message =
      "Create a Timeline scene using the Salt Flats environment reference sheet as the setting. " +
      "A slow aerial drift over the white flats at dawn, distant mountains on the horizon. " +
      "No characters, no dialogue. 10 seconds, 1 batch, MiniMax H3, 21:9, 1.0 MP.";
    const run = await runSampleThroughUi(page, request, project.id, message);
    const { plan } = run;

    expect(plan.preparationReady, JSON.stringify(plan.error || plan)).toBeTruthy();
    // Scene type + reference verification
    const refs = plan.references || [];
    expect(refs.map((r: any) => r.canonical_tag)).toContain("#SaltFlats");
    expect(refs.every((r: any) => r.status === "found")).toBeTruthy();
    expect(refs.filter((r: any) => r.asset_type === "character")).toHaveLength(0);
    expectMilestones(plan, ["environment_identified", "references_verified", "scene_structure_analyzed", "action_synthesized", "prompt_compiled"]);
    // Prompt laws
    const prompt = String(plan.compiledPrompt || "");
    expect(prompt).toContain("#SaltFlats");
    expect(prompt).not.toContain("#SaltFlats2");
    expectRuntimeSeparated(prompt);
    const action = actionSection(prompt);
    expect(action.toLowerCase()).toContain("drift");
    // No cast/voice fabrication
    expect(String(plan.directorIntent?.dialogue ? JSON.stringify(plan.directorIntent.dialogue) : "[]")).toBe("[]");
    // Persistence
    expect(run.sceneRow?.prompt).toBe(prompt);
    const batches = run.master?.batchBlocks || [];
    expect(batches.length).toBeGreaterThanOrEqual(1);
    expect(String(batches[0].promptSegments?.[0]?.text || "")).toContain("#SaltFlats");
    // Creator-visible card
    expect(run.cardText).toMatch(/Scene Prepared/i);
    expect(run.cardText).toMatch(/MiniMax H3/i);
    writeEvidence("a", baseEvidence("A", message, run));
  } finally {
    await deleteProject(request, project.id);
  }
});

// ---------------------------------------------------------------------------
// Sample B — character + environment suspense reveal
// ---------------------------------------------------------------------------

test("Sample B: character + environment suspense reveal", async ({ page, request }) => {
  test.setTimeout(240_000);
  const project = await createTempProject(request, "Universal Sample B");
  try {
    await seedEnvironment(request, project.id, "Neon Harbor", "neon_harbor");
    await seedCharacter(request, project.id, "Mara Voss", "mara-voss");
    // Phrasing family: "Build a Timeline scene …" (Timeline-first).
    const message =
      "Build a Timeline scene with the Character reference of Mara Voss inside the Neon Harbor environment reference sheet. " +
      "The harbor is foggy and quiet. The camera drifts slowly along the dock. " +
      "Do not reveal Mara until the fog thins at the end. " +
      "Her silhouette appears through the fog first, then her face. No dialogue. " +
      "10 seconds, 1 batch, MiniMax H3, 21:9, 1.0 MP.";
    const run = await runSampleThroughUi(page, request, project.id, message);
    const { plan } = run;

    expect(plan.preparationReady, JSON.stringify(plan.error || plan)).toBeTruthy();
    const tags = (plan.references || []).map((r: any) => r.canonical_tag);
    expect(tags).toContain("#NeonHarbor");
    expect(tags).toContain("@MaraVoss");
    expectMilestones(plan, ["environment_identified", "characters_identified", "references_verified", "reveals_identified", "action_synthesized", "prompt_compiled"]);
    const prompt = String(plan.compiledPrompt || "");
    expect(prompt).toContain("@MaraVoss");
    expect(prompt).toContain("#NeonHarbor");
    expectRuntimeSeparated(prompt);
    // Reveal gating survives prompt synthesis
    expect(prompt.toLowerCase()).toMatch(/do not reveal|remains? hidden|hidden until/);
    expect(prompt.toLowerCase()).toMatch(/fog/);
    expect(run.sceneRow?.prompt).toBe(prompt);
    writeEvidence("b", baseEvidence("B", message, run));
  } finally {
    await deleteProject(request, project.id);
  }
});

// ---------------------------------------------------------------------------
// Sample C — dialogue scene (two characters)
// ---------------------------------------------------------------------------

test("Sample C: dialogue scene with two characters", async ({ page, request }) => {
  test.setTimeout(240_000);
  const project = await createTempProject(request, "Universal Sample C");
  try {
    await seedEnvironment(request, project.id, "Rust Market", "rust_market");
    await seedCharacter(request, project.id, "Iris Kane", "iris-kane");
    await seedCharacter(request, project.id, "Dax Meridian", "dax-meridian");
    // Phrasing family: "Make a Timeline scene …" (Timeline-first).
    const message =
      "Make a Timeline scene with the Character reference of Iris Kane and the Character reference of Dax Meridian " +
      "in the Rust Market environment reference sheet. " +
      "Iris stands by a stall and says: \"You are late.\" Dax replies: \"The bridge was closed.\" " +
      "Minimal movement. 10 seconds, 1 batch, MiniMax H3, 21:9, 1.0 MP.";
    const run = await runSampleThroughUi(page, request, project.id, message);
    const { plan } = run;

    expect(plan.preparationReady, JSON.stringify(plan.error || plan)).toBeTruthy();
    const tags = (plan.references || []).map((r: any) => r.canonical_tag);
    expect(tags).toContain("#RustMarket");
    expect(tags).toContain("@IrisKane");
    expect(tags).toContain("@DaxMeridian");
    expectMilestones(plan, ["references_verified", "dialogue_detected", "action_synthesized", "prompt_compiled"]);
    const prompt = String(plan.compiledPrompt || "");
    expectRuntimeSeparated(prompt);
    // Dialogue preserved verbatim, attributed to speakers
    expect(prompt).toContain('"You are late."');
    expect(prompt).toContain('"The bridge was closed."');
    const action = actionSection(prompt);
    expect(action).toMatch(/Iris Kane says[^"]*"You are late\."/);
    expect(action).toMatch(/Dax Meridian (?:says|replies)[^"]*"The bridge was closed\."/);
    // Dialogue lines are structured, not paraphrased
    const dialogue = plan.directorIntent?.dialogue || [];
    expect(dialogue.map((d: any) => d.line)).toEqual(
      expect.arrayContaining(["You are late.", "The bridge was closed."]),
    );
    expect(run.sceneRow?.prompt).toBe(prompt);
    writeEvidence("c", baseEvidence("C", message, run));
  } finally {
    await deleteProject(request, project.id);
  }
});

// ---------------------------------------------------------------------------
// Sample D — prop-driven physical action
// ---------------------------------------------------------------------------

test("Sample D: prop-driven physical action", async ({ page, request }) => {
  test.setTimeout(240_000);
  const project = await createTempProject(request, "Universal Sample D");
  try {
    await seedEnvironment(request, project.id, "Flooded Arcade", "flooded_arcade");
    await seedProp(request, project.id, "Winch Tower", "winch_tower");
    // Phrasing family: "Create a Timeline scene in …" (Timeline-first).
    const message =
      "Create a Timeline scene in the Flooded Arcade environment reference sheet with the Winch Tower prop reference sheet. " +
      "The winch tower groans and tips sideways into the water, sending a wave across the arcade. " +
      "The tower is over 12 meters tall. 10 seconds, 1 batch, MiniMax H3, 21:9, 1.0 MP.";
    const run = await runSampleThroughUi(page, request, project.id, message);
    const { plan } = run;

    expect(plan.preparationReady, JSON.stringify(plan.error || plan)).toBeTruthy();
    const tags = (plan.references || []).map((r: any) => r.canonical_tag);
    expect(tags).toContain("#FloodedArcade");
    expect(tags).toContain("%WinchTower");
    expectMilestones(plan, ["environment_identified", "props_identified", "references_verified", "action_synthesized", "prompt_compiled"]);
    const prompt = String(plan.compiledPrompt || "");
    expect(prompt).toContain("%WinchTower");
    expectRuntimeSeparated(prompt);
    const action = actionSection(prompt).toLowerCase();
    // Stem-tolerant: "begins to groan and tip sideways" is a valid paraphrase.
    expect(action).toMatch(/\b(?:tips?|topples?|falls?|groans?|collapses?)\b/);
    expect(action).toMatch(/wave/);
    expect(run.sceneRow?.prompt).toBe(prompt);
    writeEvidence("d", baseEvidence("D", message, run));
  } finally {
    await deleteProject(request, project.id);
  }
});

// ---------------------------------------------------------------------------
// Sample E — VFX reveal scene
// ---------------------------------------------------------------------------

test("Sample E: VFX reveal scene", async ({ page, request }) => {
  test.setTimeout(240_000);
  const project = await createTempProject(request, "Universal Sample E");
  try {
    await seedEnvironment(request, project.id, "Obsidian Gate", "obsidian_gate");
    await seedCharacter(request, project.id, "Echo Nine", "echo-nine");
    // Phrasing family: "Prepare a Timeline scene …" (Timeline-first) with a
    // "do not reveal … before …" visibility gate (cinematic negation).
    const message =
      "Prepare a Timeline scene in the Obsidian Gate environment reference sheet with the Character reference of Echo Nine. " +
      "A ring of blue energy ignites above the gate platform. Smoke pours outward across the stone. " +
      "Do not reveal Echo Nine before the energy ring flares. " +
      "Echo Nine steps out of the smoke as the light fades. " +
      "10 seconds, 1 batch, MiniMax H3, 21:9, 1.0 MP.";
    const run = await runSampleThroughUi(page, request, project.id, message);
    const { plan } = run;

    expect(plan.preparationReady, JSON.stringify(plan.error || plan)).toBeTruthy();
    const tags = (plan.references || []).map((r: any) => r.canonical_tag);
    expect(tags).toContain("#ObsidianGate");
    expect(tags).toContain("@EchoNine");
    expectMilestones(plan, ["references_verified", "reveals_identified", "action_synthesized", "prompt_compiled"]);
    const prompt = String(plan.compiledPrompt || "");
    expectRuntimeSeparated(prompt);
    // VFX sequencing + visibility gating
    const lower = prompt.toLowerCase();
    expect(lower).toMatch(/energy|ignites|flares/);
    expect(lower).toMatch(/smoke/);
    expect(lower).toMatch(/do not reveal|remains? hidden|hidden until/);
    // Paraphrase-tolerant: "steps out of the thickening smoke" is valid.
    expect(lower).toMatch(/steps? out of the\b[^.]*?\bsmoke/);
    expect(run.sceneRow?.prompt).toBe(prompt);
    writeEvidence("e", baseEvidence("E", message, run));
  } finally {
    await deleteProject(request, project.id);
  }
});

// ---------------------------------------------------------------------------
// Sample F — multi-beat 20s scene across 2 batches
// ---------------------------------------------------------------------------

test("Sample F: multi-beat cinematic scene across two batches", async ({ page, request }) => {
  test.setTimeout(240_000);
  const project = await createTempProject(request, "Universal Sample F");
  try {
    await seedEnvironment(request, project.id, "Canyon Crossing", "canyon_crossing");
    await seedCharacter(request, project.id, "Jun Park", "jun-park");
    await seedProp(request, project.id, "Signal Kite", "signal_kite");
    // Phrasing family: "Build a scene in Timeline …" (scene-first).
    const message =
      "Build a scene in Timeline in the Canyon Crossing environment reference sheet with the Character reference of Jun Park " +
      "and the Signal Kite prop reference sheet. " +
      "Jun walks in from the left carrying the signal kite. He stops at the bridge edge and looks down. " +
      "He launches the kite into the wind. The kite climbs as the camera rises with it, " +
      "ending on a wide shot of the canyon. Keep the same canyon throughout. " +
      "20 seconds, 2 batches, MiniMax H3, 21:9, 1.0 MP.";
    const run = await runSampleThroughUi(page, request, project.id, message);
    const { plan } = run;

    expect(plan.preparationReady, JSON.stringify(plan.error || plan)).toBeTruthy();
    expect(Number(plan.batchCount)).toBe(2);
    expect(Number(plan.durationSeconds)).toBe(20);
    const tags = (plan.references || []).map((r: any) => r.canonical_tag);
    expect(tags).toContain("#CanyonCrossing");
    expect(tags).toContain("@JunPark");
    expect(tags).toContain("%SignalKite");
    expectMilestones(plan, ["references_verified", "scene_structure_analyzed", "action_synthesized", "prompt_compiled"]);
    const prompt = String(plan.compiledPrompt || "");
    expectRuntimeSeparated(prompt);
    // Reference-declaration chrome ("prop reference sheet") is request
    // language — it must never leak into CAMERA or any creative section.
    for (const section of ["CAMERA", "ACTION", "SHOT", "MOTION"]) {
      const body = promptSection(prompt, section);
      expect(body, `${section} must not carry reference-operation language: ${body}`).not.toMatch(
        /reference\s+(sheet|package|set)|reference\s+of\b/i,
      );
    }
    // Beat structure: ordered events present
    const intent = plan.directorIntent || {};
    const beats = intent.scene_beats || intent.timed_beats || [];
    expect(beats.length).toBeGreaterThanOrEqual(3);
    // Multi-batch Timeline: two windowed batch prompts
    const batches = (run.master?.batchBlocks || []).filter(
      (b: any) => b.migrationMetadata?.sourceProductionRequestId,
    );
    expect(batches.length).toBe(2);
    const timed = (run.master?.batchBlocks || []).flatMap((b: any) =>
      (b.promptSegments || []).filter((s: any) => String(s.text || "").trim()),
    );
    expect(timed.length, "one Timed Prompt regardless of batch count").toBe(1);
    expect(Number(timed[0].start || 0)).toBe(0);
    expect(Number(timed[0].length)).toBe(20);
    const scenePrompt = String(timed[0].text || "");
    expect(scenePrompt).toContain("@JunPark");
    expect(scenePrompt.toLowerCase()).toMatch(/wide shot|kite climbs|camera rises|walks/);
    expect(batches[0].duration?.plannedDuration).toBe(10);
    expect(batches[1].duration?.plannedDuration).toBe(10);
    expectNoDuplicateActionSentences(scenePrompt);
    writeEvidence("f", baseEvidence("F", message, run));
  } finally {
    await deleteProject(request, project.id);
  }
});
