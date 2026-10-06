export type VoiceIdentityBriefInput = {
  sex: "female" | "male";
  age: string;
  accent: string;
  archetype: string;
  script: string;
  promptDetails: string;
  sampleCount: 1 | 2 | 3 | 4;
};

export type VoiceCloneGenerateInput = {
  name: string;
  characterName: string;
  referencePath: string;
  referenceAssetId: string;
  testLine: string;
  sampleCount: 1 | 2 | 3 | 4;
  consentConfirmed: boolean;
};

export function compileVoiceIdentityGenerateBody(input: VoiceIdentityBriefInput): Record<string, unknown> {
  const prompt = input.promptDetails.trim();
  return {
    candidateCount: input.sampleCount,
    sampleCount: input.sampleCount,
    testLine: input.script.trim() || undefined,
    masterPrompt: prompt || undefined,
    designBrief: {
      gender: input.sex === "female" ? "Female" : "Male",
      perceivedAge: input.age,
      accent: input.accent,
      archetype: input.archetype,
      language: "English",
      additionalDirection: prompt,
    },
    method: "design",
  };
}

export function compileVoiceCloneGenerateBody(input: VoiceCloneGenerateInput): Record<string, unknown> {
  return {
    name: input.name,
    reference_path: input.referencePath,
    reference_asset_id: input.referenceAssetId,
    test_line: input.testLine,
    testLine: input.testLine,
    candidateCount: input.sampleCount,
    sampleCount: input.sampleCount,
    consent: {
      source_owner_name: input.characterName,
      performer_name: input.characterName,
      consent_confirmed: input.consentConfirmed,
      synthetic_generation_allowed: input.consentConfirmed,
      confirmed_by: "owner",
    },
  };
}

export function pickRestorableVoiceCandidates(
  voices: Array<{
    id?: string;
    approval_status?: string;
    source_mode?: string;
    updated_at?: string;
    approved_at?: string;
    candidates?: Array<{ id?: string; assetId?: string; asset_id?: string; status?: string }>;
  }>,
): { voiceId: string; sourceMode: string; candidates: Array<{ id?: string; assetId?: string; asset_id?: string; status?: string }> } | null {
  const latestApprovedAt = voices
    .filter((voice) => String(voice.approval_status || "").toLowerCase() === "approved")
    .map((voice) => String(voice.approved_at || voice.updated_at || ""))
    .sort()
    .at(-1) || "";
  const ready = voices
    .filter((voice) => {
      if (!voice.id) return false;
      const mode = String(voice.source_mode || "").toUpperCase();
      if (mode !== "CLONE" && mode !== "DESIGN") return false;
      if (String(voice.approval_status || "").toLowerCase() === "approved") return false;
      if (latestApprovedAt && String(voice.updated_at || "") <= latestApprovedAt) return false;
      const candidates = voice.candidates || [];
      return candidates.some((candidate) => candidate.assetId || candidate.asset_id);
    })
    .sort((left, right) => String(right.updated_at || "").localeCompare(String(left.updated_at || "")));
  const latest = ready[0];
  if (!latest?.id) return null;
  return {
    voiceId: latest.id,
    sourceMode: String(latest.source_mode || ""),
    candidates: latest.candidates || [],
  };
}

export function collectPlayableVoiceSamples(
  voices: Array<{
    id?: string;
    provider?: string;
    candidates?: Array<{
      id?: string;
      assetId?: string;
      asset_id?: string;
      status?: string;
      provider?: string;
      name?: string;
    }>;
  }>,
): Array<{
  id: string;
  status: string;
  assetId: string;
  voiceProfileId: string;
  provider: string;
  name: string;
}> {
  const rows: Array<{
    id: string;
    status: string;
    assetId: string;
    voiceProfileId: string;
    provider: string;
    name: string;
  }> = [];
  for (const voice of voices || []) {
    const voiceProfileId = String(voice?.id || "");
    if (!voiceProfileId) continue;
    for (const candidate of voice?.candidates || []) {
      const id = String(candidate?.id || "");
      const assetId = String(candidate?.assetId || candidate?.asset_id || "");
      if (!id || !assetId) continue;
      if (String(candidate?.status || "").toLowerCase() === "rejected") continue;
      rows.push({
        id,
        status: String(candidate?.status || "ready"),
        assetId,
        voiceProfileId,
        provider: String(candidate?.provider || voice?.provider || ""),
        name: String(candidate?.name || ""),
      });
    }
  }
  return rows;
}

export type PlayableVoiceSample = {
  id: string;
  status: string;
  assetId: string;
  voiceProfileId: string;
  provider: string;
  name: string;
  modelId?: string;
  providerVoiceId?: string;
  createdAt?: string;
};

export function pickNewestGeneratedSample(samples: PlayableVoiceSample[]): PlayableVoiceSample | null {
  const generated = samples.filter(
    (sample) => sample.provider === "elevenlabs" && sample.assetId,
  );
  if (!generated.length) return null;
  return [...generated].sort((left, right) =>
    String(right.createdAt || "").localeCompare(String(left.createdAt || "")),
  )[0];
}

export function currentApprovedSampleId(
  active: {
    approval_status?: string;
    approved_preview_asset_id?: string;
    lineage?: { approvedCandidateId?: string };
    candidates?: Array<{ id?: string; assetId?: string; asset_id?: string }>;
  } | null | undefined,
  activeVoiceProfileId: string,
): string {
  if (!activeVoiceProfileId || !active) return "";
  if (String(active.approval_status || "").toLowerCase() !== "approved") return "";
  const marked = String(active.lineage?.approvedCandidateId || "");
  if (marked) return marked;
  const preview = String(active.approved_preview_asset_id || "");
  const match = (active.candidates || []).find(
    (item) => String(item?.assetId || item?.asset_id || "") === preview && item?.id,
  );
  return match?.id ? String(match.id) : "";
}

export function canApproveSelectedVoice(input: {
  selectedId: string;
  voiceId: string;
  samples: Array<{ id: string; audioUrl?: string }>;
}): boolean {
  if (!input.voiceId || !input.selectedId) return false;
  const selected = input.samples.find((sample) => sample.id === input.selectedId);
  return Boolean(selected?.audioUrl);
}

export function voiceStudioErrorMessage(error: unknown, fallback = "Voice generation failed."): string {
  if (error && typeof error === "object" && "message" in error) {
    const message = String((error as { message?: unknown }).message || "").trim();
    if (message) return message;
  }
  if (error instanceof Error && error.message.trim()) return error.message;
  return fallback;
}

