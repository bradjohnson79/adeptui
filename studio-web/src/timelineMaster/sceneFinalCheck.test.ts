import { describe, expect, it } from "vitest";
import {
  FINAL_CHECK_CATEGORIES,
  LIFECYCLE_STATES,
  STUB_CATEGORIES,
  VERDICT_ACCEPTED,
  applyApiRepairDecision,
  applyLocalAutoRepair,
  autoRepairEligibleFindings,
  buildCategoryShell,
  classifyRuntimeKind,
  creatorVerdictToLifecycle,
  emptyStubCategory,
  ingestDialogueQc,
  isLocalRuntime,
  mapDialogueFinding,
  repairGateForRuntime,
  shouldOpenFinalCheckAfterStitch,
  crossModalityUncertainty,
  mapContinuityFinding,
  mapEquipmentFinding,
  buildRetakePack,
  PIPELINE_CATEGORIES,
  EQUIPMENT_AUTHORITY_SOURCE,
} from "./sceneFinalCheck";

function fc(partial: Partial<{ retakeEligible: boolean; autoDestroy: boolean; acceptanceEligible: boolean; creativeTaste: boolean }> = {}) {
  return {
    retakeEligible: false,
    autoDestroy: false,
    acceptanceEligible: false,
    creativeTaste: false,
    authoritySource: "dialogue_manifest",
    ...partial,
  };
}

describe("sceneFinalCheck lifecycle", () => {
  it("lists all canonical states", () => {
    expect(LIFECYCLE_STATES).toContain("BATCHES_COMPLETE");
    expect(LIFECYCLE_STATES).toContain("FINAL_CHECK");
    expect(LIFECYCLE_STATES).toContain("SCENE_FINISHED_WITH_ACCEPTED_ISSUES");
    expect(LIFECYCLE_STATES).toContain("SCENE_NOT_FINISHED");
  });

  it("maps creator verdicts", () => {
    expect(creatorVerdictToLifecycle("FINAL CHECK PASSED / SCENE FINISHED")).toBe("SCENE_FINISHED");
    expect(creatorVerdictToLifecycle("FOUND ISSUES / SCENE NOT FINISHED")).toBe("SCENE_NOT_FINISHED");
    expect(creatorVerdictToLifecycle(VERDICT_ACCEPTED)).toBe("SCENE_FINISHED_WITH_ACCEPTED_ISSUES");
  });
});

describe("category shell", () => {
  it("includes all categories and stubs are not_run not PASS", () => {
    const shell = buildCategoryShell([]);
    expect(shell.map((c) => c.category)).toEqual([...FINAL_CHECK_CATEGORIES]);
    for (const cat of STUB_CATEGORIES) {
      const row = shell.find((c) => c.category === cat)!;
      expect(row.status).toBe("not_run");
      expect(row.status).not.toBe("pass");
    }
    expect(emptyStubCategory("continuity").status).toBe("not_run");
  });

  it("hooks dialogue/language/speaker from QC findings", () => {
    const findings = ingestDialogueQc({
      verdict: "FAIL",
      findings: [
        {
          code: "UNAUTHORIZED_LANGUAGE",
          severity: "error",
          finalCheck: fc({ retakeEligible: true }),
        },
        {
          code: "WRONG_SPEAKER",
          severity: "error",
          finalCheck: fc({ retakeEligible: true }),
        },
      ],
    });
    const shell = buildCategoryShell(findings);
    const by = Object.fromEntries(shell.map((c) => [c.category, c]));
    expect(by.language.status).toBe("fail");
    expect(by.speaker.status).toBe("fail");
    expect(by.continuity.status).toBe("not_run");
    expect(by.equipment.status).toBe("not_run");
  });
});

describe("sidecar eligibility authority", () => {
  it("consumes finalCheck sidecar — does not re-derive from codes", () => {
    const hard = mapDialogueFinding({
      code: "LINE_FIDELITY_FAIL",
      severity: "error",
      finalCheck: fc({ retakeEligible: true }),
    });
    expect(hard.retakeEligible).toBe(true);
    expect(hard.autoDestroy).toBe(false);
    expect(hard.authoritySource).toBe("dialogue_manifest");

    const miss = mapDialogueFinding(
      {
        code: "OMNI_TRANSCRIPT_MISS",
        severity: "error",
        finalCheck: fc({ retakeEligible: false }),
      },
      "UNCERTAIN",
    );
    expect(miss.retakeEligible).toBe(false);
    expect(miss.confidence).toBe("low");

    const overridden = mapDialogueFinding({
      code: "LINE_FIDELITY_FAIL",
      severity: "error",
      retakeEligible: true,
      finalCheck: fc({ retakeEligible: false }),
    });
    expect(overridden.retakeEligible).toBe(false);
  });

  it("excludes Creative from auto-repair", () => {
    const creative = mapDialogueFinding({
      code: "CREATIVE_GRADE",
      severity: "info",
      taxonomy: "Creative",
      creative: true,
      finalCheck: fc({ creativeTaste: true, retakeEligible: false }),
    });
    expect(creative.taxonomy).toBe("Creative");
    const shell = buildCategoryShell([creative]);
    expect(autoRepairEligibleFindings(shell)).toEqual([]);
  });
});

describe("local vs API repair gate", () => {
  it("classifies via locality/capability not generator name strings", () => {
    expect(isLocalRuntime({ locality: "local" })).toBe(true);
    expect(isLocalRuntime({ locality: "hosted" })).toBe(false);
    expect(classifyRuntimeKind({ capability: { locality: "local" } })).toBe("local");
    expect(classifyRuntimeKind({ capability: { locality: "hosted" } })).toBe("api");
    expect(
      classifyRuntimeKind({
        generatorId: "seedance-2.0",
        adapterProfile: { byGeneratorId: { "seedance-2.0": { runtimeKind: "api" } } },
      }),
    ).toBe("api");
  });

  it("local Hard → permission not_required", () => {
    const gate = repairGateForRuntime("local", true);
    expect(gate.permission).toBe("not_required");
    expect(gate.requiresApproval).toBe(false);
    const applied = applyLocalAutoRepair(gate);
    expect(applied.permission).toBe("not_required");
    expect(applied.lifecycleStatus).toBe("REPAIRING");
    expect(applied.apiCallsDelta).toBe(0);
  });

  it("API Hard → one approval; decline = 0 api calls; Keep Current accepted", () => {
    const gate = repairGateForRuntime("api", true);
    expect(gate.permission).toBe("required");
    expect(gate.oneApprovalPerCycle).toBe(true);
    const declined = applyApiRepairDecision(gate, "decline");
    expect(declined.apiCallsDelta).toBe(0);
    expect(declined.apiCallCount).toBe(0);
    expect(declined.lifecycleStatus).toBe("SCENE_NOT_FINISHED");
    const kept = applyApiRepairDecision(gate, "keep_current");
    expect(kept.lifecycleStatus).toBe("SCENE_FINISHED_WITH_ACCEPTED_ISSUES");
    expect(kept.apiCallsDelta).toBe(0);
  });
});

describe("stitch hook", () => {
  it("opens Final Check after stitch when no terminal finished state", () => {
    expect(shouldOpenFinalCheckAfterStitch({ sceneStitch: { assetId: "s1" } })).toBe(true);
    expect(
      shouldOpenFinalCheckAfterStitch({
        sceneStitch: { assetId: "s1" },
        sceneFinalCheck: { lifecycleStatus: "SCENE_FINISHED", categories: [] },
      }),
    ).toBe(false);
    expect(
      shouldOpenFinalCheckAfterStitch({
        sceneStitch: { assetId: "s1" },
        sceneFinalCheck: { lifecycleStatus: "FINAL_CHECK", categories: [] },
      }),
    ).toBe(true);
  });
});


describe("cross-modality law", () => {
  it("empty ASR + loud energy → uncertain, not auto-retake, not destroy", () => {
    const xm = crossModalityUncertainty({
      primaryMiss: true,
      contradictingModality: true,
      code: "OMNI_TRANSCRIPT_MISS",
    });
    expect(xm.uncertain).toBe(true);
    expect(xm.autoRetake).toBe(false);
    expect(xm.autoDestroy).toBe(false);
    expect(xm.blocksFinished).toBe(true);
  });

  it("weak visual + CRS conflict → creator review, never auto-destroy", () => {
    const xm = crossModalityUncertainty({
      primaryMiss: true,
      contradictingModality: true,
      code: "IDENTITY_UNCERTAIN_CRS_CONFLICT",
    });
    expect(xm.needsCreatorReview).toBe(true);
    expect(xm.autoRetake).toBe(false);
    expect(xm.autoDestroy).toBe(false);
  });
});

describe("Slice B taxonomy", () => {
  it("SPEECH_WHEN_SILENCE_EXPECTED → Hard dialogue; sidecar retakeEligible", () => {
    const f = mapDialogueFinding({
      code: "SPEECH_WHEN_SILENCE_EXPECTED",
      severity: "error",
      finalCheck: fc({ retakeEligible: true }),
    });
    expect(f.category).toBe("dialogue");
    expect(f.taxonomy).toBe("Hard");
    expect(f.retakeEligible).toBe(true);
  });

  it("UNAUTHORIZED_BACKGROUND_SPEAKER → Hard speaker (+ dialogue mirror)", () => {
    const f = mapDialogueFinding({
      code: "UNAUTHORIZED_BACKGROUND_SPEAKER",
      severity: "error",
      finalCheck: fc({ retakeEligible: true }),
    });
    expect(f.category).toBe("speaker");
    expect((f as any).alsoCategories).toContain("dialogue");
    const shell = buildCategoryShell([f]);
    const by = Object.fromEntries(shell.map((c) => [c.category, c]));
    expect(by.speaker.status).toBe("fail");
    expect(by.dialogue.status).toBe("fail");
  });

  it("MODALITY_CONFLICT → UNCERTAIN; audio not-PASS; not auto-destroy", () => {
    const f = mapDialogueFinding(
      {
        code: "MODALITY_CONFLICT",
        severity: "error",
        finalCheck: {
          ...fc({ retakeEligible: false }),
          modalityConflict: true,
          modalities: ["asr", "energy"],
          conflictReason: "empty ASR + loud energy",
        } as any,
      },
      "UNCERTAIN",
    );
    expect(f.retakeEligible).toBe(false);
    expect(f.confidence).toBe("low");
    expect((f as any).alsoCategories).toContain("audio");
    const shell = buildCategoryShell([f]);
    const by = Object.fromEntries(shell.map((c) => [c.category, c]));
    expect(by.dialogue.status).toBe("uncertain");
    expect(by.audio.status).toBe("uncertain");
    expect(by.audio.status).not.toBe("pass");
  });

  it("OMNI_TRANSCRIPT_MISS stays UNCERTAIN", () => {
    const f = mapDialogueFinding(
      { code: "OMNI_TRANSCRIPT_MISS", severity: "error", finalCheck: fc({ retakeEligible: false }) },
      "UNCERTAIN",
    );
    expect(f.retakeEligible).toBe(false);
    expect(f.confidence).toBe("low");
  });
});

describe("Continuity + Equipment pipelines", () => {
  it("continuity pipeline not_run without Omni packet (not PASS)", () => {
    const shell = buildCategoryShell([]);
    const by = Object.fromEntries(shell.map((c) => [c.category, c]));
    expect(by.continuity.status).toBe("not_run");
    expect(by.continuity.status).not.toBe("pass");
    expect(PIPELINE_CATEGORIES.has("continuity")).toBe(true);
  });

  it("Hard continuity high-conf established → retakeEligible", () => {
    const f = mapContinuityFinding({
      code: "CONTINUITY_TELEPORT",
      severity: "error",
      confidence: "high",
      establishedAuthority: true,
      finalCheck: fc({ retakeEligible: true }),
    });
    expect(f.category).toBe("continuity");
    expect(f.retakeEligible).toBe(true);
  });

  it("weak visual + CRS → no auto", () => {
    const f = mapContinuityFinding(
      { code: "CONTINUITY_CRS_TEMPORAL_CONFLICT", confidence: "low", weakVisual: true },
      "UNCERTAIN",
    );
    expect(f.retakeEligible).toBe(false);
    expect(f.confidence).toBe("low");
  });

  it("equipment Hard crew/boom uses RCP authority; creative camera never auto", () => {
    const hard = mapEquipmentFinding({
      code: "UNAUTHORIZED_PRODUCTION_EQUIPMENT",
      confidence: "high",
      message: "boom mic operator in frame",
      finalCheck: { ...fc({ retakeEligible: true }), authoritySource: EQUIPMENT_AUTHORITY_SOURCE } as any,
    });
    expect(hard.category).toBe("equipment");
    expect(hard.retakeEligible).toBe(true);
    expect(hard.authoritySource).toContain("retake_context_package");
    expect((hard as any).alsoCategories).toContain("camera");
    const creative = mapEquipmentFinding({ code: "CREATIVE_PUSH_IN", creative: true });
    expect(creative.taxonomy).toBe("Creative");
    expect(creative.retakeEligible).toBe(false);
  });

  it("PRESERVE pack fields present", () => {
    const f = mapDialogueFinding({
      code: "UNAUTHORIZED_LANGUAGE",
      severity: "error",
      finalCheck: fc({ retakeEligible: true }),
    });
    const pack = buildRetakePack([f]);
    expect(pack.WHAT_WRONG).toBeTruthy();
    expect(pack.WHAT_CHANGE).toBeTruthy();
    expect(pack.WHAT_PRESERVE).toBeTruthy();
    expect(pack.WINDOW).toBeTruthy();
    expect(pack.AUTHORITIES).toBeTruthy();
    expect(pack.METHOD).toBeTruthy();
    expect(pack.neverInventAuthorityFromBadOutput).toBe(true);
  });
});

describe("Slice C WRONG_SPEAKER", () => {
  it("WRONG_SPEAKER + sidecar lands in speaker (and dialogue) Hard taxonomy", () => {
    const f = mapDialogueFinding({
      code: "WRONG_SPEAKER",
      severity: "error",
      finalCheck: fc({ retakeEligible: true }),
    });
    expect(f.category).toBe("speaker");
    expect(f.taxonomy).toBe("Hard");
    expect(f.retakeEligible).toBe(true);
    expect((f as any).alsoCategories).toContain("dialogue");
    const shell = buildCategoryShell([f]);
    const by = Object.fromEntries(shell.map((c) => [c.category, c]));
    expect(by.speaker.status).toBe("fail");
    expect(by.dialogue.status).toBe("fail");
  });
});
