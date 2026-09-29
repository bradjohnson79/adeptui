/**
 * Co-Director Final Check — FE lifecycle + category shell contracts.
 * Mirrors studio-api/.../scene_final_check.py. Does not replace sceneRenderProgress.
 */

export const LIFECYCLE_STATES = [
  "RENDERING",
  "BATCHES_COMPLETE",
  "STITCHING",
  "FINAL_CHECK",
  "REPAIRING",
  "REVERIFYING",
  "SCENE_FINISHED",
  "SCENE_FINISHED_WITH_ACCEPTED_ISSUES",
  "SCENE_NOT_FINISHED",
] as const;

export type SceneLifecycleStatus = (typeof LIFECYCLE_STATES)[number];

export const FINAL_CHECK_CATEGORIES = [
  "dialogue",
  "language",
  "speaker",
  "identity",
  "environment",
  "continuity",
  "camera",
  "equipment",
  "audio",
  "technical",
] as const;

export type FinalCheckCategory = (typeof FINAL_CHECK_CATEGORIES)[number];

export const STUB_CATEGORIES = new Set<FinalCheckCategory>([
  "identity",
  "environment",
  "technical",
]);

export const DIALOGUE_OWNED_CATEGORIES = new Set<FinalCheckCategory>([
  "dialogue",
  "language",
  "speaker",
]);

export type FinalCheckTaxonomy = "Hard" | "Soft" | "Creative";

export type RuntimeKind = "local" | "api";

export type RepairPermission =
  | "not_required"
  | "required"
  | "granted"
  | "declined"
  | "keep_current";

export const VERDICT_PASSED = "FINAL CHECK PASSED / SCENE FINISHED";
export const VERDICT_FOUND_ISSUES = "FOUND ISSUES / SCENE NOT FINISHED";
export const VERDICT_ACCEPTED = "SCENE FINISHED ISSUES ACCEPTED BY CREATOR";

/** Dialogue Authority findings[].finalCheck sidecar — eligibility authority. */
export type DialogueFinalCheckSidecar = {
  retakeEligible: boolean;
  autoDestroy: boolean;
  acceptanceEligible: boolean;
  creativeTaste: boolean;
  authoritySource: string;
  note?: string;
};

export type FinalCheckFinding = {
  category: FinalCheckCategory | string;
  taxonomy: FinalCheckTaxonomy;
  code?: string | null;
  severity?: string;
  retakeEligible: boolean;
  autoDestroy?: boolean;
  acceptanceEligible?: boolean;
  creativeTaste?: boolean;
  authoritySource?: string;
  confidence?: "high" | "low";
  message?: string | null;
  source?: string;
  finalCheck?: DialogueFinalCheckSidecar;
};

export type FinalCheckCategoryResult = {
  category: FinalCheckCategory | string;
  status: "pass" | "fail" | "not_run" | "uncertain";
  taxonomy?: FinalCheckTaxonomy | null;
  findings: FinalCheckFinding[];
  source?: string;
  note?: string;
};

export type SceneFinalCheckRepairGate = {
  runtimeKind: RuntimeKind;
  permission: RepairPermission;
  apiCallCount: number;
  requiresApproval?: boolean;
  actions?: string[];
  oneApprovalPerCycle?: boolean;
  decision?: string;
  apiCallsDelta?: number;
  lifecycleStatus?: SceneLifecycleStatus | string;
  creatorVerdict?: string;
  note?: string;
  reuse?: string;
};

export type RetakePack = {
  WHAT_WRONG: string[];
  WHAT_CHANGE: string;
  WHAT_PRESERVE: string;
  WINDOW: Record<string, unknown>;
  AUTHORITIES: string[];
  METHOD: string;
  neverInventAuthorityFromBadOutput: boolean;
  oneIntervalForCompatibleDefects?: boolean;
  groupedFindingCount?: number;
};

export type SceneFinalCheckState = {
  lifecycleStatus: SceneLifecycleStatus | string;
  creatorVerdict?: string | null;
  openedAt?: string | null;
  closedAt?: string | null;
  categories: FinalCheckCategoryResult[];
  repairGate?: SceneFinalCheckRepairGate | null;
  stitchAssetId?: string | null;
  retakeLoopCount?: number;
  maxRetakeLoops?: number;
  unresolvedBlocking?: boolean;
  autoRepairEligibleCount?: number;
  policy?: string;
  retakePack?: RetakePack | Record<string, unknown> | null;
};

const DA_CODE_TO_CATEGORY: Record<string, FinalCheckCategory> = {
  WRONG_LANGUAGE: "language",
  UNAUTHORIZED_LANGUAGE: "language",
  SPOKEN_LANGUAGE_AUTHORITY_MISSING: "language",
  WRONG_SPEAKER: "speaker",
  ADLIB_OR_NONLITERAL: "dialogue",
  LINE_FIDELITY_FAIL: "dialogue",
  SILENT_WHEN_SPEECH_EXPECTED: "dialogue",
  OMNI_TRANSCRIPT_MISS: "dialogue",
  SPEECH_WHEN_SILENCE_EXPECTED: "dialogue",
  UNAUTHORIZED_BACKGROUND_SPEAKER: "speaker",
  MODALITY_CONFLICT: "dialogue",
  OMNI_UNAVAILABLE: "dialogue",
  OBSERVED_LANGUAGE_UNKNOWN: "language",
};

const DA_NO_AUTO = new Set(["OMNI_TRANSCRIPT_MISS", "MODALITY_CONFLICT", "OMNI_UNAVAILABLE", "OBSERVED_LANGUAGE_UNKNOWN"]);

export function isLocalRuntime(args: {
  locality?: string | null;
  executionType?: string | null;
  capability?: { locality?: string | null; executionType?: string | null } | null;
}): boolean {
  const cap = args.capability;
  if (cap) {
    const loc = String(cap.locality || "").toLowerCase();
    if (loc === "local") return true;
    if (loc === "hosted") return false;
    const exec = String(cap.executionType || "").toLowerCase();
    if (exec === "api") return false;
    if (exec === "local" || exec === "comfy" || exec === "comfyui") return true;
  }
  const loc = String(args.locality || "").toLowerCase();
  if (loc === "local") return true;
  if (loc === "hosted" || loc === "api" || loc === "cloud") return false;
  const exec = String(args.executionType || "").toLowerCase();
  if (exec === "api") return false;
  if (exec === "local" || exec === "comfy" || exec === "comfyui") return true;
  return false;
}

export function classifyRuntimeKind(args: {
  locality?: string | null;
  executionType?: string | null;
  capability?: { locality?: string | null; executionType?: string | null } | null;
  generatorId?: string | null;
  adapterProfile?: {
    runtimeKind?: RuntimeKind;
    locality?: string;
    executionType?: string;
    byGeneratorId?: Record<string, { runtimeKind?: RuntimeKind }>;
  } | null;
}): RuntimeKind {
  const profile = args.adapterProfile;
  if (profile?.runtimeKind === "local" || profile?.runtimeKind === "api") return profile.runtimeKind;
  if (isLocalRuntime(args)) return "local";
  if (profile?.byGeneratorId && args.generatorId) {
    const entry = profile.byGeneratorId[args.generatorId];
    if (entry?.runtimeKind === "local" || entry?.runtimeKind === "api") return entry.runtimeKind;
  }
  return "api";
}

export function emptyStubCategory(category: FinalCheckCategory | string): FinalCheckCategoryResult {
  return {
    category,
    status: "not_run",
    taxonomy: null,
    findings: [],
    source: "stub",
    note: "Category not owned by Omni Dialogue QC yet — not run (not PASS).",
  };
}

/** Consume Dialogue Authority finding — sidecar is eligibility authority. */
export function mapDialogueFinding(
  finding: Record<string, unknown>,
  verdict?: string | null,
): FinalCheckFinding {
  const code = String(finding.code || "").trim();
  const severity = String(finding.severity || "").trim().toLowerCase();
  const sidecar = (finding.finalCheck && typeof finding.finalCheck === "object"
    ? (finding.finalCheck as DialogueFinalCheckSidecar)
    : null);

  const category = DA_CODE_TO_CATEGORY[code] || "dialogue";
  let taxonomy: FinalCheckTaxonomy =
    severity === "error" || code in DA_CODE_TO_CATEGORY ? "Hard" : "Soft";
  if (finding.taxonomy === "Hard" || finding.taxonomy === "Soft" || finding.taxonomy === "Creative") {
    taxonomy = finding.taxonomy;
  }
  if (finding.creative === true || sidecar?.creativeTaste) taxonomy = "Creative";

  let confidence: "high" | "low" = "high";
  const confRaw = String(finding.confidence || "").toLowerCase();
  if (confRaw === "high" || confRaw === "low") confidence = confRaw;
  else if (DA_NO_AUTO.has(code) || String(verdict || "").toUpperCase() === "UNCERTAIN") confidence = "low";

  let retakeEligible: boolean;
  let autoDestroy = false;
  let acceptanceEligible = false;
  let creativeTaste = taxonomy === "Creative";
  let authoritySource = "dialogue_manifest";

  if (sidecar) {
    retakeEligible = Boolean(sidecar.retakeEligible);
    autoDestroy = Boolean(sidecar.autoDestroy);
    acceptanceEligible = Boolean(sidecar.acceptanceEligible);
    creativeTaste = Boolean(sidecar.creativeTaste);
    authoritySource = String(sidecar.authoritySource || "dialogue_manifest");
    if (creativeTaste) {
      taxonomy = "Creative";
      retakeEligible = false;
    }
  } else {
    if (typeof finding.retakeEligible === "boolean") retakeEligible = finding.retakeEligible;
    else if (taxonomy === "Creative" || DA_NO_AUTO.has(code) || confidence === "low") retakeEligible = false;
    else retakeEligible = taxonomy === "Hard";
  }

  const alsoCategories: string[] = [];
  if (code === "UNAUTHORIZED_BACKGROUND_SPEAKER" || code === "WRONG_SPEAKER") alsoCategories.push("dialogue");
  const modalityConflict = Boolean((sidecar as any)?.modalityConflict || finding.modalityConflict);
  if (code === "MODALITY_CONFLICT" || code === "OMNI_TRANSCRIPT_MISS" || modalityConflict) {
    alsoCategories.push("audio");
  }
  if (code === "MODALITY_CONFLICT" || code === "OMNI_TRANSCRIPT_MISS") confidence = "low";
  const finalCheckOut: any = sidecar ? { ...sidecar } : {
    retakeEligible, autoDestroy, acceptanceEligible, creativeTaste, authoritySource,
  };
  if (sidecar && (sidecar as any).modalityConflict != null) finalCheckOut.modalityConflict = Boolean((sidecar as any).modalityConflict);
  if (sidecar && (sidecar as any).modalities) finalCheckOut.modalities = (sidecar as any).modalities;
  if (sidecar && (sidecar as any).conflictReason) finalCheckOut.conflictReason = (sidecar as any).conflictReason;
  return {
    category,
    taxonomy,
    code: code || null,
    severity: String(finding.severity || (taxonomy === "Hard" ? "error" : "warning")),
    retakeEligible,
    autoDestroy,
    acceptanceEligible,
    creativeTaste,
    authoritySource,
    confidence,
    message: (finding.message as string) || (finding.reason as string) || null,
    source: "dialogueQcDiagnostics",
    alsoCategories,
    modalityConflict,
    finalCheck: finalCheckOut,
  } as FinalCheckFinding;
}

export function ingestDialogueQc(qc: Record<string, unknown> | null | undefined): FinalCheckFinding[] {
  if (!qc || typeof qc !== "object") return [];
  const verdict = String(qc.verdict || "").toUpperCase();
  const findings = Array.isArray(qc.findings) ? qc.findings : [];
  const out: FinalCheckFinding[] = [];
  for (const f of findings) {
    if (f && typeof f === "object") out.push(mapDialogueFinding(f as Record<string, unknown>, verdict));
  }
  return out;
}


export const PIPELINE_CATEGORIES = new Set<FinalCheckCategory>([
  "continuity",
  "camera",
  "equipment",
  "audio",
]);

export const EQUIPMENT_AUTHORITY_SOURCE = "retake_context_package.prompt_law_crew_out";

export function emptyPipelineNotRun(
  category: FinalCheckCategory | string,
  note: string,
): FinalCheckCategoryResult {
  return {
    category,
    status: "not_run",
    taxonomy: null,
    findings: [],
    source: "pipeline_ready",
    note,
  };
}

export function buildCategoryShell(findings: FinalCheckFinding[]): FinalCheckCategoryResult[] {
  const expanded: FinalCheckFinding[] = [...findings];
  for (const f of findings) {
    const also = (f as FinalCheckFinding & { alsoCategories?: string[] }).alsoCategories || [];
    for (const a of also) {
      expanded.push({ ...f, category: a, source: f.source });
    }
  }
  const byCat: Record<string, FinalCheckFinding[]> = {};
  for (const c of FINAL_CHECK_CATEGORIES) byCat[c] = [];
  for (const f of expanded) {
    const cat = String(f.category || "dialogue");
    if (!byCat[cat]) byCat[cat] = [];
    byCat[cat].push(f);
  }
  return FINAL_CHECK_CATEGORIES.map((cat) => {
    if (STUB_CATEGORIES.has(cat)) return emptyStubCategory(cat);
    const catFindings = byCat[cat] || [];
    if (PIPELINE_CATEGORIES.has(cat) && !catFindings.length) {
      const note =
        cat === "continuity"
          ? "Continuity Final Check pipeline ready. No Omni continuity QC packet — not run (not PASS)."
          : cat === "audio"
            ? "Audio surfaces modality-conflict from Dialogue Authority sidecar. No conflict — not run."
            : `${cat} pipeline ready. Authority=${EQUIPMENT_AUTHORITY_SOURCE}. No Omni packet — not run (not PASS).`;
      return emptyPipelineNotRun(cat, note);
    }
    if (!catFindings.length) {
      return {
        category: cat,
        status: "pass" as const,
        taxonomy: null,
        findings: [],
        source: "dialogueQcDiagnostics",
        note: "No Dialogue Authority findings for this slice.",
      };
    }
    const hasHard = catFindings.some((f) => f.taxonomy === "Hard");
    const hasUncertain = catFindings.some(
      (f) =>
        f.confidence === "low" ||
        f.code === "MODALITY_CONFLICT" ||
        f.code === "OMNI_TRANSCRIPT_MISS" ||
        Boolean((f as any).modalityConflict),
    );
    let status: FinalCheckCategoryResult["status"] = "pass";
    if (hasHard && catFindings.some((f) => f.confidence !== "low" || f.retakeEligible)) status = "fail";
    else if (hasUncertain) status = "uncertain";
    else if (hasHard) status = "fail";
    if (
      catFindings.some((f) => f.code === "MODALITY_CONFLICT" || f.code === "OMNI_TRANSCRIPT_MISS") &&
      !catFindings.some((f) => f.retakeEligible && f.confidence === "high")
    ) {
      status = "uncertain";
    }
    return {
      category: cat,
      status,
      taxonomy: hasHard ? "Hard" : "Soft",
      findings: catFindings,
      source: catFindings[0]?.source || "dialogueQcDiagnostics",
    };
  });
}


export function autoRepairEligibleFindings(categories: FinalCheckCategoryResult[]): FinalCheckFinding[] {
  const out: FinalCheckFinding[] = [];
  for (const cat of categories) {
    for (const f of cat.findings || []) {
      if (f.taxonomy === "Creative" || f.creativeTaste) continue;
      if (f.autoDestroy) continue;
      if (!f.retakeEligible) continue;
      if (f.confidence === "low") continue;
      out.push(f);
    }
  }
  return out;
}

export function repairGateForRuntime(
  runtimeKind: RuntimeKind,
  hasAutoEligible: boolean,
): SceneFinalCheckRepairGate {
  if (!hasAutoEligible) {
    return {
      runtimeKind,
      permission: "not_required",
      apiCallCount: 0,
      requiresApproval: false,
      actions: [],
      note: "No auto-repair-eligible findings",
    };
  }
  if (runtimeKind === "local") {
    return {
      runtimeKind: "local",
      permission: "not_required",
      apiCallCount: 0,
      requiresApproval: false,
      actions: ["auto_retake"],
      note: "Local Hard → auto Manifest-driven Re-Take → reverify. NO permission prompt.",
      reuse: "consume_dialogue_retake_repair / dialogueRetakeRepair",
    };
  }
  return {
    runtimeKind: "api",
    permission: "required",
    apiCallCount: 0,
    requiresApproval: true,
    actions: ["repair_automatically", "review_first", "keep_current"],
    note: "API Hard → propose → one approval per repair cycle. Decline = zero extra API calls.",
    oneApprovalPerCycle: true,
  };
}

export function applyApiRepairDecision(
  gate: SceneFinalCheckRepairGate,
  decision: "repair_automatically" | "review_first" | "keep_current" | "decline" | "dismiss",
): SceneFinalCheckRepairGate {
  const out: SceneFinalCheckRepairGate = { ...gate, decision, apiCallCount: gate.apiCallCount || 0 };
  if (decision === "decline" || decision === "dismiss") {
    return {
      ...out,
      permission: "declined",
      apiCallsDelta: 0,
      lifecycleStatus: "SCENE_NOT_FINISHED",
      creatorVerdict: VERDICT_FOUND_ISSUES,
    };
  }
  if (decision === "keep_current") {
    return {
      ...out,
      permission: "keep_current",
      apiCallsDelta: 0,
      lifecycleStatus: "SCENE_FINISHED_WITH_ACCEPTED_ISSUES",
      creatorVerdict: VERDICT_ACCEPTED,
    };
  }
  if (decision === "repair_automatically") {
    return {
      ...out,
      permission: "granted",
      apiCallsDelta: 1,
      lifecycleStatus: "REPAIRING",
    };
  }
  return { ...out, permission: "required", apiCallsDelta: 0, lifecycleStatus: "FINAL_CHECK" };
}

export function applyLocalAutoRepair(gate: SceneFinalCheckRepairGate): SceneFinalCheckRepairGate {
  return {
    ...gate,
    permission: "not_required",
    requiresApproval: false,
    apiCallCount: gate.apiCallCount || 0,
    apiCallsDelta: 0,
    lifecycleStatus: "REPAIRING",
    decision: "auto_retake",
  };
}

export function creatorVerdictToLifecycle(verdict: string): SceneLifecycleStatus {
  const v = String(verdict || "").trim();
  if (v === VERDICT_PASSED || v.startsWith("FINAL CHECK PASSED")) return "SCENE_FINISHED";
  if (v === VERDICT_ACCEPTED || v.toUpperCase().includes("ISSUES ACCEPTED")) {
    return "SCENE_FINISHED_WITH_ACCEPTED_ISSUES";
  }
  return "SCENE_NOT_FINISHED";
}

export function isFinalCheckOpen(state: SceneFinalCheckState | null | undefined): boolean {
  if (!state) return false;
  return ["FINAL_CHECK", "REPAIRING", "REVERIFYING", "SCENE_NOT_FINISHED"].includes(
    String(state.lifecycleStatus || ""),
  );
}

export function shouldOpenFinalCheckAfterStitch(master: {
  sceneStitch?: { assetId?: string } | null;
  sceneFinalCheck?: SceneFinalCheckState | null;
} | null | undefined): boolean {
  if (!master?.sceneStitch?.assetId) return false;
  const life = master.sceneFinalCheck?.lifecycleStatus;
  if (!life) return true;
  return ["BATCHES_COMPLETE", "STITCHING", "FINAL_CHECK", "SCENE_NOT_FINISHED"].includes(String(life));
}


/** PRIMARY LAW (cross-modality): absence of evidence ≠ evidence of absence when another modality contradicts. */
export function crossModalityUncertainty(args: {
  primaryMiss: boolean;
  contradictingModality: boolean;
  code?: string | null;
}): {
  uncertain: boolean;
  autoRetake: boolean;
  autoDestroy: boolean;
  needsCreatorReview: boolean;
  blocksFinished: boolean;
  reason: string;
  law: string;
} {
  if (args.primaryMiss && args.contradictingModality) {
    return {
      uncertain: true,
      autoRetake: false,
      autoDestroy: false,
      needsCreatorReview: true,
      blocksFinished: true,
      reason:
        "Cross-modality contradiction: weak/single-modality miss is UNCERTAIN, not evidence of absence — creator review; never auto-destroy local gen",
      law: "ABSENCE_OF_EVIDENCE_NEQ_EVIDENCE_OF_ABSENCE",
    };
  }
  return {
    uncertain: false,
    autoRetake: false,
    autoDestroy: false,
    needsCreatorReview: false,
    blocksFinished: Boolean(args.primaryMiss),
    reason: "No cross-modality contradiction",
    law: "ABSENCE_OF_EVIDENCE_NEQ_EVIDENCE_OF_ABSENCE",
  };
}


export const CONTINUITY_HARD_CODES = new Set([
  "CONTINUITY_BREAK",
  "CONTINUITY_TELEPORT",
  "CONTINUITY_SIDES_FLIP",
  "CONTINUITY_WARDROBE",
  "CONTINUITY_ENV_VS_CANON",
  "CONTINUITY_AUTHORITY_VIOLATION",
]);

export const EQUIPMENT_HARD_CODES = new Set([
  "UNAUTHORIZED_PRODUCTION_EQUIPMENT",
  "DIEGETIC_CREW",
  "BOOM_IN_FRAME",
  "CAMERA_CREW_IN_FRAME",
  "CREW_IN_FRAME",
]);

export function mapContinuityFinding(
  finding: Record<string, unknown>,
  verdict?: string | null,
): FinalCheckFinding {
  const code = String(finding.code || "").trim().toUpperCase();
  const sidecar = (finding.finalCheck && typeof finding.finalCheck === "object"
    ? (finding.finalCheck as DialogueFinalCheckSidecar)
    : null);
  const confRaw = String(finding.confidence || "").toLowerCase();
  const established = Boolean(
    finding.establishedAuthority ||
      finding.vsCanon ||
      (sidecar &&
        ["continuity_canon", "crs_temporal", "scene_canon", "wardrobe_canon", "sides_canon"].includes(
          String(sidecar.authoritySource || ""),
        )),
  );
  const invented = Boolean(finding.inventedFromBadFrame || finding.fromBadFrame);
  const uncertain =
    confRaw === "low" ||
    String(verdict || "").toUpperCase() === "UNCERTAIN" ||
    Boolean(finding.weakVisual) ||
    invented ||
    code.includes("UNCERTAIN") ||
    code.includes("CRS_TEMPORAL");

  let taxonomy: FinalCheckTaxonomy =
    CONTINUITY_HARD_CODES.has(code) || String(finding.severity) === "error" ? "Hard" : "Soft";
  if (finding.creative === true || sidecar?.creativeTaste) taxonomy = "Creative";

  let confidence: "high" | "low" = uncertain ? "low" : confRaw === "low" ? "low" : "high";
  let retakeEligible = false;
  if (sidecar) retakeEligible = Boolean(sidecar.retakeEligible);
  else retakeEligible = taxonomy === "Hard" && confidence === "high" && established && !invented && !uncertain;
  if (invented || taxonomy === "Creative") retakeEligible = false;

  return {
    category: "continuity",
    taxonomy,
    code: code || "CONTINUITY_BREAK",
    severity: String(finding.severity || (taxonomy === "Hard" ? "error" : "warning")),
    retakeEligible,
    autoDestroy: Boolean(sidecar?.autoDestroy),
    acceptanceEligible: Boolean(sidecar?.acceptanceEligible),
    creativeTaste: taxonomy === "Creative",
    authoritySource: String(
      sidecar?.authoritySource || finding.authoritySource || (established ? "continuity_canon" : "omni_continuity"),
    ),
    confidence,
    message: (finding.message as string) || (finding.reason as string) || null,
    source: "omniContinuityDiagnostics",
    finalCheck: sidecar || {
      retakeEligible,
      autoDestroy: false,
      acceptanceEligible: false,
      creativeTaste: taxonomy === "Creative",
      authoritySource: String(finding.authoritySource || "continuity_canon"),
    },
  };
}

export function mapEquipmentFinding(
  finding: Record<string, unknown>,
  verdict?: string | null,
): FinalCheckFinding & { alsoCategories?: string[] } {
  const code = String(finding.code || "UNAUTHORIZED_PRODUCTION_EQUIPMENT").trim().toUpperCase();
  const sidecar = (finding.finalCheck && typeof finding.finalCheck === "object"
    ? (finding.finalCheck as DialogueFinalCheckSidecar)
    : null);
  if (finding.creative === true || finding.creativeTaste === true || code.startsWith("CREATIVE_")) {
    return {
      category: "camera",
      taxonomy: "Creative",
      code,
      severity: "info",
      retakeEligible: false,
      autoDestroy: false,
      acceptanceEligible: true,
      creativeTaste: true,
      authoritySource: "creative_suggestion",
      confidence: "high",
      message: (finding.message as string) || "Creative camera suggestion",
      source: "omniEquipmentDiagnostics",
      alsoCategories: [],
      finalCheck: {
        retakeEligible: false,
        autoDestroy: false,
        acceptanceEligible: true,
        creativeTaste: true,
        authoritySource: "creative_suggestion",
      },
    };
  }
  const confRaw = String(finding.confidence || "").toLowerCase();
  let confidence: "high" | "low" = confRaw === "low" ? "low" : "high";
  if (String(verdict || "").toUpperCase() === "UNCERTAIN") confidence = "low";
  let retakeEligible = sidecar ? Boolean(sidecar.retakeEligible) : confidence === "high";
  if (confidence === "low") retakeEligible = false;
  return {
    category: "equipment",
    taxonomy: "Hard",
    code: EQUIPMENT_HARD_CODES.has(code) ? code : "UNAUTHORIZED_PRODUCTION_EQUIPMENT",
    severity: String(finding.severity || "error"),
    retakeEligible,
    autoDestroy: Boolean(sidecar?.autoDestroy),
    acceptanceEligible: Boolean(sidecar?.acceptanceEligible),
    creativeTaste: false,
    authoritySource: String(sidecar?.authoritySource || EQUIPMENT_AUTHORITY_SOURCE),
    confidence,
    message:
      (finding.message as string) ||
      (finding.observation as string) ||
      "Unauthorized diegetic crew/equipment",
    source: "omniEquipmentDiagnostics",
    alsoCategories: ["camera"],
    finalCheck: sidecar || {
      retakeEligible,
      autoDestroy: false,
      acceptanceEligible: false,
      creativeTaste: false,
      authoritySource: EQUIPMENT_AUTHORITY_SOURCE,
    },
  };
}

export function buildRetakePack(findings: FinalCheckFinding[]): RetakePack {
  const eligible = findings.filter(
    (f) => f.retakeEligible && f.taxonomy === "Hard" && f.confidence !== "low" && !f.creativeTaste,
  );
  const authorities = Array.from(
    new Set(eligible.map((f) => String(f.authoritySource || f.finalCheck?.authoritySource || "dialogue_manifest"))),
  );
  return {
    WHAT_WRONG: eligible.map((f) => String(f.message || f.code || "defect")),
    WHAT_CHANGE: "Restore approved production intent for grouped Hard defects",
    WHAT_PRESERVE:
      "Approved Timeline R2V continuity, Timed Prompt bytes, non-defective ranges, cast identity refs, location/Quarters",
    WINDOW: { mode: "smallest_compatible_interval", note: "ONE interval for compatible defects" },
    AUTHORITIES: authorities.length ? authorities : ["dialogueAuthorityManifest"],
    METHOD: "Authority-driven Re-Take; smallest interval; never invent authority from bad output",
    neverInventAuthorityFromBadOutput: true,
    oneIntervalForCompatibleDefects: true,
    groupedFindingCount: eligible.length,
  };
}

