/**
 * Deterministic support for product-owner human experience review.
 * Does NOT complete or score the human gate.
 * ADEPT_BETA_TARGET=1, workers=1, retries=0.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext } from "@playwright/test";
import { API, BETA_TARGET, waitForAppReady } from "../helpers/app";

const PROJECT_NAME = "The Dreamweaver";
const ARTIFACT_DIR = path.join(
  process.cwd(),
  "docs/release-gate/co-director-creative-operating-intelligence/artifacts/human-gate-support",
);

const JARGON_RE =
  /\b(reloadKey|provenance|graph hash|provider translation|specialist_id|mock flag)\b/i;
const SPECIALIST_VOICE_RE =
  /\b(the producer says|the story editor says|script-supervisor says|as your continuity)\b/i;

function writeArtifact(name: string, data: unknown) {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
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
  expect(named, `${PROJECT_NAME} must exist`).toBeTruthy();
  return named as { id: string; name: string };
}

async function setInitiative(request: APIRequestContext, projectId: string, level: string) {
  const res = await request.put(
    `${API}/api/codirector/projects/${projectId}/creative-operating/initiative`,
    { data: { initiativeLevel: level } },
  );
  expect(res.ok()).toBeTruthy();
  return res.json();
}

async function decide(
  request: APIRequestContext,
  projectId: string,
  message: string,
  extra?: Record<string, unknown>,
) {
  const t0 = Date.now();
  const res = await request.post(
    `${API}/api/codirector/projects/${projectId}/creative-operating/decision`,
    { data: { message, ...(extra || {}) } },
  );
  const ms = Date.now() - t0;
  expect(res.ok()).toBeTruthy();
  const body = await res.json();
  return { body, ms };
}

test.describe.configure({ mode: "serial", retries: 0 });

test.describe("@critical @beta creative operating human-gate support", () => {
  test.skip(!BETA_TARGET, "Set ADEPT_BETA_TARGET=1");

  test("support scenarios for owner review (not a human score)", async ({ request }) => {
    test.setTimeout(600_000);
    await waitForAppReady(request);
    const project = await resolveDreamweaver(request);
    const gates: Record<string, string> = {};
    const latency: Record<string, unknown> = {
      label: "Creative Operating decision-layer latency",
      note: "Not complete Co-Director TTFT or full chat response.",
      modelQueueTimeMs: null,
      firstProviderTokenMs: null,
      firstRenderedTokenMs: null,
      fullResponseCompletionMs: null,
    };

    // 1. Quiet Partner listening
    await setInitiative(request, project.id, "QUIET_PARTNER");
    const quiet = await decide(
      request,
      project.id,
      "The founding researcher returns to the quiet archive and lays down detail without pausing. " +
        "She notices the strained partnership and keeps the tape running. " +
        "I am not asking for feedback yet — please keep listening while I continue.",
    );
    latency.quietDecisionLayerMs = quiet.ms;
    expect(quiet.body.decision?.listeningOnly).toBeTruthy();
    expect(Number(quiet.body.decision?.questionBudget ?? 1)).toBe(0);
    gates["Quiet Partner listening turn"] = quiet.body.decision?.listeningOnly ? "GO" : "FAIL";
    writeArtifact("01_quiet_listening.json", quiet);

    // 2. Proactive Producer development
    await setInitiative(request, project.id, "PROACTIVE_PRODUCER");
    const proactive = await decide(
      request,
      project.id,
      "Help me develop the lead investigator. The role is clear but their deeper motivation is not locked. " +
        "What should we deepen next?",
    );
    latency.proactiveDecisionLayerMs = proactive.ms;
    expect(proactive.body.decision?.listeningOnly).toBeFalsy();
    expect(Number(proactive.body.decision?.questionBudget ?? 0)).toBeGreaterThanOrEqual(1);
    const fwdText = String(proactive.body.decision?.forwardSuggestion?.suggestion || "");
    expect(/Episodes?\s*2\s*[-–—]\s*10|full season production/i.test(fwdText)).toBeFalsy();
    gates["Proactive Producer development turn"] =
      !proactive.body.decision?.listeningOnly && Number(proactive.body.decision?.questionBudget) >= 1
        ? "GO"
        : "FAIL";
    writeArtifact("02_proactive_develop.json", proactive);

    // 3. Hands-On authorship gate (decision posture + composition contract)
    await setInitiative(request, project.id, "HANDS_ON_CO_CREATOR");
    const hands = await decide(
      request,
      project.id,
      "Draft a short exploratory preview of the archive confrontation scene for me.",
    );
    expect(hands.body.decision?.initiativeLevel).toBe("HANDS_ON_CO_CREATOR");
    gates["Hands-On authorship gate"] =
      hands.body.decision?.initiativeLevel === "HANDS_ON_CO_CREATOR" ? "GO" : "FAIL";
    writeArtifact("03_hands_on.json", {
      ...hands,
      compositionHint:
        "Creator chat must ask authorship before major writing; mark drafts proposed/exploratory.",
    });

    // 4. Curiosity thread persistence
    const state = await (
      await request.get(`${API}/api/codirector/projects/${project.id}/creative-operating`)
    ).json();
    expect(Array.isArray(state.curiosityThreads)).toBeTruthy();
    gates["Curiosity thread persistence"] = Array.isArray(state.curiosityThreads) ? "GO" : "FAIL";
    writeArtifact("04_curiosity_state.json", {
      threadCount: (state.curiosityThreads || []).length,
      sample: (state.curiosityThreads || []).slice(0, 3),
    });

    // 5. Dismissed suggestion suppression
    const stampDismiss = `HG-dismiss-${Date.now()}`;
    const ep = await decide(
      request,
      project.id,
      `Episode 1 establishes the archive discovery (${stampDismiss}). ` +
        "Help me think about the next installment without locking canon. " +
        `Open question: what does the partner withhold after the tape (${stampDismiss})?`,
    );
    let fwd = ep.body.decision?.forwardSuggestion as { id?: string; state?: string } | undefined;
    if (!fwd?.id) {
      const pre = await (
        await request.get(`${API}/api/codirector/projects/${project.id}/creative-operating`)
      ).json();
      fwd = (pre.forwardSuggestions || []).find(
        (s: { id?: string; state?: string }) => s.state === "ACTIVE" && s.id,
      );
    }
    if (fwd?.id) {
      const dismiss = await request.post(
        `${API}/api/codirector/projects/${project.id}/creative-operating/forward/dismiss`,
        { data: { suggestionId: fwd.id } },
      );
      expect(dismiss.ok()).toBeTruthy();
      const after = await (
        await request.get(`${API}/api/codirector/projects/${project.id}/creative-operating`)
      ).json();
      const dismissedIds: string[] = after.dismissedSuggestionIds || [];
      const stillActive = (after.forwardSuggestions || []).some(
        (s: { id?: string; state?: string }) => s.id === fwd!.id && s.state === "ACTIVE",
      );
      const suppressed = dismissedIds.includes(String(fwd.id)) || !stillActive;
      expect(suppressed).toBeTruthy();
      gates["Dismissed suggestion suppression"] = suppressed ? "GO" : "FAIL";
      writeArtifact("05_dismiss_forward.json", {
        dismissedId: fwd.id,
        stillActive,
        inDismissedIds: dismissedIds.includes(String(fwd.id)),
      });
    } else {
      gates["Dismissed suggestion suppression"] = "FAIL";
      writeArtifact("05_dismiss_forward.json", { ok: false, reason: "no forward suggestion" });
    }

    // 6. Canon versus possibility
    const knowledge = proactive.body.decision?.importantNewKnowledge || [];
    const badPromote = knowledge.filter(
      (k: { kind?: string; canonState?: string }) =>
        ["INTERPRETATION", "POSSIBILITY"].includes(String(k.kind)) &&
        ["CONFIRMED", "LOCKED"].includes(String(k.canonState)),
    );
    gates["Canon versus possibility"] = badPromote.length === 0 ? "GO" : "FAIL";
    writeArtifact("06_canon_vs_possibility.json", { knowledge, badPromote });

    // 7. Correction and undo
    const correct = await request.post(
      `${API}/api/codirector/projects/${project.id}/creative-operating/identity/correct`,
      {
        data: {
          surfaces: ["Special Agent Morgan", "Agent Morgan"],
          canonicalName: "Special Agent Jordan Morgan",
        },
      },
    );
    expect(correct.ok()).toBeTruthy();
    const correctBody = await correct.json();
    expect(correctBody.ok).toBeTruthy();
    expect(correctBody.undoSupported).toBeTruthy();
    gates["Correction and undo"] = correctBody.ok && correctBody.undoSupported ? "GO" : "FAIL";
    writeArtifact("07_correction.json", correctBody);

    // 8. Script breakdown
    const scriptRes = await request.post(
      `${API}/api/codirector/projects/${project.id}/creative-operating/script/analyze`,
      {
        data: {
          text: `
EPISODE 1

INT. ARCHIVE ROOM - NIGHT

SPECIAL AGENT MORGAN enters.

SPECIAL AGENT MORGAN
We logged the first signal here.

INT. HALLWAY - NIGHT

MORGAN walks alone.
`.trim(),
          filename: "human-gate-ep1.txt",
          installmentHint: "Episode 1",
        },
      },
    );
    expect(scriptRes.ok()).toBeTruthy();
    const scriptBody = await scriptRes.json();
    expect((scriptBody.breakdown?.scenes || []).length).toBeGreaterThan(0);
    gates["Script breakdown"] = (scriptBody.breakdown?.scenes || []).length > 0 ? "GO" : "FAIL";
    writeArtifact("08_script_breakdown.json", scriptBody);

    // 9. Specialist disagreement synthesis + 13. no specialist voice
    const disagree = await decide(
      request,
      project.id,
      "Should we reveal the archive truth in this installment?",
      {
        specialistPositions: {
          "story-editor": "The reveal is emotionally powerful here.",
          producer: "The episode is already overloaded.",
          "script-supervisor": "The reveal conflicts with established chronology.",
          director: "Foreshadow visually now; reveal later.",
        },
      },
    );
    const synth = String(disagree.body.decision?.disagreement?.synthesizedRecommendation || "");
    expect(synth.length).toBeGreaterThan(20);
    expect(SPECIALIST_VOICE_RE.test(synth)).toBeFalsy();
    gates["Specialist disagreement synthesis"] = synth ? "GO" : "FAIL";
    gates["No specialist voice"] = SPECIALIST_VOICE_RE.test(synth) ? "FAIL" : "GO";
    writeArtifact("09_disagreement.json", { synth, decision: disagree.body.decision });

    // 10–11. Standalone film + documentary
    const stamp = Date.now();
    const film = await request.post(`${API}/api/projects`, {
      data: { name: `COI-HG-Film-${stamp}`, primary_project_type: "feature_film" },
    });
    expect(film.ok()).toBeTruthy();
    const filmId = String((await film.json()).id);
    const filmDec = await decide(
      request,
      filmId,
      "This standalone feature film has opening and first act established. " +
        "Help me clarify the next structural turn into Act II — not a sequel trilogy.",
    );
    const filmFmt = String(filmDec.body.decision?.projectFormat || "");
    const filmFwd = String(filmDec.body.decision?.forwardSuggestion?.suggestion || "");
    expect(filmFmt).not.toBe("EPISODIC_SERIES");
    expect(/Episode\s*2/i.test(filmFwd)).toBeFalsy();
    gates["Standalone-film behavior"] =
      filmFmt !== "EPISODIC_SERIES" && !/Episode\s*2/i.test(filmFwd) ? "GO" : "FAIL";
    writeArtifact("10_standalone_film.json", filmDec);

    const doc = await request.post(`${API}/api/projects`, {
      data: { name: `COI-HG-Doc-${stamp}`, primary_project_type: "documentary" },
    });
    expect(doc.ok()).toBeTruthy();
    const docId = String((await doc.json()).id);
    const docDec = await decide(
      request,
      docId,
      "Documentary interviews and archival gaps remain. We need a missing perspective from someone " +
        "who disagrees with the central subject — not episode structure.",
    );
    const docFmt = String(docDec.body.decision?.projectFormat || "");
    const docFwd = String(docDec.body.decision?.forwardSuggestion?.suggestion || "");
    expect(docFmt).not.toBe("EPISODIC_SERIES");
    expect(/Episode\s*2/i.test(docFwd)).toBeFalsy();
    gates["Documentary behavior"] =
      docFmt !== "EPISODIC_SERIES" && !/Episode\s*2/i.test(docFwd) ? "GO" : "FAIL";
    writeArtifact("11_documentary.json", docDec);

    // 12. Latency capture (decision-layer only)
    gates["Latency capture"] =
      typeof latency.quietDecisionLayerMs === "number" &&
      Number(latency.quietDecisionLayerMs) < 5000
        ? "GO"
        : "FAIL";
    writeArtifact("12_latency.json", latency);

    // 14. No technical jargon in synthesized recommendation / forward suggestion
    const jargonHit =
      JARGON_RE.test(synth) ||
      JARGON_RE.test(fwdText) ||
      JARGON_RE.test(String(quiet.body.decision?.surfacedQuestion || ""));
    gates["No technical jargon"] = jargonHit ? "FAIL" : "GO";

    // 15. Project isolation
    const aState = await (
      await request.get(`${API}/api/codirector/projects/${project.id}/creative-operating`)
    ).json();
    const bState = await (
      await request.get(`${API}/api/codirector/projects/${filmId}/creative-operating`)
    ).json();
    expect(aState.projectId).toBe(project.id);
    expect(bState.projectId).toBe(filmId);
    gates["Project isolation"] = aState.projectId !== bState.projectId ? "GO" : "FAIL";

    const failed = Object.entries(gates).filter(([, v]) => v !== "GO");
    writeArtifact("human_gate_support_gates.json", {
      gates,
      failed,
      latency,
      note: "Support only — product-owner scores remain blank in HUMAN_EXPERIENCE_REVIEW.md",
    });
    expect(failed, `Failed support gates: ${JSON.stringify(failed)}`).toEqual([]);
  });
});
