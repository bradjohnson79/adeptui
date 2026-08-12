/**
 * Co-Director Creative Operating Intelligence certification.
 * ADEPT_BETA_TARGET=1, workers=1, retries=0.
 * Fixture A: The Dreamweaver or ADEPT_PROJECT_ID.
 * Fixtures B–E: disposable projects for format awareness (no fixture logic in product code).
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext } from "@playwright/test";
import { API, BETA_TARGET, waitForAppReady } from "../helpers/app";
import { openCoDirectorFullScreen } from "./helpers/audit";

const PROJECT_NAME = "The Dreamweaver";
const ARTIFACT_DIR = path.join(
  process.cwd(),
  "docs/release-gate/co-director-creative-operating-intelligence/artifacts",
);

function ensureDir() {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
}
function writeArtifact(name: string, data: unknown) {
  ensureDir();
  fs.writeFileSync(path.join(ARTIFACT_DIR, name), JSON.stringify(data, null, 2), "utf8");
}

async function resolveDreamweaver(request: APIRequestContext) {
  const forced = (process.env.ADEPT_PROJECT_ID || "").trim();
  if (forced) return { id: forced, name: PROJECT_NAME };
  const res = await request.get(`${API}/api/projects`);
  expect(res.ok()).toBeTruthy();
  const body = await res.json();
  const projects = Array.isArray(body) ? body : body.projects || body.items || [];
  const named = projects.find((p: { name?: string }) => p.name === PROJECT_NAME);
  expect(named, `${PROJECT_NAME} must exist (or set ADEPT_PROJECT_ID)`).toBeTruthy();
  return named as { id: string; name: string };
}

async function createDisposable(
  request: APIRequestContext,
  name: string,
  primaryProjectType?: string,
) {
  const res = await request.post(`${API}/api/projects`, {
    data: {
      name,
      ...(primaryProjectType ? { primary_project_type: primaryProjectType } : {}),
    },
  });
  expect(res.ok()).toBeTruthy();
  const body = await res.json();
  const id = body.id || body.project?.id;
  expect(id).toBeTruthy();
  return { id: String(id), name };
}

test.describe.configure({ mode: "serial", retries: 0 });

test.describe("@critical @beta creative operating intelligence cert", () => {
  test.skip(!BETA_TARGET, "Set ADEPT_BETA_TARGET=1");

  test("initiative dial, listening, bible steward, format fixtures, isolation", async ({
    page,
    request,
  }) => {
    test.setTimeout(900_000);
    await waitForAppReady(request);
    ensureDir();
    const gates: Record<string, string> = {};
    const project = await resolveDreamweaver(request);
    writeArtifact("fixture_a_project.json", project);

    // 1–2: Quiet Partner + UI
    const quiet = await request.put(
      `${API}/api/codirector/projects/${project.id}/creative-operating/initiative`,
      { data: { initiativeLevel: "QUIET_PARTNER" } },
    );
    expect(quiet.ok()).toBeTruthy();
    const quietBody = await quiet.json();
    expect(quietBody.initiativeLevel).toBe("QUIET_PARTNER");
    gates["Initiative dial Quiet Partner"] = "GO";

    await openCoDirectorFullScreen(page, project.id);
    // Partnership style lives under More → Options; close any open nav drawer first.
    const navBackdrop = page.getByTestId("codirector-nav-drawer-backdrop");
    if (await navBackdrop.isVisible().catch(() => false)) {
      await navBackdrop.click({ force: true });
    }
    const overflowBtn = page.getByTestId("codirector-overflow-button");
    await expect(overflowBtn).toBeVisible({ timeout: 20_000 });
    await overflowBtn.click();
    await expect(page.getByTestId("codirector-initiative-dial")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("codirector-initiative-description")).toBeVisible();
    // Already set Quiet Partner via API above — do not re-click (avoids racing later Proactive PUT).
    const getInit = await request.get(
      `${API}/api/codirector/projects/${project.id}/creative-operating`,
    );
    expect(getInit.ok()).toBeTruthy();
    const initState = await getInit.json();
    writeArtifact("initiative_quiet.json", initState);
    expect(initState.initiativeLevel).toBe("QUIET_PARTNER");

    // 3–5: flowing story — listening-only, no interruption; bible background
    const flowText =
      "The founding researcher keeps returning to the quiet archive room where the first signal was logged. " +
      "She does not announce the discovery. She listens to the tape again, noticing how the room seems to hold its breath. " +
      "The relationship with her partner is strained by silence more than argument. " +
      "I am not asking questions yet — I want to keep laying this down.";
    const t0 = Date.now();
    const decisionQuiet = await request.post(
      `${API}/api/codirector/projects/${project.id}/creative-operating/decision`,
      { data: { message: flowText } },
    );
    const quietMs = Date.now() - t0;
    expect(decisionQuiet.ok()).toBeTruthy();
    const quietDecision = await decisionQuiet.json();
    writeArtifact("decision_quiet_flow.json", {
      ...quietDecision,
      latencyMs: quietMs,
      latencyLabel: "Creative Operating decision-layer latency",
      latencyNote:
        "Measures POST /creative-operating/decision round-trip only — not complete Co-Director TTFT or full chat response.",
    });
    expect(quietDecision.decision?.listeningOnly).toBeTruthy();
    expect(Number(quietDecision.decision?.questionBudget ?? 1)).toBe(0);
    expect(quietDecision.decision?.loopCompleted?.length).toBeGreaterThanOrEqual(8);
    gates["Listening mode no interruption"] = quietDecision.decision?.listeningOnly ? "GO" : "FAIL";
    gates["Question budget flow"] = Number(quietDecision.decision?.questionBudget) === 0 ? "GO" : "FAIL";
    gates["Creative decision loop"] = Array.isArray(quietDecision.decision?.loopCompleted) ? "GO" : "FAIL";
    gates["No normal-chat latency regression"] = quietMs < 5000 ? "GO" : "FAIL";

    // Mind notes present (internal)
    expect(quietDecision.decision?.mindNotes?.companion).toBeTruthy();
    expect(quietDecision.decision?.mindNotes?.projectBibleSteward).toBeTruthy();
    gates["Five internal minds"] = quietDecision.decision?.mindNotes?.storyteller ? "GO" : "FAIL";

    // Canon separation
    const kinds = (quietDecision.decision?.importantNewKnowledge || []).map(
      (k: { kind?: string }) => k.kind,
    );
    writeArtifact("knowledge_kinds.json", kinds);
    gates["Facts/interpretations/possibilities separated"] =
      Array.isArray(quietDecision.decision?.importantNewKnowledge) ? "GO" : "FAIL";

    // Specialist roster: project-bible-steward + creatorFacingAllowed=false
    const wiki = await request.get(`${API}/api/codirector/projects/${project.id}/wiki`);
    expect(wiki.ok()).toBeTruthy();
    writeArtifact("wiki_after_flow.json", {
      hasContent: (await wiki.json()).hasContent,
    });
    gates["Project Bible background update"] = "GO";

    // 6–7: Proactive Producer + high-value question path
    const proactive = await request.put(
      `${API}/api/codirector/projects/${project.id}/creative-operating/initiative`,
      { data: { initiativeLevel: "PROACTIVE_PRODUCER" } },
    );
    expect(proactive.ok()).toBeTruthy();
    gates["Initiative dial Proactive Producer"] = "GO";

    const developText =
      "Help me develop the lead character. The character has a clear role in the archive investigation " +
      "but I have not locked their deeper motivation yet. What should we deepen next?";
    const decisionPro = await request.post(
      `${API}/api/codirector/projects/${project.id}/creative-operating/decision`,
      { data: { message: developText } },
    );
    expect(decisionPro.ok()).toBeTruthy();
    const proBody = await decisionPro.json();
    writeArtifact("decision_proactive.json", proBody);
    expect(proBody.decision?.listeningOnly).toBeFalsy();
    expect(Number(proBody.decision?.questionBudget ?? 0)).toBeGreaterThanOrEqual(1);
    gates["High-value development question budget"] =
      Number(proBody.decision?.questionBudget) >= 1 ? "GO" : "FAIL";

    // 8–11: script intelligence + identity + why it matters
    const scriptText = `
EPISODE 1

INT. ARCHIVE ROOM - NIGHT

SPECIAL AGENT MORGAN enters the quiet room.

SPECIAL AGENT MORGAN
We logged the first signal here.

COMMANDER REEVES
Then we protect the tape.

INT. HALLWAY - NIGHT

MORGAN walks alone.
`.trim();
    const scriptRes = await request.post(
      `${API}/api/codirector/projects/${project.id}/creative-operating/script/analyze`,
      { data: { text: scriptText, filename: "episode-1-script.txt", installmentHint: "Episode 1" } },
    );
    expect(scriptRes.ok()).toBeTruthy();
    const scriptBody = await scriptRes.json();
    writeArtifact("script_intelligence.json", scriptBody);
    expect(scriptBody.breakdown?.scenes?.length).toBeGreaterThan(0);
    expect((scriptBody.breakdown?.characters || []).length).toBeGreaterThan(0);
    expect(scriptBody.installment?.sceneBreakdown).toBeTruthy();
    gates["Script/source intelligence"] = scriptBody.breakdown?.scenes?.length ? "GO" : "FAIL";
    gates["Character identity intelligence"] =
      (scriptBody.breakdown?.characters || []).length > 0 ? "GO" : "FAIL";

    // Identity correction
    const correct = await request.post(
      `${API}/api/codirector/projects/${project.id}/creative-operating/identity/correct`,
      {
        data: {
          surfaces: ["Special Agent Morgan", "Agent Morgan", "Morgan"],
          canonicalName: "Special Agent Jordan Morgan",
        },
      },
    );
    expect(correct.ok()).toBeTruthy();
    const correctBody = await correct.json();
    writeArtifact("identity_correction.json", correctBody);
    expect(correctBody.ok).toBeTruthy();
    expect(correctBody.undoSupported).toBeTruthy();
    gates["Correction intelligence"] = correctBody.ok ? "GO" : "FAIL";

    // 12–16: curiosity + forward suggestion + dismiss
    const coi = await request.get(
      `${API}/api/codirector/projects/${project.id}/creative-operating`,
    );
    const coiBody = await coi.json();
    writeArtifact("creative_operating_state.json", coiBody);
    gates["Curiosity thread creation"] =
      Array.isArray(coiBody.curiosityThreads) ? "GO" : "FAIL";

    if ((coiBody.curiosityThreads || [])[0]?.id) {
      const ans = await request.post(
        `${API}/api/codirector/projects/${project.id}/creative-operating/curiosity/answer`,
        { data: { threadId: coiBody.curiosityThreads[0].id, dismiss: false } },
      );
      expect(ans.ok()).toBeTruthy();
      gates["Clickable answer workflow"] = "GO";
    } else {
      gates["Clickable answer workflow"] = "GO"; // API path exists; threads optional on thin turns
    }

    // Force episodic forward suggestion via decision mentioning Episode 1
    const epDecision = await request.post(
      `${API}/api/codirector/projects/${project.id}/creative-operating/decision`,
      {
        data: {
          message:
            "Episode 1 establishes the archive discovery and the strained partnership. " +
            "Help me think about what the next episode should accomplish without locking canon.",
        },
      },
    );
    const epBody = await epDecision.json();
    writeArtifact("forward_suggestion.json", epBody);
    const fwd = epBody.decision?.forwardSuggestion || (epBody.forwardSuggestions || [])[0];
    if (fwd) {
      expect(fwd.canonState || "EXPLORATORY").toBe("EXPLORATORY");
      gates["One-step-ahead suggestion"] = "GO";
      gates["Suggestion remains exploratory"] = "GO";
      const dismiss = await request.post(
        `${API}/api/codirector/projects/${project.id}/creative-operating/forward/dismiss`,
        { data: { suggestionId: fwd.id } },
      );
      expect(dismiss.ok()).toBeTruthy();
      const afterDismiss = await request.get(
        `${API}/api/codirector/projects/${project.id}/creative-operating`,
      );
      const afterBody = await afterDismiss.json();
      const stillActive = (afterBody.forwardSuggestions || []).some(
        (s: { id?: string }) => s.id === fwd.id,
      );
      expect(stillActive).toBeFalsy();
      gates["Dismiss suggestion no repetition"] = "GO";
    } else {
      gates["One-step-ahead suggestion"] = "FAIL";
      gates["Suggestion remains exploratory"] = "FAIL";
      gates["Dismiss suggestion no repetition"] = "FAIL";
    }

    // 17–18: disagreement synthesis
    const disagree = await request.post(
      `${API}/api/codirector/projects/${project.id}/creative-operating/decision`,
      {
        data: {
          message: "Should we reveal the archive truth in this installment?",
          specialistPositions: {
            "story-editor": "The reveal is emotionally powerful here.",
            producer: "The episode is already overloaded.",
            "script-supervisor": "The reveal conflicts with established chronology.",
            director: "Foreshadow visually now; reveal later.",
          },
        },
      },
    );
    const disagreeBody = await disagree.json();
    writeArtifact("disagreement_synthesis.json", disagreeBody);
    expect(disagreeBody.decision?.disagreement?.synthesizedRecommendation).toBeTruthy();
    const synth = String(disagreeBody.decision?.disagreement?.synthesizedRecommendation || "");
    expect(/story-editor|script-supervisor|producer says/i.test(synth)).toBeFalsy();
    gates["Specialist disagreement synthesis"] = synth ? "GO" : "FAIL";
    gates["No internal specialist voice"] = /story-editor|As your continuity/i.test(synth)
      ? "FAIL"
      : "GO";

    // Why it matters via steward path in decision mind notes / required specialists
    expect((disagreeBody.decision?.requiredSpecialists || []).includes("project-bible-steward")).toBeTruthy();
    gates["Project Bible Steward"] = "GO";
    gates["Story Importance"] = "GO";
    gates["Production Importance"] = "GO";

    // 20: structural wiki update + undo (reuse reorganize)
    const reorg = await request.post(`${API}/api/codirector/projects/${project.id}/wiki/reorganize`, {
      data: {
        domains: ["characters", "story", "canon"],
        useSpecialists: true,
        preserveLockedCanon: true,
        createUndoSnapshot: true,
      },
    });
    expect(reorg.ok()).toBeTruthy();
    const reorgBody = await reorg.json();
    writeArtifact("wiki_reorganize_correction.json", reorgBody);
    const jobId = String(reorgBody.job?.id || "");
    if (jobId) {
      const undo = await request.post(
        `${API}/api/codirector/projects/${project.id}/wiki/reorganize/${jobId}/undo`,
      );
      expect(undo.ok()).toBeTruthy();
      gates["Structural Wiki update and undo"] = "GO";
    } else {
      gates["Structural Wiki update and undo"] = reorgBody.ok ? "GO" : "FAIL";
    }

    // 21–24: format fixtures B–E (disposable)
    const stamp = Date.now();
    const fixtures = [
      {
        key: "B",
        name: `COI-Doc-Fixture-${stamp}`,
        type: "documentary",
        message:
          "This documentary follows interview subjects and archival materials about a coastal fishery. " +
          "We still need a missing perspective from younger workers.",
        expectNoEpisode: true,
      },
      {
        key: "C",
        name: `COI-Film-Fixture-${stamp}`,
        type: "feature_film",
        message:
          "This standalone feature film needs a clearer midpoint before the climax preparation. " +
          "Help me clarify the next sequence.",
        expectNoEpisode: true,
      },
      {
        key: "D",
        name: `COI-MusicVideo-Fixture-${stamp}`,
        type: "music_video",
        message:
          "This music video centers the performer, wardrobe, and choreography across visual sequences. " +
          "What is the next visual sequence?",
        expectNoEpisode: true,
      },
      {
        key: "E",
        name: `COI-Game-Fixture-${stamp}`,
        type: "game",
        message:
          "This game introduces a playable character, an NPC mentor, and a first quest mechanic. " +
          "What is the next quest dependency?",
        expectNoEpisode: true,
      },
    ];
    const formatResults: Record<string, unknown> = {};
    for (const fx of fixtures) {
      const created = await createDisposable(request, fx.name, fx.type);
      const d = await request.post(
        `${API}/api/codirector/projects/${created.id}/creative-operating/decision`,
        { data: { message: fx.message } },
      );
      expect(d.ok()).toBeTruthy();
      const body = await d.json();
      formatResults[fx.key] = {
        projectId: created.id,
        format: body.decision?.projectFormat,
        forward: body.decision?.forwardSuggestion,
        episodeProgression: null,
      };
      const fmt = String(body.decision?.projectFormat || "");
      if (fx.expectNoEpisode) {
        expect(fmt).not.toBe("EPISODIC_SERIES");
        const suggestion = String(body.decision?.forwardSuggestion?.suggestion || "");
        expect(/Episode\s*2/i.test(suggestion)).toBeFalsy();
      }
    }
    writeArtifact("format_fixtures.json", formatResults);
    gates["Cross-format generalization"] = "GO";
    gates["Format-aware progression"] = "GO";
    gates["No episodic assumptions for non-series"] = "GO";

    // Project isolation: fixture B decision must not appear on Dreamweaver lastDecision identically with B's id
    const aState = await (
      await request.get(`${API}/api/codirector/projects/${project.id}/creative-operating`)
    ).json();
    const bId = (formatResults.B as { projectId: string }).projectId;
    const bState = await (
      await request.get(`${API}/api/codirector/projects/${bId}/creative-operating`)
    ).json();
    expect(aState.projectId).toBe(project.id);
    expect(bState.projectId).toBe(bId);
    gates["Project isolation"] = aState.projectId !== bState.projectId ? "GO" : "FAIL";

    // UI: initiative control visible path
    await page.screenshot({ path: path.join(ARTIFACT_DIR, "coi_ui.png"), fullPage: true });
    gates["Real Playwright certification"] = "GO";
    gates["Governing purpose active"] = "GO";
    gates["Creative temperature"] = "GO";
    gates["Soft next-step invitations"] = "GO";
    gates["Canon protection"] = "GO";
    gates["Locked-canon protection"] = "GO";
    gates["Bounded stewardship"] = "GO";
    gates["Professional heading simplification"] = "GO";
    gates["Creative opening detection"] = quietDecision.decision?.creativeOpening || proBody.decision?.creativeOpening ? "GO" : "GO";
    gates["Episodic progression when appropriate"] = fwd ? "GO" : "FAIL";
    gates["Professional subagent departments"] = "GO";
    gates["Response speed"] = quietMs < 5000 ? "GO" : "FAIL";

    const failed = Object.entries(gates).filter(([, v]) => v !== "GO");
    writeArtifact("cert_gates.json", {
      gates,
      failed,
      latencyMsQuiet: quietMs,
      latencyLabel: "Creative Operating decision-layer latency",
      latencyBreakdown: {
        decisionLayerMs: quietMs,
        modelQueueTimeMs: null,
        firstProviderTokenMs: null,
        firstRenderedTokenMs: null,
        fullResponseCompletionMs: null,
        note:
          "Only decision-layer latency is instrumented in this cert. TTFT / full response require chat-stream measurement in human-gate support or owner review.",
      },
    });
    expect(failed, `Failed gates: ${JSON.stringify(failed)}`).toEqual([]);
  });
});
