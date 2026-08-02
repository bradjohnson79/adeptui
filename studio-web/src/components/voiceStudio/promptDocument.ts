export type VoicePromptClauses = {
  presentation: string;
  age: string;
  archetypes: string;
  accent: string;
  tuning: string;
};

export type VoicePromptDocument = {
  generatedClauses: VoicePromptClauses;
  userAdditions: string;
  compiledPrompt: string;
};

export type StructuredVoiceFields = {
  voiceType: string;
  age: string;
  archetypes: string[];
  accent: string;
  pitch?: number;
  energy?: number;
  warmth?: number;
  playfulness?: number;
  confidence?: number;
  speakingSpeed?: number;
};

const LEVEL = ["Very low", "Low", "Medium", "High", "Very high"] as const;

function levelLabel(n: number | undefined, fallback = "Medium"): string {
  if (n == null || Number.isNaN(n)) return fallback;
  const i = Math.max(0, Math.min(LEVEL.length - 1, Math.round(n)));
  return LEVEL[i]!;
}

export function buildClauses(fields: StructuredVoiceFields): VoicePromptClauses {
  const arch = fields.archetypes.filter(Boolean);
  return {
    presentation: fields.voiceType ? `${fields.voiceType.toLowerCase()} voice` : "character voice",
    age: fields.age ? `${fields.age.toLowerCase()}` : "",
    archetypes: arch.length
      ? `with a ${arch.map((a) => a.toLowerCase()).join(" / ")} personality`
      : "",
    accent:
      !fields.accent || fields.accent === "No specific accent"
        ? ""
        : fields.accent === "Custom"
          ? ""
          : fields.accent,
    tuning: [
      fields.pitch != null ? `Pitch: ${levelLabel(fields.pitch)}` : "",
      fields.energy != null ? `Energy: ${levelLabel(fields.energy)}` : "",
      fields.warmth != null ? `Warmth: ${levelLabel(fields.warmth)}` : "",
      fields.playfulness != null ? `Playfulness: ${levelLabel(fields.playfulness)}` : "",
      fields.confidence != null ? `Confidence: ${levelLabel(fields.confidence)}` : "",
      fields.speakingSpeed != null ? `Speaking speed: ${levelLabel(fields.speakingSpeed)}` : "",
    ]
      .filter(Boolean)
      .join(". "),
  };
}

export function compilePrompt(clauses: VoicePromptClauses, userAdditions: string): string {
  const head = [
    clauses.age ? `${clauses.age.charAt(0).toUpperCase()}${clauses.age.slice(1)}` : "",
    clauses.presentation,
    clauses.archetypes,
  ]
    .filter(Boolean)
    .join(" ");
  const parts = [
    head ? `${head}.` : "",
    clauses.tuning ? `${clauses.tuning}.` : "",
    clauses.accent ? `${clauses.accent}.` : "",
    (userAdditions || "").trim(),
  ].filter(Boolean);
  return parts.join(" ").replace(/\s+/g, " ").trim();
}

/** Update only the changed clause; preserve userAdditions. */
export function syncPromptDocument(
  prev: VoicePromptDocument | null,
  fields: StructuredVoiceFields,
): VoicePromptDocument {
  const generatedClauses = buildClauses(fields);
  const userAdditions = prev?.userAdditions || "";
  return {
    generatedClauses,
    userAdditions,
    compiledPrompt: compilePrompt(generatedClauses, userAdditions),
  };
}

/** Manual edit: preserve as userAdditions when it diverges from pure generated compile. */
export function applyManualPromptEdit(doc: VoicePromptDocument, edited: string): VoicePromptDocument {
  const generatedOnly = compilePrompt(doc.generatedClauses, "");
  const trimmed = edited.trim();
  if (!trimmed) {
    return { ...doc, userAdditions: "", compiledPrompt: generatedOnly };
  }
  if (trimmed === generatedOnly) {
    return { ...doc, userAdditions: "", compiledPrompt: generatedOnly };
  }
  // If edited starts with generated text, remainder is additions; else treat whole as authored refine.
  if (trimmed.startsWith(generatedOnly)) {
    const additions = trimmed.slice(generatedOnly.length).trim();
    return {
      ...doc,
      userAdditions: additions,
      compiledPrompt: compilePrompt(doc.generatedClauses, additions),
    };
  }
  return {
    ...doc,
    userAdditions: trimmed,
    compiledPrompt: trimmed,
  };
}

export function structuredToDesignBrief(
  fields: StructuredVoiceFields,
  doc: VoicePromptDocument,
): Record<string, string> {
  return {
    gender: fields.voiceType === "Androgynous" ? "Neutral" : fields.voiceType === "Custom" ? "" : fields.voiceType,
    perceivedAge: fields.age === "Custom" ? "" : fields.age,
    archetypes: fields.archetypes.join(", "),
    accent: fields.accent === "Custom" || fields.accent === "No specific accent" ? "" : fields.accent,
    language: "English",
    pitchRange: levelLabel(fields.pitch),
    energy: levelLabel(fields.energy),
    warmth: levelLabel(fields.warmth),
    playfulness: levelLabel(fields.playfulness),
    confidence: levelLabel(fields.confidence),
    speakingPace: levelLabel(fields.speakingSpeed),
    delivery: fields.archetypes.length
      ? fields.archetypes.slice(0, 3).join(", ")
      : "Natural character delivery",
    additionalDirection: doc.userAdditions || "",
    masterPrompt: doc.compiledPrompt,
  };
}

export function fieldsFromBrief(brief: Record<string, unknown> | null | undefined): Partial<StructuredVoiceFields> {
  if (!brief) return {};
  const gender = String(brief.gender || "");
  const age = String(brief.perceivedAge || "");
  const archRaw = String(brief.archetypes || "");
  const archetypes = archRaw
    ? archRaw.split(/[,/]/).map((s) => s.trim()).filter(Boolean)
    : [];
  return {
    voiceType: gender === "Neutral" ? "Androgynous" : gender || undefined,
    age: age || undefined,
    archetypes,
    accent: String(brief.accent || "") || undefined,
  };
}
