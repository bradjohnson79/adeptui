import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import {
  applyApprovedIdentityToSession,
  avatarGenerateBlockers,
  buildAvatarPrompt,
  canGenerateAvatarSession,
  emptyAvatarSession,
  estimateDialogueSeconds,
  pickApprovedCharacterStill,
  validateAvatarSession,
  type AvatarMode,
  type AvatarPresentationPlan,
  type AvatarProjectJob,
  type AvatarRuntimeGate,
  type AvatarSession,
} from "../avatar/types";
import { CharacterReferenceAssetPicker } from "./CoDirector/characters/CharacterReferenceAssetPicker";
import { useBindCoDirectorWorkspace, useOpenCoDirector } from "./CoDirector";
import type { VoicePerformanceRecord } from "../contracts/voicePerformanceM410";
import { buildAiGuidedSetupPath } from "../setup/navigation";
import type { SetupComponentStatus } from "../setup/types";
import type { Project } from "../types";
import type { EditorTab } from "../workspacePrefs";

type ProfileItem = {
  id: string;
  name: string;
  kind: string;
  media_path?: string;
  tag?: string;
  stillAssetId?: string | null;
};

type ReviewTab = "sections" | "takes" | "progress" | "completed";

type ApprovedVoiceChoice = {
  recordId: string;
  takeId: string;
  audioAssetId: string;
  voiceIdentityId: string;
  providerId: string;
  title: string;
  subtitle: string;
  updatedAt: string;
};

type VoiceReadiness = {
  approvedVoice?: boolean;
  readyForPerformance?: boolean;
  readyForTestingPerformance?: boolean;
  testingVoiceReady?: boolean;
  pronunciationCount?: number;
  reactionReadyCount?: number;
  voiceVersionId?: string | null;
};

type ScriptDocumentChoice = {
  id: string;
  title: string;
  updatedAt?: string;
};

type ScriptSceneChoice = {
  sceneHeadingId: string;
  sceneHeading: string;
  sceneNumber?: string;
  productionStatus?: string;
  sceneId?: string | null;
};

type RetakeActionChoice = {
  id: string;
  label: string;
  note: string;
  toolId?: "avatar.request_retake" | "avatar.repair_lipsync";
};

const MODE_CARDS: Array<{
  id: AvatarMode;
  label: string;
  blurb: string;
  shotSize: string;
}> = [
  {
    id: "talking_portrait",
    label: "Talking Head",
    blurb: "A close, steady presenter frame for direct delivery.",
    shotSize: "close-up",
  },
  {
    id: "cinematic_character",
    label: "Presenter",
    blurb: "A clean long-form host setup for explainers and updates.",
    shotSize: "medium close-up",
  },
  {
    id: "full_body",
    label: "Full-Body Presenter",
    blurb: "More room for gesture, posture, and walk-on presentation.",
    shotSize: "medium full",
  },
  {
    id: "existing_video_lipsync",
    label: "Existing Video Dubbing",
    blurb: "Replace dialogue on an already-shot presenter clip.",
    shotSize: "match source video",
  },
];

const STYLE_CARDS = [
  {
    id: "direct_presenter",
    label: "Direct Presenter",
    blurb: "Clear, confident delivery straight to camera.",
    tone: "confident",
    angle: "direct-to-camera",
    style: "cinematic live-action presenter",
  },
  {
    id: "warm_host",
    label: "Warm Host",
    blurb: "Friendly and welcoming without overplaying it.",
    tone: "friendly",
    angle: "direct-to-camera",
    style: "warm studio host",
  },
  {
    id: "guided_explainer",
    label: "Guided Explainer",
    blurb: "Calm instruction with a little more space for motion.",
    tone: "calm",
    angle: "slightly off-camera",
    style: "clean explainer performance",
  },
  {
    id: "stylized_performance",
    label: "Stylized Performance",
    blurb: "More graphic, designed, or cinematic styling.",
    tone: "serious",
    angle: "three-quarter",
    style: "stylized presenter performance",
  },
] as const;

const FRAMING_CARDS = [
  {
    id: "tight_headline",
    label: "Tight Headline",
    blurb: "Great for punchy lines and strong eye contact.",
    shotSize: "close-up",
    lens: "85mm",
  },
  {
    id: "medium_presenter",
    label: "Presenter Frame",
    blurb: "Balanced framing for most long-form speaking work.",
    shotSize: "medium close-up",
    lens: "50mm",
  },
  {
    id: "desk_or_podium",
    label: "Desk or Podium",
    blurb: "A little wider when hands or props matter.",
    shotSize: "medium shot",
    lens: "35mm",
  },
  {
    id: "full_stage",
    label: "Full Stage",
    blurb: "Use when the whole body and movement sell the performance.",
    shotSize: "full body",
    lens: "28mm",
  },
] as const;

const BACKGROUND_CARDS = [
  {
    id: "studio_gradient",
    label: "Studio",
    blurb: "Simple polished backdrop for presenter work.",
    backgroundMode: "solid",
    notes: "Soft studio gradient with clean separation.",
  },
  {
    id: "branded_set",
    label: "Branded Set",
    blurb: "A designed stage for show formats and recurring series.",
    backgroundMode: "environment",
    notes: "Branded presenter set with room for subtle depth.",
  },
  {
    id: "soft_environment",
    label: "Environment",
    blurb: "A believable location that still keeps the presenter clear.",
    backgroundMode: "environment",
    notes: "Natural environment with presenter-friendly lighting.",
  },
  {
    id: "graphic_canvas",
    label: "Graphic Canvas",
    blurb: "A stylized background for title cards or punchier segments.",
    backgroundMode: "generated",
    notes: "Graphic canvas background with clean contrast.",
  },
] as const;

const DURATION_CARDS = [
  {
    id: "quick_update",
    label: "Quick Update",
    blurb: "Best for a short presenter beat or hook.",
    seconds: 4,
  },
  {
    id: "story_section",
    label: "Story Section",
    blurb: "A balanced section size for long-form assembly.",
    seconds: 6,
  },
  {
    id: "chapter_pass",
    label: "Chapter Pass",
    blurb: "Use when you want a fuller section before retakes.",
    seconds: 8,
  },
] as const;

const PROVIDER_ORDER = [
  "longcat-video-avatar-1-5-local",
  "infinitetalk-local",
  "musetalk-1-5-local",
  "echomimic-v2-local",
] as const;

const REVIEW_TABS: ReviewTab[] = ["sections", "takes", "progress", "completed"];

const RETAKE_ACTIONS: RetakeActionChoice[] = [
  {
    id: "reperform_sentence",
    label: "Re-perform Sentence",
    note: "Re-perform the drifting sentence while matching the surrounding delivery.",
    toolId: "avatar.request_retake",
  },
  {
    id: "resync_paragraph",
    label: "Re-sync Paragraph",
    note: "Re-sync this paragraph while preserving the neighboring continuity.",
    toolId: "avatar.request_retake",
  },
  {
    id: "regenerate_gesture",
    label: "Regenerate Gesture",
    note: "Refresh the gesture timing without changing the rest of the section.",
    toolId: "avatar.request_retake",
  },
  {
    id: "correct_pronunciation",
    label: "Correct Pronunciation",
    note: "Correct pronunciation while keeping the rest of the performance intact.",
    toolId: "avatar.request_retake",
  },
  {
    id: "replace_background",
    label: "Replace Background",
    note: "Replace the background while preserving the presenter continuity.",
    toolId: "avatar.request_retake",
  },
  {
    id: "regenerate_section",
    label: "Regenerate Section",
    note: "Regenerate only this section and preserve the completed neighboring sections.",
    toolId: "avatar.request_retake",
  },
  {
    id: "repair_lip_sync",
    label: "Repair Lip-Sync",
    note: "Repair lip sync with MuseTalk while preserving the current section as reference.",
    toolId: "avatar.repair_lipsync",
  },
];

function Tip({ text }: { text: string }) {
  return (
    <span className="avatar-inline-tip" title={text} aria-label={text}>
      {" "}
      (?)
    </span>
  );
}

function displayTime(value?: string | null): string {
  if (!value) return "Just now";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Just now";
  return parsed.toLocaleString();
}

function formatDurationMs(value = 0): string {
  const totalSeconds = Math.max(0, Math.round(value / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return minutes ? `${minutes}m ${seconds}s` : `${seconds}s`;
}

function sectionStatusLabel(status?: string): string {
  switch (status) {
    case "planning":
      return "Planning";
    case "queued":
      return "Queued";
    case "running":
    case "generating":
      return "Generating";
    case "paused":
      return "Paused";
    case "assembling":
      return "Assembling";
    case "completed":
      return "Completed";
    case "failed":
      return "Failed";
    case "cancelled":
      return "Cancelled";
    case "retake_requested":
      return "Retake requested";
    case "approved":
      return "Approved";
    default:
      return "Planned";
  }
}

function normalizeSession(session: AvatarSession): AvatarSession {
  return {
    ...session,
    input_mode:
      session.input_mode ||
      (session.voice?.approved_take_id || session.voice?.approved_record_id ? "approved_voice" : "script"),
    presentation_style: session.presentation_style || "direct_presenter",
    framing_choice: session.framing_choice || "medium_presenter",
    background_choice: session.background_choice || "studio_gradient",
    duration_class: session.duration_class || "story_section",
    provider_mode: session.provider_mode || "best_match",
    provider_choice: session.provider_choice ?? null,
    voice: {
      ...session.voice,
      fallback_audio_asset_id: session.voice?.fallback_audio_asset_id ?? null,
      approved_record_id: session.voice?.approved_record_id ?? null,
      approved_take_id: session.voice?.approved_take_id ?? null,
    },
    links: {
      ...session.links,
      script_document_id: session.links?.script_document_id ?? null,
      script_scene_heading_id: session.links?.script_scene_heading_id ?? null,
      script_scene_id: session.links?.script_scene_id ?? null,
      script_source_label: session.links?.script_source_label ?? "",
      script_revision_version: session.links?.script_revision_version ?? null,
      voice_record_id: session.links?.voice_record_id ?? null,
      voice_take_id: session.links?.voice_take_id ?? null,
    },
  };
}

function planSectionDurationMs(plan?: AvatarPresentationPlan | null): number {
  if (!plan?.sectionTargetSeconds) return 0;
  return Math.max(2000, Math.round(plan.sectionTargetSeconds * 1000));
}

function runtimeStatus(component: SetupComponentStatus): {
  label: "Experimental" | "Not Installed" | "Needs Repair";
  tone: "warn" | "bad";
} {
  const healthState = String((component.environment?.healthState as string | undefined) || "");
  if (healthState === "experimental" || component.status === "ready") {
    return { label: "Experimental", tone: "warn" };
  }
  if (component.status === "error" || component.status === "update_available") {
    return { label: "Needs Repair", tone: "bad" };
  }
  return { label: "Not Installed", tone: "warn" };
}

function bestMatchProvider(
  session: AvatarSession,
  providers: SetupComponentStatus[],
): SetupComponentStatus | null {
  const byId = new Map(providers.map((item) => [item.id, item]));
  if (session.mode === "existing_video_lipsync") {
    return byId.get("musetalk-1-5-local") || null;
  }
  if (session.mode === "full_body") {
    return byId.get("longcat-video-avatar-1-5-local") || null;
  }
  if (session.presentation_style === "stylized_performance") {
    return byId.get("longcat-video-avatar-1-5-local") || null;
  }
  return byId.get("infinitetalk-local") || byId.get("longcat-video-avatar-1-5-local") || null;
}

function approvedVoiceOptions(records: VoicePerformanceRecord[], characterId?: string | null): ApprovedVoiceChoice[] {
  if (!characterId) return [];
  return records
    .filter((record) => String(record.characterId || "") === String(characterId))
    .map((record) => {
      const approvedTake = record.takes.find(
        (take) => take.id === record.approvedTakeId && take.audioAssetId,
      );
      if (!approvedTake?.audioAssetId) return null;
      return {
        recordId: record.id,
        takeId: approvedTake.id,
        audioAssetId: approvedTake.audioAssetId,
        voiceIdentityId: record.voiceIdentityId,
        providerId: record.providerId,
        title: record.dialogueText.trim().slice(0, 90) || approvedTake.label,
        subtitle: approvedTake.label,
        updatedAt: record.updatedAt,
      } satisfies ApprovedVoiceChoice;
    })
    .filter(Boolean) as ApprovedVoiceChoice[];
}

export function AvatarStudioWorkspace({
  project,
  onChange,
  onGo,
}: {
  project: Project;
  onChange?: () => Promise<void>;
  onGo: (tab: EditorTab) => void;
}) {
  const openCoDirector = useOpenCoDirector();
  const openSetup = (componentId?: string) => {
    window.location.assign(
      buildAiGuidedSetupPath({
        projectId: project.id,
        componentId,
        source: "avatar_studio",
      }),
    );
  };
  useBindCoDirectorWorkspace({
    projectId: project.id,
    projectName: project.name,
    primaryProjectType: "talking_avatar",
    workspaceTab: "avatar",
    onGoTab: (tab) => onGo(tab as EditorTab),
  });
  const [params] = useSearchParams();
  const [sessions, setSessions] = useState<AvatarSession[]>([]);
  const [session, setSession] = useState<AvatarSession | null>(null);
  const [characters, setCharacters] = useState<ProfileItem[]>([]);
  const [audioAssets, setAudioAssets] = useState<any[]>([]);
  const [videoAssets, setVideoAssets] = useState<any[]>([]);
  const [imageAssets, setImageAssets] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [issues, setIssues] = useState<{ level: string; text: string }[]>([]);
  const [avatarJobs, setAvatarJobs] = useState<AvatarProjectJob[]>([]);
  const [activeJob, setActiveJob] = useState<AvatarProjectJob | null>(null);
  const [needsCharacter, setNeedsCharacter] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [durationOpen, setDurationOpen] = useState(false);
  const [planOpen, setPlanOpen] = useState(false);
  const [backgroundPickerOpen, setBackgroundPickerOpen] = useState(false);
  const [characterStills, setCharacterStills] = useState<Record<string, string>>({});
  const [reviewTab, setReviewTab] = useState<ReviewTab>("sections");
  const [runtimeComponents, setRuntimeComponents] = useState<SetupComponentStatus[]>([]);
  const [voiceReadiness, setVoiceReadiness] = useState<VoiceReadiness | null>(null);
  const [voiceRecords, setVoiceRecords] = useState<VoicePerformanceRecord[]>([]);
  const [scriptDocuments, setScriptDocuments] = useState<ScriptDocumentChoice[]>([]);
  const [scriptScenes, setScriptScenes] = useState<ScriptSceneChoice[]>([]);

  const loadLists = async () => {
    const [chars, charProfiles, lib, list] = await Promise.all([
      api.listProfiles("character").catch(() => []),
      api.listCharacterProfiles(project.id).catch(() => ({ items: [] as any[] })),
      api.library(project.id).catch(() => null),
      api.listAvatarSessions(project.id).catch(() => []),
    ]);
    const fromProfiles = (chars || []) as ProfileItem[];
    const fromCharacterProfiles = ((charProfiles as any)?.items || []).map((c: any) => ({
      id: String(c.id),
      name: String(c.name || "Character"),
      kind: "character",
    }));
    const merged = new Map<string, ProfileItem>();
    for (const item of [...fromProfiles, ...fromCharacterProfiles]) {
      if (item?.id) merged.set(String(item.id), item);
    }
    const normalizedCharacters = [...merged.values()];
    const stillEntries = await Promise.all(
      normalizedCharacters.map(async (item) => {
        const identity = await resolveCharacterIdentity(item.id, item.name).catch(() => null);
        return [item.id, identity?.stillAssetId || item.stillAssetId || null] as const;
      }),
    );
    const nextStills: Record<string, string> = {};
    const charactersWithStills = normalizedCharacters.map((item) => {
      const stillAssetId = stillEntries.find((entry) => entry[0] === item.id)?.[1] || null;
      if (stillAssetId) nextStills[item.id] = stillAssetId;
      return { ...item, stillAssetId };
    });
    setCharacterStills((prev) => ({ ...prev, ...nextStills }));
    setCharacters(charactersWithStills);
    const assets = lib?.items || [];
    setAudioAssets(assets.filter((asset: any) => asset.kind === "audio"));
    setVideoAssets(assets.filter((asset: any) => asset.kind === "video"));
    setImageAssets(assets.filter((asset: any) => asset.kind === "image"));
    const normalized = (list || []).map((item: AvatarSession) => normalizeSession(item));
    setSessions(normalized);
    return { sessions: normalized, characters: charactersWithStills };
  };

  const loadJobs = async (sessionId: string, preferredJobId?: string | null) => {
    const jobs = await api.listAvatarJobs(project.id, sessionId).catch(() => [] as AvatarProjectJob[]);
    setAvatarJobs(jobs);
    const nextActive =
      jobs.find((item) => item.id === preferredJobId) ||
      jobs.find((item) => item.id === session?.active_job_id) ||
      jobs[0] ||
      null;
    setActiveJob(nextActive);
    return jobs;
  };

  const loadScriptSources = async (preferredDocumentId?: string | null) => {
    try {
      const docsPayload = await api.scriptwriter.documents(project.id).catch(() => ({ documents: [] as Record<string, unknown>[] }));
      const documents = (docsPayload.documents || []).map((item) => ({
        id: String(item.id || ""),
        title: String(item.title || item.name || "Untitled Script"),
        updatedAt: item.updatedAt ? String(item.updatedAt) : undefined,
      }));
      setScriptDocuments(documents.filter((item) => item.id));
      const selectedDocumentId =
        preferredDocumentId ||
        session?.links?.script_document_id ||
        documents[0]?.id ||
        null;
      if (!selectedDocumentId) {
        setScriptScenes([]);
        return;
      }
      const bundle = await api.scriptwriter.document(project.id, selectedDocumentId).catch(() => null);
      const scenes = (((bundle as any)?.navigator || []) as Record<string, unknown>[]).map((item) => ({
        sceneHeadingId: String(item.sceneHeadingId || ""),
        sceneHeading: String(item.sceneHeading || item.title || "Scene"),
        sceneNumber: item.sceneNumber ? String(item.sceneNumber) : undefined,
        productionStatus: item.productionStatus ? String(item.productionStatus) : undefined,
        sceneId: item.sceneId ? String(item.sceneId) : null,
      }));
      setScriptScenes(scenes.filter((item) => item.sceneHeadingId));
    } catch {
      setScriptDocuments([]);
      setScriptScenes([]);
    }
  };

  const refreshRuntimeStatus = async () => {
    try {
      const next = await api.setupStatus();
      const avatarComponents = (next.components || [])
        .filter((component) => PROVIDER_ORDER.includes(component.id as (typeof PROVIDER_ORDER)[number]))
        .sort(
          (a, b) =>
            PROVIDER_ORDER.indexOf(a.id as (typeof PROVIDER_ORDER)[number]) -
            PROVIDER_ORDER.indexOf(b.id as (typeof PROVIDER_ORDER)[number]),
        );
      setRuntimeComponents(avatarComponents);
    } catch {
      setRuntimeComponents([]);
    }
  };

  const resolveCharacterIdentity = async (characterId: string, fallbackName?: string) => {
    const [profile, refs] = await Promise.all([
      api.getCharacterProfile(project.id, characterId).catch(() => null),
      api.listCharacterReferences(project.id, characterId).catch(() => ({ items: [] as any[] })),
    ]);
    const name = String((profile as { name?: string } | null)?.name || fallbackName || "Character");
    const picked = pickApprovedCharacterStill({
      profile: (profile || null) as any,
      references: (((refs as { items?: any[] })?.items || []) as any[]),
      candidates: ((((profile as { candidates?: any[] } | null)?.candidates ||
        (profile as { generation?: { candidates?: any[] } } | null)?.generation?.candidates ||
        []) as any[])),
    });
    if (picked?.assetId) {
      setCharacterStills((prev) => ({ ...prev, [characterId]: picked.assetId }));
    }
    return {
      name,
      stillAssetId: picked?.assetId || null,
      stillRole: picked?.role || null,
    };
  };

  const bindCharacterSession = async (
    characterId: string,
    seededSessions?: AvatarSession[],
    seededCharacters?: ProfileItem[],
  ) => {
    const availableSessions = seededSessions || sessions;
    const availableCharacters = seededCharacters || characters;
    const listed = availableCharacters.find((item) => item.id === characterId);
    const identity = await resolveCharacterIdentity(characterId, listed?.name);
    const existing = availableSessions.find((item) => item.character_profile_id === characterId);
    if (existing) {
      setNeedsCharacter(false);
      let next = applyApprovedIdentityToSession(normalizeSession(existing), {
        characterId,
        characterName: identity.name || existing.character_name,
        stillAssetId: existing.source_still_asset_id || identity.stillAssetId,
        stillRole: identity.stillRole,
      });
      if (!existing.source_still_asset_id && identity.stillAssetId) {
        try {
          next = normalizeSession(await api.patchAvatarSession(project.id, next.id, next));
        } catch {
          /* keep local identity bind if persist fails */
        }
      }
      setSession(next);
      setSessions((prev) => prev.map((item) => (item.id === next.id ? next : item)));
      await loadJobs(existing.id, existing.active_job_id);
      return;
    }
    if (!listed && !identity.name) {
      setNeedsCharacter(true);
      setSession(null);
      return;
    }
    const boot = applyApprovedIdentityToSession(
      normalizeSession(emptyAvatarSession(project.id, `${identity.name} Presenter Session`)),
      {
        characterId,
        characterName: identity.name,
        stillAssetId: identity.stillAssetId,
        stillRole: identity.stillRole,
      },
    );
    const created = normalizeSession(
      await api.createAvatarSession(project.id, {
        name: boot.name,
        character_profile_id: boot.character_profile_id || undefined,
        character_name: boot.character_name,
        mode: boot.mode,
        bootstrap: boot,
      }),
    );
    setNeedsCharacter(false);
    setSession(created);
    setSessions((prev) => [created, ...prev]);
    setAvatarJobs([]);
    setActiveJob(null);
  };

  useEffect(() => {
    (async () => {
      await refreshRuntimeStatus();
      const loaded = await loadLists();
      let profileQ = params.get("profile") || params.get("characterId");
      if (!profileQ) {
        try {
          profileQ =
            sessionStorage.getItem("adept_avatar_profile") ||
            sessionStorage.getItem("adept_selected_character") ||
            "";
          if (sessionStorage.getItem("adept_avatar_profile")) {
            sessionStorage.removeItem("adept_avatar_profile");
          }
        } catch {
          /* ignore */
        }
      }
      if (!profileQ) {
        setNeedsCharacter(true);
        setSession(null);
        return;
      }
      await bindCharacterSession(profileQ, loaded.sessions, loaded.characters);
    })().catch((error) => {
      console.error(error);
      setMsg(error instanceof Error ? error.message : String(error));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id, params]);

  useEffect(() => {
    const characterId = session?.character_profile_id;
    if (!characterId) {
      setVoiceReadiness(null);
      setVoiceRecords([]);
      return;
    }
    (async () => {
      try {
        const [readiness, records] = await Promise.all([
          api.voicePerformanceReadiness(characterId, project.id).catch(() => null),
          api.voicePerformanceM410
            .listProjectRecords(project.id)
            .then((payload) => payload.records || [])
            .catch(() => [] as VoicePerformanceRecord[]),
        ]);
        setVoiceReadiness(readiness as VoiceReadiness | null);
        setVoiceRecords(records);
      } catch {
        setVoiceReadiness(null);
        setVoiceRecords([]);
      }
    })().catch(() => {
      setVoiceReadiness(null);
      setVoiceRecords([]);
    });
  }, [project.id, session?.character_profile_id]);

  useEffect(() => {
    void loadScriptSources(session?.links?.script_document_id).catch(() => {
      setScriptDocuments([]);
      setScriptScenes([]);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id, session?.id, session?.links?.script_document_id]);

  useEffect(() => {
    if (!session?.id) {
      setAvatarJobs([]);
      setActiveJob(null);
      return;
    }
    void loadJobs(session.id, session.active_job_id).catch(() => {
      setAvatarJobs([]);
      setActiveJob(null);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id, session?.id, session?.active_job_id]);

  const patchSession = (patch: Partial<AvatarSession>) => {
    if (!session) return;
    setSession({
      ...session,
      ...patch,
      updated_at: new Date().toISOString(),
    });
  };

  const patchSessionLinks = (patch: Record<string, unknown>) => {
    if (!session) return;
    patchSession({
      links: {
        ...session.links,
        ...patch,
      },
    });
  };

  const patchPresentationPlan = (patch: Partial<AvatarPresentationPlan>) => {
    if (!session) return;
    patchSession({
      presentation_plan: {
        ...(session.presentation_plan || {
          version: "m4.12",
          summary: "",
          sectioningStrategy: "",
          sectionTargetSeconds: 6,
          deliveryStyle: "",
          gazeStyle: "",
          gestureStyle: "",
          pacingStyle: "",
          chapterTransitionStyle: "",
          emphasisNotes: "",
          postureNotes: "",
          pronunciationNotes: "",
          backgroundRecommendation: "",
          framingRecommendation: "",
          continuityChecklist: "",
          retakeGuidance: "",
          sections: [],
        }),
        ...patch,
      },
    });
  };

  const patchPresentationSection = (sectionId: string, patch: Record<string, string>) => {
    if (!session?.presentation_plan) return;
    patchPresentationPlan({
      sections: session.presentation_plan.sections.map((item) =>
        item.id === sectionId ? { ...item, ...patch } : item,
      ),
    });
  };

  const persistSession = async (next: AvatarSession) => {
    const prompts = buildAvatarPrompt(next);
    const payload = {
      ...next,
      prompt: next.prompt || prompts.prompt,
      negative_prompt: next.negative_prompt || prompts.negative_prompt,
    };
    const saved = normalizeSession(await api.patchAvatarSession(project.id, next.id, payload));
    setSession(saved);
    setSessions((prev) => prev.map((item) => (item.id === saved.id ? saved : item)));
    await onChange?.();
    return saved;
  };

  const useScriptScene = async () => {
    const documentId = session?.links?.script_document_id;
    const sceneHeadingId = session?.links?.script_scene_heading_id;
    if (!session || !documentId || !sceneHeadingId) return;
    setBusy(true);
    try {
      const prepared = await api.scriptwriter.prepareTimeline(project.id, documentId, sceneHeadingId);
      const proposal = (prepared.proposal || {}) as Record<string, unknown>;
      const dialogue = Array.isArray(proposal.dialogue)
        ? proposal.dialogue
            .map((item) => String((item as Record<string, unknown>).text || "").trim())
            .filter(Boolean)
            .join("\n\n")
        : "";
      const selectedScene = scriptScenes.find((item) => item.sceneHeadingId === sceneHeadingId);
      patchSession({
        dialogue_original: dialogue || session.dialogue_original,
        links: {
          ...session.links,
          script_document_id: documentId,
          script_scene_heading_id: sceneHeadingId,
          script_scene_id: selectedScene?.sceneId || null,
          script_source_label: String(proposal.sceneHeading || selectedScene?.sceneHeading || ""),
        },
      });
      setMsg(
        dialogue
          ? "Scene dialogue linked from Scriptwriter."
          : "Scene linked for provenance. Add or refine the exact performance lines here if needed.",
      );
    } catch (error) {
      setMsg(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  const syncJobState = async (job: AvatarProjectJob, nextSession?: AvatarSession | null) => {
    setActiveJob(job);
    setAvatarJobs((prev) => {
      const next = prev.filter((item) => item.id !== job.id);
      return [job, ...next];
    });
    if (nextSession) {
      const normalizedSession = normalizeSession({ ...nextSession, active_job_id: job.id });
      setSession(normalizedSession);
      setSessions((prev) =>
        prev.map((item) => (item.id === normalizedSession.id ? normalizedSession : item)),
      );
    }
  };

  const saveDraft = async () => {
    if (!session) return;
    setBusy(true);
    try {
      await persistSession(session);
      setMsg("Presenter setup saved.");
    } catch (error) {
      setMsg(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  const askCoDirectorForPlan = () => {
    if (!session) return;
    openCoDirector(
      `Plan this Avatar Studio presentation for ${session.character_name || "this presenter"}. ` +
        "Use the avatar presentation tools to inspect the session, section the script, " +
        "and propose creator-facing notes for delivery, gaze, gesture, pacing, chapter transitions, " +
        "emphasis, posture, pronunciation, background, framing, continuity, and section retakes.",
      { fullscreen: true },
    );
  };

  const createPlanProposal = async () => {
    if (!session?.presentation_plan) return;
    setBusy(true);
    try {
      const plan = session.presentation_plan;
      const proposal = await api.proposeCoDirectorToolCall(project.id, {
        toolId: "avatar.create_plan",
        createdBy: "user",
        arguments: {
          sessionId: session.id,
          summary: plan.summary,
          sectioningStrategy: plan.sectioningStrategy,
          targetSectionDurationMs: planSectionDurationMs(plan),
          deliveryStyle: plan.deliveryStyle,
          gazeStyle: plan.gazeStyle,
          gestureStyle: plan.gestureStyle,
          pacingStyle: plan.pacingStyle,
          chapterTransitionStyle: plan.chapterTransitionStyle,
          emphasisNotes: plan.emphasisNotes,
          postureNotes: plan.postureNotes,
          pronunciationNotes: plan.pronunciationNotes,
          backgroundRecommendation: plan.backgroundRecommendation,
          framingRecommendation: plan.framingRecommendation,
          continuityChecklist: plan.continuityChecklist,
          retakeGuidance: plan.retakeGuidance,
        },
      });
      setMsg(`Presentation plan proposal ${proposal.id} is ready in Co-Director Approvals.`);
    } catch (error) {
      setMsg(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  const createNew = async () => {
    if (!session) return;
    setBusy(true);
    try {
      const boot = applyApprovedIdentityToSession(
        normalizeSession(emptyAvatarSession(project.id, `Presenter ${sessions.length + 1}`)),
        {
          characterId: session.character_profile_id || "",
          characterName: session.character_name,
          stillAssetId: session.source_still_asset_id || (session.character_profile_id ? characterStills[session.character_profile_id] : null),
          stillRole: session.links.master_sheet_id ? "sheet" : null,
        },
      );
      const created = normalizeSession(
        await api.createAvatarSession(project.id, {
          name: boot.name,
          character_profile_id: boot.character_profile_id || undefined,
          character_name: boot.character_name,
          mode: boot.mode,
          bootstrap: boot,
        }),
      );
      setSession(created);
      setSessions((prev) => [created, ...prev]);
      setAvatarJobs([]);
      setActiveJob(null);
      setMsg("New presenter session ready.");
    } catch (error) {
      setMsg(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  const runValidate = async () => {
    if (!session) return;
    setBusy(true);
    try {
      const saved = await persistSession(session);
      const response = await api.validateAvatarSession(project.id, saved.id);
      setIssues(response.issues || validateAvatarSession(saved));
      setMsg(response.ok ? "Presenter setup looks ready." : "A few setup items still need attention.");
    } catch (error) {
      setMsg(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  const generateVideo = async () => {
    if (!session) return;
    setBusy(true);
    setMsg("");
    try {
      const saved = await persistSession(session);
      const validation = await api.validateAvatarSession(project.id, saved.id);
      setIssues(validation.issues || validateAvatarSession(saved));
      if (!validation.ok) {
        setMsg("Complete the blocked items before generating.");
        return;
      }
      if (saved.mode === "existing_video_lipsync") {
        if (!museTalkProvider || runtimeStatus(museTalkProvider).label === "Not Installed") {
          setMsg("MuseTalk 1.5 is not installed yet, so Lip-Sync Repair cannot be prepared.");
          return;
        }
        const nextJob = await api.createAvatarJob(project.id, saved.id, {
          providerId: "musetalk-1-5-local",
          startImmediately: false,
        });
        const refreshedSession = normalizeSession(await api.getAvatarSession(project.id, saved.id));
        await syncJobState(nextJob, refreshedSession);
        setReviewTab("sections");
        setMsg(
          `Lip-Sync Repair plan ready with ${nextJob.sections.length} section${
            nextJob.sections.length === 1 ? "" : "s"
          }. Review the section plan before proposing repair actions.`,
        );
        return;
      }
      const nextJob = await api.createAvatarJob(project.id, saved.id, {
        providerId: selectedProvider?.id || saved.provider_choice || saved.model_id,
        startImmediately: true,
      });
      const refreshedSession = normalizeSession(await api.getAvatarSession(project.id, saved.id));
      await syncJobState(nextJob, refreshedSession);
      setReviewTab("sections");
      setMsg(
        nextJob.status === "failed"
          ? nextJob.lastError?.message || "Section generation stopped on an honest runtime error."
          : `Long-form plan ready with ${nextJob.sections.length} section${
              nextJob.sections.length === 1 ? "" : "s"
            }.`,
      );
    } catch (error) {
      setMsg(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  const runJobAction = async (
    action: () => Promise<AvatarProjectJob>,
    successMessage?: string,
    nextTab?: ReviewTab,
  ) => {
    if (!session || !activeJob) return;
    setBusy(true);
    try {
      const updated = await action();
      const refreshedSession = normalizeSession(await api.getAvatarSession(project.id, session.id));
      await syncJobState(updated, refreshedSession);
      if (nextTab) setReviewTab(nextTab);
      if (successMessage) setMsg(successMessage);
    } catch (error) {
      setMsg(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  const pauseActiveJob = async () => {
    if (!activeJob) return;
    await runJobAction(
      () => api.pauseAvatarJob(project.id, activeJob.id),
      "Section generation paused. Resume when you are ready.",
      "progress",
    );
  };

  const resumeActiveJob = async () => {
    if (!activeJob) return;
    await runJobAction(
      () => api.resumeAvatarJob(project.id, activeJob.id),
      "Section generation resumed.",
      "progress",
    );
  };

  const cancelActiveJob = async () => {
    if (!activeJob) return;
    await runJobAction(
      () => api.cancelAvatarJob(project.id, activeJob.id),
      "This long-form pass was cancelled. You can retry only the sections you need later.",
      "progress",
    );
  };

  const retrySection = async (sectionId: string) => {
    if (!activeJob) return;
    await runJobAction(
      () => api.retryAvatarSection(project.id, activeJob.id, sectionId),
      "Retry requested for the failed section only.",
      "sections",
    );
  };

  const proposeRetake = async (sectionId: string, action: RetakeActionChoice) => {
    if (!activeJob) return;
    setBusy(true);
    try {
      const proposal = await api.proposeCoDirectorToolCall(project.id, {
        toolId: action.toolId || "avatar.request_retake",
        createdBy: "user",
        arguments: {
          jobId: activeJob.id,
          sectionId,
          actionType: action.id,
          reason: action.label,
          note: action.note,
        },
      });
      setMsg(`Retake proposal ${proposal.id} is ready in Co-Director Approvals.`);
      setReviewTab("sections");
    } catch (error) {
      setMsg(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  const proposeReplaceVoice = async () => {
    if (!session) return;
    if (!selectedApprovedVoice) {
      setMsg("Choose an approved Voice Studio take before replacing the voice performance.");
      return;
    }
    setBusy(true);
    try {
      const proposal = await api.proposeCoDirectorToolCall(project.id, {
        toolId: "avatar.replace_voice",
        createdBy: "user",
        arguments: {
          sessionId: session.id,
          audioAssetId: selectedApprovedVoice.audioAssetId,
          approvedRecordId: selectedApprovedVoice.recordId,
          approvedTakeId: selectedApprovedVoice.takeId,
          profileId: selectedApprovedVoice.voiceIdentityId,
          providerId: "voice-performance-m410",
          modelId: selectedApprovedVoice.providerId,
          pronunciationNotes: activeSession.voice.pronunciation_notes || "",
        },
      });
      setMsg(`Voice replacement proposal ${proposal.id} is ready in Co-Director Approvals.`);
    } catch (error) {
      setMsg(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  const proposeTimelineHandoff = async (
    placementMode: "full_presentation" | "selected_section" | "replace_section" | "create_alternate_take",
    sectionId?: string,
  ) => {
    if (!activeJob) return;
    setBusy(true);
    try {
      const proposal = await api.proposeCoDirectorToolCall(project.id, {
        toolId: "avatar.prepare_timeline",
        createdBy: "user",
        arguments: {
          jobId: activeJob.id,
          placementMode,
          sectionId: placementMode === "selected_section" ? sectionId : undefined,
          replaceSectionId: placementMode === "replace_section" ? sectionId : undefined,
          trackId: placementMode === "create_alternate_take" ? "avatar-alternates" : "avatar-presenter",
        },
      });
      setMsg(`Timeline handoff proposal ${proposal.id} is ready in Co-Director Approvals. It does not write the Timeline.`);
      setReviewTab("completed");
    } catch (error) {
      setMsg(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  const approveSection = async (sectionId: string) => {
    if (!activeJob) return;
    await runJobAction(
      () => api.approveAvatarSection(project.id, activeJob.id, sectionId),
      "Section approved for assembly.",
      "sections",
    );
  };

  const validateTransitions = async () => {
    if (!activeJob) return;
    await runJobAction(
      () => api.validateAvatarTransitions(project.id, activeJob.id, { validated: true }),
      "Transition validation hook recorded.",
      "progress",
    );
  };

  const assembleActiveJob = async () => {
    if (!activeJob) return;
    await runJobAction(
      () => api.assembleAvatarJob(project.id, activeJob.id),
      "Assembly contract completed. Final composite rendering remains a stub in this pass.",
      "completed",
    );
  };

  const sendTakeToDirector = async (takeId: string) => {
    if (!session) return;
    const take = session.takes.find((item) => item.id === takeId);
    if (!take?.asset_id) {
      setMsg("This take does not have a video asset yet.");
      return;
    }
    setBusy(true);
    try {
      await api.promote(project.id, {
        asset_id: take.asset_id,
        target: "scene_new",
        name: `${session.character_name || "Avatar"} — ${take.label}`,
      });
      await api.addAvatarTake(project.id, session.id, {
        asset_id: take.asset_id || undefined,
        scene_id: take.scene_id || undefined,
        approved: true,
        status: "final",
        label: take.label,
        performance_note: take.performance_note,
        favorite: take.favorite,
      });
      const refreshed = normalizeSession(await api.getAvatarSession(project.id, session.id));
      setSession(refreshed);
      setSessions((prev) => prev.map((item) => (item.id === refreshed.id ? refreshed : item)));
      setMsg("Video sent to Timeline as a new scene.");
      setReviewTab("completed");
    } catch (error) {
      setMsg(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  const approvedVoices = useMemo(
    () => approvedVoiceOptions(voiceRecords, session?.character_profile_id),
    [voiceRecords, session?.character_profile_id],
  );

  if (needsCharacter) {
    return (
      <div className="page" data-testid="avatar-requires-character">
        <header className="hero" style={{ paddingTop: "1rem" }}>
          <h1>Avatar Studio</h1>
          <p>Choose a character to open a long-form presenter workspace.</p>
        </header>
        <div className="row-actions" style={{ gap: "0.75rem", flexWrap: "wrap" }}>
          <button type="button" data-testid="avatar-choose-character" onClick={() => onGo("characters")}>
            Choose Avatar
          </button>
          <button type="button" data-testid="avatar-open-character-profiles" onClick={() => onGo("characters")}>
            Open Character Creator
          </button>
        </div>
        {characters.length ? (
          <label style={{ display: "block", marginTop: "1.25rem", maxWidth: "24rem" }}>
            Or pick from this project
            <select
              data-testid="avatar-character-select"
              defaultValue=""
              onChange={(event) => {
                const nextId = event.target.value;
                if (!nextId) return;
                try {
                  sessionStorage.setItem("adept_selected_character", nextId);
                  sessionStorage.setItem("adept_avatar_profile", nextId);
                } catch {
                  /* ignore */
                }
                void bindCharacterSession(nextId).catch(console.error);
              }}
            >
              <option value="">Select character…</option>
              {characters.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
        ) : null}
      </div>
    );
  }

  if (!session) {
    return (
      <div className="page">
        <p className="empty">Loading Avatar Studio…</p>
      </div>
    );
  }

  const activeSession = normalizeSession(session);
  const presentationPlan = activeSession.presentation_plan;
  const previewAssetId =
    activeSession.source_still_asset_id ||
    activeSession.takes.find((item) => item.asset_id)?.asset_id ||
    null;
  const previewSrc = previewAssetId ? api.assetUrl(previewAssetId) : null;
  const scriptText = activeSession.dialogue_spoken || activeSession.dialogue_original || "";
  const estimatedSeconds = estimateDialogueSeconds(scriptText);
  const bestProvider = bestMatchProvider(activeSession, runtimeComponents);
  const selectedProvider =
    activeSession.provider_mode === "choose_provider"
      ? runtimeComponents.find((item) => item.id === activeSession.provider_choice) || bestProvider
      : bestProvider;
  const selectedApprovedVoice = approvedVoices.find(
    (item) => item.audioAssetId === activeSession.voice.audio_asset_id,
  );
  const resolvedAudioAssetId =
    activeSession.input_mode === "approved_voice"
      ? activeSession.voice.audio_asset_id
      : activeSession.voice.fallback_audio_asset_id || activeSession.voice.audio_asset_id;
  const museTalkProvider = runtimeComponents.find((item) => item.id === "musetalk-1-5-local") || null;
  const selectedRuntimeStatus = selectedProvider
    ? runtimeStatus(selectedProvider)
    : { label: "Choose Runtime" as const, tone: "warn" as const };
  const selectedRuntimeGate: AvatarRuntimeGate = selectedProvider
    ? { id: selectedProvider.id, name: selectedProvider.name, label: selectedRuntimeStatus.label }
    : { label: "Choose Runtime" };
  const generateBlockers = avatarGenerateBlockers(activeSession, selectedRuntimeGate);
  const canGenerate = canGenerateAvatarSession(activeSession, selectedRuntimeGate);
  const generateBlockReason = generateBlockers[0]?.text || "";
  const completedTakes = activeSession.takes.filter(
    (item) => item.approved || item.status === "final" || !!item.scene_id,
  );
  const activeSections = activeJob?.sections || [];
  const completedSections = activeSections.filter(
    (item) => item.status === "completed" || item.status === "approved",
  );
  const failedSections = activeSections.filter((item) => item.status === "failed");
  const approvedSections = activeSections.filter((item) => item.status === "approved");
  const canPauseJob = activeJob?.status === "queued" || activeJob?.status === "generating";
  const canResumeJob =
    activeJob?.status === "paused" || activeJob?.status === "failed" || activeJob?.status === "queued";
  const canAssembleJob =
    !!activeJob &&
    activeSections.length > 0 &&
    failedSections.length === 0 &&
    completedSections.length === activeSections.length;

  return (
    <div className="page avatar-studio avatar-studio-v2" data-testid="avatar-studio-workspace">
      <header className="avatar-studio-head avatar-studio-head--presenter">
        <div>
          <p className="eyebrow">Avatar Studio</p>
          <h1>
            {activeSession.character_name || "Presenter"}
            <span className="muted avatar-session-name"> · {activeSession.name}</span>
          </h1>
          <p className="muted">
            Select Avatar → Script or Approved Voice → Presentation Style → Framing → Background →
            Generate → Review → Timeline
          </p>
        </div>
        <div className="row avatar-head-actions" style={{ flexWrap: "wrap", gap: "0.5rem" }}>
          <select
            aria-label="Open session"
            title="Open a saved Avatar Studio session"
            value={activeSession.id}
            onChange={async (event) => {
              const next = normalizeSession(
                await api.getAvatarSession(project.id, event.target.value),
              );
              setSession(next);
              await loadJobs(next.id, next.active_job_id);
            }}
          >
            {sessions.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
          <button type="button" onClick={createNew} disabled={busy}>
            New Session
          </button>
          <button
            type="button"
            onClick={() => openSetup()}
            title="Open AI Guided Setup for avatar runtimes"
            aria-label="Open AI Guided Setup for avatar runtimes"
          >
            Open Runtime Setup
          </button>
          <button type="button" className="primary" onClick={saveDraft} disabled={busy}>
            Save Draft
          </button>
        </div>
      </header>

      <div className="avatar-hero-layout">
        <section className="dash-card avatar-preview-pane avatar-preview-pane--large">
          <div className="avatar-preview-pane__header">
            <div>
              <p className="eyebrow">Avatar Preview</p>
              <h2>{MODE_CARDS.find((item) => item.id === activeSession.mode)?.label || "Presenter"}</h2>
            </div>
            <div className="avatar-preview-pane__chips">
              <span className="pill">{FRAMING_CARDS.find((item) => item.id === activeSession.framing_choice)?.label || activeSession.camera.shot_size}</span>
              <span className="pill">{STYLE_CARDS.find((item) => item.id === activeSession.presentation_style)?.label || "Style"}</span>
              <span className="pill">{selectedProvider ? runtimeStatus(selectedProvider).label : "Choose Runtime"}</span>
            </div>
          </div>
          <div className="cinematic-media motif-imagegen avatar-preview-media avatar-preview-media--workspace">
            <div className="cinematic-media-fallback" aria-hidden="true" />
            {previewSrc ? (
              <img
                src={previewSrc}
                alt={`${activeSession.character_name || "Avatar"} preview`}
                onError={(event) => {
                  (event.currentTarget as HTMLImageElement).style.display = "none";
                }}
              />
            ) : (
              <div className="avatar-preview-empty">
                <strong>{activeSession.character_name || "Presenter"}</strong>
                <span>
                  {activeSession.character_profile_id
                    ? "No approved Character Creator still is bound yet. Open Character Creator to approve a hero, sheet, or portrait."
                    : "Choose a character so Avatar Studio can bind the approved still."}
                </span>
                <div className="avatar-inline-actions" style={{ justifyContent: "center" }}>
                  <button type="button" onClick={() => onGo("characters")}>
                    Open Character Creator
                  </button>
                </div>
              </div>
            )}
            <div className="cinematic-media-overlay" />
            <span className="hero-media-caption">
              {activeSession.background_notes || "Ready for a presenter background"} · ~
              {Math.max(estimatedSeconds, 0)}s script estimate
            </span>
          </div>
          <div className="avatar-preview-pane__footer">
            {msg ? <p className="pill avatar-preview-message">{msg}</p> : null}
            {activeJob ? (
              <p className="scene-meta">
                Active job: {activeJob.id} · {sectionStatusLabel(activeJob.status)}
              </p>
            ) : null}
            {avatarJobs.length ? (
              <p className="scene-meta">
                {avatarJobs.length} long-form job{avatarJobs.length === 1 ? "" : "s"} in this presenter history
              </p>
            ) : null}
            <div className="avatar-preview-summary">
              <div>
                <span className="avatar-summary-label">Voice</span>
                <strong>
                  {activeSession.input_mode === "approved_voice"
                    ? selectedApprovedVoice
                      ? "Approved voice attached"
                      : "Approved voice needed"
                    : scriptText.trim()
                      ? "Script ready"
                      : "Script needed"}
                </strong>
              </div>
              <div>
                <span className="avatar-summary-label">Timeline</span>
                <strong>
                  {activeJob
                    ? `${completedSections.length}/${activeSections.length || 0} sections planned`
                    : completedTakes.length
                      ? `${completedTakes.length} ready`
                      : "No completed videos yet"}
                </strong>
              </div>
            </div>
          </div>
        </section>

        <aside className="dash-card avatar-create-panel" data-testid="avatar-create-panel">
          <div className="avatar-create-panel__heading">
            <div>
              <p className="eyebrow">Create</p>
              <h2>Long-Form Presenter</h2>
            </div>
            <div className="avatar-provider-glance">
              <span className="scene-meta">Provider Mode</span>
              <strong>
                {activeSession.provider_mode === "best_match"
                  ? "Best Match"
                  : activeSession.provider_mode === "choose_provider"
                    ? "Choose Provider"
                    : "Compare"}
              </strong>
            </div>
          </div>

          <section className="avatar-create-section">
            <div className="avatar-section-title-row">
              <h3>Select Avatar</h3>
              <Tip text="Pick the presenter you want to perform this section. Each character keeps their own avatar session history." />
            </div>
            <div className="avatar-card-grid avatar-card-grid--avatars">
              {characters.map((item) => {
                const selected = activeSession.character_profile_id === item.id;
                const stillId = item.stillAssetId || characterStills[item.id] || null;
                return (
                  <button
                    key={item.id}
                    type="button"
                    className={`avatar-choice-card${selected ? " is-selected" : ""}`}
                    aria-pressed={selected}
                    aria-label={selected ? `${item.name}, current presenter` : `Select ${item.name}`}
                    onClick={() => {
                      try {
                        sessionStorage.setItem("adept_selected_character", item.id);
                        sessionStorage.setItem("adept_avatar_profile", item.id);
                      } catch {
                        /* ignore */
                      }
                      void bindCharacterSession(item.id).catch(console.error);
                    }}
                  >
                    <span className="avatar-choice-card__art" aria-hidden="true">
                      {stillId ? (
                        <img src={api.assetUrl(stillId)} alt="" />
                      ) : (
                        item.name.slice(0, 1).toUpperCase()
                      )}
                    </span>
                    <span className="avatar-choice-card__copy">
                      <strong>{item.name}</strong>
                      <span>{selected ? "Current presenter" : stillId ? "Approved still ready" : "Open this presenter"}</span>
                    </span>
                  </button>
                );
              })}
            </div>
          </section>

          <section className="avatar-create-section">
            <div className="avatar-section-title-row">
              <h3>Mode</h3>
              <Tip text="Choose the kind of presenter performance you want to build. More stylized looks stay tucked inside Advanced." />
            </div>
            <p className="scene-meta">Card choices stay local until Save Draft or Generate.</p>
            <div className="avatar-card-grid" data-testid="avatar-mode-cards">
              {MODE_CARDS.map((item) => {
                const selected = activeSession.mode === item.id;
                const dubbingUnavailable =
                  item.id === "existing_video_lipsync" &&
                  (!museTalkProvider || runtimeStatus(museTalkProvider).label === "Not Installed");
                return (
                  <button
                    key={item.id}
                    type="button"
                    className={`avatar-choice-card${selected ? " is-selected" : ""}${dubbingUnavailable ? " is-unavailable" : ""}`}
                    aria-pressed={selected}
                    aria-disabled={dubbingUnavailable}
                    title={
                      dubbingUnavailable
                        ? "MuseTalk 1.5 is not installed, so Existing Video Dubbing cannot be prepared."
                        : item.blurb
                    }
                    onClick={() =>
                      patchSession({
                        mode: item.id,
                        camera: {
                          ...activeSession.camera,
                          shot_size: item.shotSize,
                        },
                      })
                    }
                  >
                    <span className="avatar-choice-card__copy">
                      <strong>{item.label}</strong>
                      <span>
                        {dubbingUnavailable
                          ? "MuseTalk 1.5 is not installed, so this plan-only dubbing path is unavailable."
                          : item.blurb}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
          </section>

          <section className="avatar-create-section">
            <div className="avatar-section-title-row">
              <h3>Script or Approved Voice</h3>
              <Tip text="Use Script when you are still writing the section. Use Approved Voice when Voice Studio already has the take you trust." />
            </div>
            <div className="avatar-toggle-row">
              <button
                type="button"
                className={activeSession.input_mode === "script" ? "primary" : ""}
                onClick={() => patchSession({ input_mode: "script" })}
              >
                Script
              </button>
              <button
                type="button"
                className={activeSession.input_mode === "approved_voice" ? "primary" : ""}
                onClick={() => patchSession({ input_mode: "approved_voice" })}
              >
                Approved Voice
              </button>
            </div>
            {activeSession.input_mode === "script" ? (
              <>
                <div className="gen-grid">
                  <div className="field">
                    <label>Script Document</label>
                    <select
                      value={activeSession.links.script_document_id || ""}
                      onChange={(event) => {
                        const nextId = event.target.value || null;
                        patchSessionLinks({
                          script_document_id: nextId,
                          script_scene_heading_id: null,
                          script_scene_id: null,
                          script_source_label: "",
                        });
                        void loadScriptSources(nextId).catch(() => {
                          setScriptScenes([]);
                        });
                      }}
                    >
                      <option value="">Select document…</option>
                      {scriptDocuments.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.title}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label>Scene Source</label>
                    <select
                      value={activeSession.links.script_scene_heading_id || ""}
                      onChange={(event) => {
                        const sceneHeadingId = event.target.value || null;
                        const selectedScene = scriptScenes.find((item) => item.sceneHeadingId === sceneHeadingId);
                        patchSessionLinks({
                          script_scene_heading_id: sceneHeadingId,
                          script_scene_id: selectedScene?.sceneId || null,
                          script_source_label: selectedScene?.sceneHeading || "",
                        });
                      }}
                    >
                      <option value="">Select scene…</option>
                      {scriptScenes.map((item) => (
                        <option key={item.sceneHeadingId} value={item.sceneHeadingId}>
                          {item.sceneNumber ? `${item.sceneNumber} · ` : ""}
                          {item.sceneHeading}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                <div className="avatar-inline-actions" style={{ marginBottom: "0.65rem" }}>
                  <button
                    type="button"
                    onClick={() => void useScriptScene()}
                    disabled={busy || !activeSession.links.script_document_id || !activeSession.links.script_scene_heading_id}
                  >
                    Use Scene Dialogue
                  </button>
                  <button type="button" onClick={() => onGo("scriptwriter")}>
                    Open Scriptwriter
                  </button>
                  <span className="scene-meta">
                    {activeSession.links.script_source_label
                      ? `Linked: ${activeSession.links.script_source_label}`
                      : "Link a Scriptwriter scene to keep provenance with this presenter pass."}
                  </span>
                </div>
                <div className="field">
                  <label>Presenter Script</label>
                  <textarea
                    data-testid="avatar-script-input"
                    rows={5}
                    value={activeSession.dialogue_original}
                    onChange={(event) => patchSession({ dialogue_original: event.target.value })}
                    placeholder="Write the section exactly as the presenter should deliver it."
                  />
                  <div className="avatar-inline-actions">
                    <span className="scene-meta">~{estimatedSeconds || 0}s speaking estimate</span>
                    <span className="scene-meta">
                      Need the voice performance first? Open Voice Studio and approve a take there.
                    </span>
                  </div>
                </div>
              </>
            ) : approvedVoices.length ? (
              <div className="avatar-approved-voice-list">
                {approvedVoices.map((item) => {
                  const selected = activeSession.voice.approved_take_id === item.takeId;
                  return (
                    <button
                      key={item.takeId}
                      type="button"
                      className={`avatar-approved-voice-card${selected ? " is-selected" : ""}`}
                      onClick={() =>
                        patchSession({
                          input_mode: "approved_voice",
                          voice: {
                            ...activeSession.voice,
                            provider: "voice-performance-m410",
                            audio_asset_id: item.audioAssetId,
                            approved_record_id: item.recordId,
                            approved_take_id: item.takeId,
                            profile_id: item.voiceIdentityId,
                            model: item.providerId,
                          },
                          links: {
                            ...activeSession.links,
                            voice_record_id: item.recordId,
                            voice_take_id: item.takeId,
                          },
                        })
                      }
                    >
                      <strong>{item.title}</strong>
                      <span>{item.subtitle}</span>
                      <span className="scene-meta">Updated {displayTime(item.updatedAt)}</span>
                    </button>
                  );
                })}
                <div className="avatar-inline-actions">
                  <span className="scene-meta">
                    {voiceReadiness?.pronunciationCount || 0} pronunciations · {voiceReadiness?.reactionReadyCount || 0} reactions ready
                  </span>
                  <span className="scene-meta">Approved takes stay source-of-truth in Voice Studio.</span>
                  <button type="button" onClick={() => onGo("voicestudio")}>
                    Open Voice Studio
                  </button>
                </div>
              </div>
            ) : (
              <div className="avatar-blocked-card">
                <strong>No approved voice take yet</strong>
                <p>
                  Build and approve a performance in Voice Studio, then come back here to attach it
                  to the presenter section.
                </p>
                <div className="avatar-inline-actions">
                  <button type="button" className="primary" onClick={() => onGo("voicestudio")}>
                    Open Voice Studio
                  </button>
                  <span className="scene-meta">
                    {voiceReadiness?.approvedVoice
                      ? "Voice identity approved, but no take is attached yet."
                      : "Voice identity approval still needed."}
                  </span>
                </div>
              </div>
            )}
            {activeSession.mode === "existing_video_lipsync" ? (
              <>
                <div className="field" style={{ marginTop: "0.85rem" }}>
                  <label>Existing Video</label>
                  <select
                    value={activeSession.source_video_asset_id || ""}
                    onChange={(event) =>
                      patchSession({ source_video_asset_id: event.target.value || null })
                    }
                  >
                    <option value="">Select video…</option>
                    {videoAssets.map((asset) => (
                      <option key={asset.id} value={asset.id}>
                        {asset.tag || asset.filename}
                      </option>
                    ))}
                  </select>
                </div>
                <p className="scene-meta" style={{ marginTop: "0.5rem" }}>
                  {!museTalkProvider || runtimeStatus(museTalkProvider).label === "Not Installed"
                    ? "MuseTalk 1.5 is not installed, so Existing Video Dubbing cannot be prepared. Open Runtime Setup to install it."
                    : "MuseTalk 1.5 is a plan-only Lip-Sync Repair and dubbing path here, not a live certified generator."}
                </p>
              </>
            ) : null}
          </section>

          <section className="avatar-create-section">
            <div className="avatar-section-title-row">
              <h3>Presentation Style</h3>
              <Tip text="This shapes how the presenter feels on camera. It affects the mood and visual style notes saved with the section." />
            </div>
            <div className="avatar-card-grid">
              {STYLE_CARDS.map((item) => {
                const selected = activeSession.presentation_style === item.id;
                return (
                  <button
                    key={item.id}
                    type="button"
                    aria-pressed={selected}
                    className={`avatar-choice-card${selected ? " is-selected" : ""}`}
                    onClick={() =>
                      patchSession({
                        presentation_style: item.id,
                        performance: { ...activeSession.performance, tone: item.tone as any },
                        camera: { ...activeSession.camera, angle: item.angle },
                        look: { ...activeSession.look, style: item.style },
                      })
                    }
                  >
                    <span className="avatar-choice-card__copy">
                      <strong>{item.label}</strong>
                      <span>{item.blurb}</span>
                    </span>
                  </button>
                );
              })}
            </div>
          </section>

          <section className="avatar-create-section">
            <div className="avatar-section-title-row">
              <h3>Framing</h3>
              <Tip text="Use framing to decide how close the camera feels to the performer. It is separate from Mode so you can keep the same workflow while changing the shot." />
            </div>
            <div className="avatar-card-grid">
              {FRAMING_CARDS.map((item) => {
                const selected = activeSession.framing_choice === item.id;
                return (
                  <button
                    key={item.id}
                    type="button"
                    aria-pressed={selected}
                    className={`avatar-choice-card${selected ? " is-selected" : ""}`}
                    onClick={() =>
                      patchSession({
                        framing_choice: item.id,
                        camera: {
                          ...activeSession.camera,
                          shot_size: item.shotSize,
                          lens: item.lens,
                        },
                        look: {
                          ...activeSession.look,
                          framing: item.shotSize,
                          lens: item.lens,
                        },
                      })
                    }
                  >
                    <span className="avatar-choice-card__copy">
                      <strong>{item.label}</strong>
                      <span>{item.blurb}</span>
                    </span>
                  </button>
                );
              })}
            </div>
          </section>

          <section className="avatar-create-section">
            <div className="avatar-section-title-row">
              <h3>Background</h3>
              <Tip text="Pick the environment the presenter should feel grounded in. Keep it simple in the main flow and move detailed notes into Advanced when needed." />
            </div>
            <div className="avatar-card-grid">
              {BACKGROUND_CARDS.map((item) => {
                const selected = activeSession.background_choice === item.id && !activeSession.background_asset_id;
                return (
                  <button
                    key={item.id}
                    type="button"
                    aria-pressed={selected}
                    className={`avatar-choice-card${selected ? " is-selected" : ""}`}
                    onClick={() =>
                      patchSession({
                        background_choice: item.id,
                        background_asset_id: null,
                        background_mode: item.backgroundMode,
                        background_notes: item.notes,
                        look: {
                          ...activeSession.look,
                          background: item.label,
                          environment_profile_id: null,
                        },
                      })
                    }
                  >
                    <span className="avatar-choice-card__copy">
                      <strong>{item.label}</strong>
                      <span>{item.blurb}</span>
                    </span>
                  </button>
                );
              })}
            </div>
            <div className="avatar-inline-actions">
              <button
                type="button"
                className={activeSession.background_asset_id ? "primary" : ""}
                aria-pressed={!!activeSession.background_asset_id}
                onClick={() => setBackgroundPickerOpen(true)}
              >
                {activeSession.background_asset_id ? "Change Library plate" : "Use Library plate"}
              </button>
              {activeSession.background_asset_id ? (
                <span className="scene-meta">Library plate {activeSession.background_asset_id} is saved on this session.</span>
              ) : (
                <span className="scene-meta">Optional Library plate reuses the Character Creator picker. Unsupported generators are not listed.</span>
              )}
            </div>
            <CharacterReferenceAssetPicker
              projectId={project.id}
              currentAssetId={activeSession.background_asset_id}
              open={backgroundPickerOpen}
              onCancel={() => setBackgroundPickerOpen(false)}
              onConfirm={(asset) => {
                patchSession({
                  background_choice: "library_plate",
                  background_asset_id: asset.id,
                  background_mode: "environment",
                  background_notes: `Library plate ${asset.tag || asset.filename || asset.id}`,
                  look: {
                    ...activeSession.look,
                    background: "Library plate",
                    environment_profile_id: asset.id,
                  },
                });
                setBackgroundPickerOpen(false);
              }}
            />
          </section>

          <details
            className="avatar-advanced-panel"
            open={durationOpen}
            onToggle={(event) => setDurationOpen((event.currentTarget as HTMLDetailsElement).open)}
          >
            <summary>
              Duration
              <Tip text="This is a section-size planning choice for long-form work. It helps you decide how much to pack into the current presenter pass." />
            </summary>
            <div className="avatar-advanced-panel__body">
            <div className="avatar-card-grid">
              {DURATION_CARDS.map((item) => {
                const selected = activeSession.duration_class === item.id;
                return (
                  <button
                    key={item.id}
                    type="button"
                    aria-pressed={selected}
                    className={`avatar-choice-card${selected ? " is-selected" : ""}`}
                    onClick={() => patchSession({ duration_class: item.id })}
                  >
                    <span className="avatar-choice-card__copy">
                      <strong>{item.label}</strong>
                      <span>{item.blurb}</span>
                    </span>
                  </button>
                );
              })}
            </div>
            </div>
          </details>

          {presentationPlan ? (
            <details
              className="avatar-advanced-panel"
              data-testid="avatar-presentation-plan"
              open={planOpen}
              onToggle={(event) => setPlanOpen((event.currentTarget as HTMLDetailsElement).open)}
            >
              <summary>
                Presentation Plan
                <Tip text="This is your creator-facing direction plan for sectioning, delivery, gaze, gesture, pacing, transitions, pronunciation, and continuity. Save the draft anytime, or ask Co-Director to turn it into an approval-ready plan." />
              </summary>
              <div className="avatar-advanced-panel__body">
              <div className="field">
                <label>Plan Summary</label>
                <textarea
                  rows={3}
                  value={presentationPlan.summary}
                  onChange={(event) => patchPresentationPlan({ summary: event.target.value })}
                  placeholder="Describe how this presenter section should feel overall."
                />
              </div>
              <div className="gen-grid">
                <div className="field">
                  <label>Sectioning Strategy</label>
                  <textarea
                    rows={3}
                    value={presentationPlan.sectioningStrategy}
                    onChange={(event) => patchPresentationPlan({ sectioningStrategy: event.target.value })}
                    placeholder="How should this long-form pass break into reviewable sections?"
                  />
                </div>
                <div className="field">
                  <label>Section Length (seconds)</label>
                  <input
                    type="number"
                    min={2}
                    max={30}
                    step={0.5}
                    value={presentationPlan.sectionTargetSeconds}
                    onChange={(event) =>
                      patchPresentationPlan({
                        sectionTargetSeconds: Math.max(2, Number(event.target.value || 6)),
                      })
                    }
                  />
                </div>
              </div>
              <div className="avatar-inline-actions" style={{ flexWrap: "wrap" }}>
                <button type="button" onClick={askCoDirectorForPlan} disabled={busy}>
                  Ask Co-Director to Plan
                </button>
                <button type="button" className="primary" onClick={() => void createPlanProposal()} disabled={busy}>
                  Create Plan Proposal
                </button>
                <span className="scene-meta">
                  Proposal approval writes the plan back to this session. Save Draft keeps your edits locally in Avatar Studio now.
                </span>
              </div>
              <details className="avatar-advanced-panel" open>
                <summary>Direction Notes</summary>
                <div className="avatar-advanced-panel__body">
                  <div className="gen-grid">
                    <div className="field">
                      <label>Delivery</label>
                      <textarea
                        rows={2}
                        value={presentationPlan.deliveryStyle}
                        onChange={(event) => patchPresentationPlan({ deliveryStyle: event.target.value })}
                      />
                    </div>
                    <div className="field">
                      <label>Gaze</label>
                      <textarea
                        rows={2}
                        value={presentationPlan.gazeStyle}
                        onChange={(event) => patchPresentationPlan({ gazeStyle: event.target.value })}
                      />
                    </div>
                    <div className="field">
                      <label>Gesture</label>
                      <textarea
                        rows={2}
                        value={presentationPlan.gestureStyle}
                        onChange={(event) => patchPresentationPlan({ gestureStyle: event.target.value })}
                      />
                    </div>
                    <div className="field">
                      <label>Pacing</label>
                      <textarea
                        rows={2}
                        value={presentationPlan.pacingStyle}
                        onChange={(event) => patchPresentationPlan({ pacingStyle: event.target.value })}
                      />
                    </div>
                    <div className="field">
                      <label>Chapter Transitions</label>
                      <textarea
                        rows={2}
                        value={presentationPlan.chapterTransitionStyle}
                        onChange={(event) => patchPresentationPlan({ chapterTransitionStyle: event.target.value })}
                      />
                    </div>
                    <div className="field">
                      <label>Posture</label>
                      <textarea
                        rows={2}
                        value={presentationPlan.postureNotes}
                        onChange={(event) => patchPresentationPlan({ postureNotes: event.target.value })}
                      />
                    </div>
                    <div className="field">
                      <label>Emphasis</label>
                      <textarea
                        rows={2}
                        value={presentationPlan.emphasisNotes}
                        onChange={(event) => patchPresentationPlan({ emphasisNotes: event.target.value })}
                      />
                    </div>
                    <div className="field">
                      <label>Pronunciation</label>
                      <textarea
                        rows={2}
                        value={presentationPlan.pronunciationNotes}
                        onChange={(event) => patchPresentationPlan({ pronunciationNotes: event.target.value })}
                      />
                    </div>
                    <div className="field">
                      <label>Background Recommendation</label>
                      <textarea
                        rows={2}
                        value={presentationPlan.backgroundRecommendation}
                        onChange={(event) => patchPresentationPlan({ backgroundRecommendation: event.target.value })}
                      />
                    </div>
                    <div className="field">
                      <label>Framing Recommendation</label>
                      <textarea
                        rows={2}
                        value={presentationPlan.framingRecommendation}
                        onChange={(event) => patchPresentationPlan({ framingRecommendation: event.target.value })}
                      />
                    </div>
                    <div className="field">
                      <label>Continuity Checklist</label>
                      <textarea
                        rows={2}
                        value={presentationPlan.continuityChecklist}
                        onChange={(event) => patchPresentationPlan({ continuityChecklist: event.target.value })}
                      />
                    </div>
                    <div className="field">
                      <label>Retake Guidance</label>
                      <textarea
                        rows={2}
                        value={presentationPlan.retakeGuidance}
                        onChange={(event) => patchPresentationPlan({ retakeGuidance: event.target.value })}
                      />
                    </div>
                  </div>
                  {presentationPlan.sections.length ? (
                    <div className="avatar-take-list">
                      {presentationPlan.sections.map((section) => (
                        <article key={section.id} className="avatar-take-card">
                          <div>
                            <h3>{section.label}</h3>
                            <p className="muted">
                              {section.excerpt || section.summary}
                              {section.startMs != null && section.endMs != null
                                ? ` · ${formatDurationMs(section.endMs - section.startMs)}`
                                : ""}
                            </p>
                          </div>
                          <div className="gen-grid">
                            <div className="field">
                              <label>Section Summary</label>
                              <textarea
                                rows={2}
                                value={section.summary}
                                onChange={(event) =>
                                  patchPresentationSection(section.id, { summary: event.target.value })
                                }
                              />
                            </div>
                            <div className="field">
                              <label>Delivery</label>
                              <textarea
                                rows={2}
                                value={section.delivery}
                                onChange={(event) =>
                                  patchPresentationSection(section.id, { delivery: event.target.value })
                                }
                              />
                            </div>
                            <div className="field">
                              <label>Emphasis</label>
                              <textarea
                                rows={2}
                                value={section.emphasis}
                                onChange={(event) =>
                                  patchPresentationSection(section.id, { emphasis: event.target.value })
                                }
                              />
                            </div>
                            <div className="field">
                              <label>Transition</label>
                              <textarea
                                rows={2}
                                value={section.transition}
                                onChange={(event) =>
                                  patchPresentationSection(section.id, { transition: event.target.value })
                                }
                              />
                            </div>
                            <div className="field">
                              <label>Retake Focus</label>
                              <textarea
                                rows={2}
                                value={section.retakeFocus}
                                onChange={(event) =>
                                  patchPresentationSection(section.id, { retakeFocus: event.target.value })
                                }
                              />
                            </div>
                          </div>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <p className="empty">Add script or approved voice to preview presentation sections.</p>
                  )}
                </div>
              </details>
              </div>
            </details>
          ) : null}

          <details
            className="avatar-advanced-panel"
            data-testid="avatar-advanced-panel"
            open={advancedOpen}
            onToggle={(event) => setAdvancedOpen((event.currentTarget as HTMLDetailsElement).open)}
          >
            <summary data-testid="avatar-advanced-toggle">
              Advanced
              <Tip text="This is where provider choice, fallback assets, and deeper creative notes live. The main workspace stays focused on the presenter flow." />
            </summary>
            <div className="avatar-advanced-panel__body">
              <div className="field">
                <label>
                  Provider Mode
                  <Tip text="Best Match lets the studio suggest a runtime. Choose Provider saves one yourself. Compare shows the current avatar runtimes side by side." />
                </label>
                <div className="avatar-toggle-row">
                  <button
                    type="button"
                    className={activeSession.provider_mode === "best_match" ? "primary" : ""}
                    onClick={() => patchSession({ provider_mode: "best_match", provider_choice: null })}
                  >
                    Best Match
                  </button>
                  <button
                    type="button"
                    className={activeSession.provider_mode === "choose_provider" ? "primary" : ""}
                    onClick={() => patchSession({ provider_mode: "choose_provider" })}
                  >
                    Choose Provider
                  </button>
                  <button
                    type="button"
                    className={activeSession.provider_mode === "compare" ? "primary" : ""}
                    onClick={() => patchSession({ provider_mode: "compare" })}
                  >
                    Compare
                  </button>
                </div>
              </div>

              {bestProvider ? (
                <div className="avatar-provider-highlight">
                  <span className={`status-badge ${runtimeStatus(bestProvider).tone}`}>
                    {runtimeStatus(bestProvider).label}
                  </span>
                  <div>
                    <strong>{bestProvider.name}</strong>
                    <p className="muted">
                      {activeSession.provider_mode === "best_match"
                        ? "Recommended for this presenter setup."
                        : "Saved provider labels stay Experimental until live benchmarks are available."}
                    </p>
                  </div>
                </div>
              ) : (
                <div className="avatar-blocked-card">
                  <strong>No avatar runtime found yet</strong>
                  <p>Open Runtime Setup to review avatar runtimes, then let Source Manager run the approved install or repair.</p>
                  <button type="button" onClick={() => openSetup("longcat-video-avatar-1-5-local")} title="Open AI Guided Setup for avatar runtimes">
                    Open Runtime Setup
                  </button>
                </div>
              )}

              {(activeSession.provider_mode === "choose_provider" ||
                activeSession.provider_mode === "compare") && runtimeComponents.length ? (
                <div className="avatar-provider-grid" data-testid="avatar-provider-status">
                  {runtimeComponents.map((component) => {
                    const status = runtimeStatus(component);
                    const selected = activeSession.provider_choice === component.id;
                    return (
                      <button
                        key={component.id}
                        type="button"
                        className={`avatar-provider-card${selected ? " is-selected" : ""}`}
                        onClick={() =>
                          patchSession({
                            provider_mode: "choose_provider",
                            provider_choice: component.id,
                            model_id: component.id,
                          })
                        }
                      >
                        <div className="avatar-provider-card__header">
                          <strong>{component.name}</strong>
                          <span className={`status-badge ${status.tone}`}>{status.label}</span>
                        </div>
                        <span>{component.purpose || "Avatar runtime"}</span>
                      </button>
                    );
                  })}
                </div>
              ) : null}

              <div className="gen-grid">
                <div className="field">
                  <label>Reference Image</label>
                  <select
                    value={activeSession.source_still_asset_id || ""}
                    onChange={(event) =>
                      patchSession({ source_still_asset_id: event.target.value || null })
                    }
                  >
                    <option value="">Optional still…</option>
                    {imageAssets.map((asset) => (
                      <option key={asset.id} value={asset.id}>
                        {asset.tag || asset.filename}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label>Fallback Audio</label>
                  <select
                    value={activeSession.voice.fallback_audio_asset_id || ""}
                    onChange={(event) =>
                      patchSession({
                        voice: {
                          ...activeSession.voice,
                          fallback_audio_asset_id: event.target.value || null,
                        },
                      })
                    }
                  >
                    <option value="">Optional fallback audio…</option>
                    {audioAssets.map((asset) => (
                      <option key={asset.id} value={asset.id}>
                        {asset.tag || asset.filename}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="field">
                <label>Spoken Rewrite</label>
                <textarea
                  rows={3}
                  value={activeSession.dialogue_spoken}
                  onChange={(event) => patchSession({ dialogue_spoken: event.target.value })}
                  placeholder="Optional performance rewrite for the presenter."
                />
              </div>

              <div className="field">
                <label>Creative Notes</label>
                <textarea
                  rows={3}
                  value={activeSession.prompt}
                  onChange={(event) => patchSession({ prompt: event.target.value })}
                  placeholder="Extra notes for the visual performance."
                />
              </div>

              <div className="field">
                <label>Exclude Notes</label>
                <textarea
                  rows={2}
                  value={activeSession.negative_prompt}
                  onChange={(event) => patchSession({ negative_prompt: event.target.value })}
                  placeholder="What should the avatar avoid?"
                />
              </div>

              <label className="row avatar-check-row">
                <input
                  type="checkbox"
                  checked={activeSession.continuity_lock}
                  onChange={(event) => patchSession({ continuity_lock: event.target.checked })}
                />
                Keep this presenter locked to the same identity choices.
              </label>

              <div className="avatar-inline-actions">
                <button type="button" onClick={() => void refreshRuntimeStatus()}>
                  Refresh Runtime Status
                </button>
                <button type="button" onClick={() => openSetup("longcat-video-avatar-1-5-local")} title="Open AI Guided Setup for avatar runtimes">
                  Open Runtime Setup
                </button>
              </div>
            </div>
          </details>

          <div className="avatar-create-panel__cta">
            <button
              type="button"
              className="primary avatar-generate-button"
              onClick={() => void generateVideo()}
              disabled={busy || !canGenerate}
              aria-disabled={busy || !canGenerate}
              title={!canGenerate ? generateBlockReason : "Plan sections. Live video stays uncertified."}
            >
              {busy
                ? "Working..."
                : activeSession.mode === "existing_video_lipsync"
                  ? "Prepare Lip-Sync Repair"
                  : "Generate Avatar Video"}
            </button>
            <p className="muted" data-testid="avatar-generate-reason">
              {canGenerate
                ? activeSession.mode === "existing_video_lipsync"
                  ? "Creates a plan-only Lip-Sync Repair job. MuseTalk is not executed here, and the Timeline handoff does not write the Timeline."
                  : "Creates a long-form section plan. Live avatar video is not certified in this pass, and the Timeline handoff does not write the Timeline."
                : generateBlockReason}
            </p>
            {!canGenerate && generateBlockReason.includes("Voice Studio") ? (
              <button type="button" onClick={() => onGo("voicestudio")}>
                Open Voice Studio
              </button>
            ) : null}
            {!canGenerate && generateBlockReason.includes("Runtime Setup") ? (
              <button
                type="button"
                onClick={() => openSetup(selectedProvider?.id)}
                title="Open AI Guided Setup for avatar runtimes"
              >
                Open Runtime Setup
              </button>
            ) : null}
            {!canGenerate && generateBlockReason.includes("script") ? (
              <button type="button" onClick={() => onGo("scriptwriter")}>
                Open Scriptwriter
              </button>
            ) : null}
          </div>
        </aside>
      </div>

      <section className="dash-card avatar-review-panel">
        <nav className="avatar-review-tabs" role="tablist" aria-label="Avatar review tabs" data-testid="avatar-review-tabs">
          {REVIEW_TABS.map((item) => (
            <button
              key={item}
              type="button"
              role="tab"
              aria-selected={reviewTab === item}
              className={reviewTab === item ? "primary" : ""}
              onClick={() => setReviewTab(item)}
            >
              {item === "completed"
                ? "Completed Videos"
                : item[0].toUpperCase() + item.slice(1)}
            </button>
          ))}
        </nav>

        {reviewTab === "sections" ? (
          <>
            {!activeJob ? (
              <div className="avatar-review-grid">
                <article className="avatar-review-card">
                  <h3>Section Plan</h3>
                  <p>
                    Generate a long-form job to turn this presenter setup into persistent sections
                    with overlap, continuity hooks, and retryable status.
                  </p>
                </article>
                <article className="avatar-review-card">
                  <h3>Current Setup</h3>
                  <ul className="home-list">
                    <li>Avatar: {activeSession.character_name || "Not selected"}</li>
                    <li>
                      Input:{" "}
                      {activeSession.input_mode === "approved_voice"
                        ? selectedApprovedVoice
                          ? "Approved voice attached"
                          : "Approved voice still needed"
                        : scriptText.trim()
                          ? "Script ready"
                          : "Script still empty"}
                    </li>
                    <li>
                      Style:{" "}
                      {STYLE_CARDS.find((item) => item.id === activeSession.presentation_style)?.label ||
                        "Not chosen"}
                    </li>
                    <li>
                      Framing:{" "}
                      {FRAMING_CARDS.find((item) => item.id === activeSession.framing_choice)?.label ||
                        activeSession.camera.shot_size}
                    </li>
                  </ul>
                </article>
                <article className="avatar-review-card">
                  <h3>Next Best Step</h3>
                  <div className="avatar-inline-actions avatar-inline-actions--stack">
                    <button type="button" onClick={() => onGo("voicestudio")}>
                      Open Voice Studio
                    </button>
                    <button type="button" onClick={() => onGo("scriptwriter")}>
                      Open Scriptwriter
                    </button>
                    <button type="button" onClick={() => void generateVideo()} disabled={busy || !canGenerate}>
                      Plan Sections
                    </button>
                  </div>
                </article>
              </div>
            ) : (
              <div className="avatar-take-list">
                {activeSections.map((item) => {
                  const sectionPlan = (item.presentationPlan || {}) as Record<string, unknown>;
                  return (
                  <article key={item.id} className="avatar-take-card">
                    <div>
                      <h3>
                        Section {item.order + 1}
                        {item.attempt && item.attempt > 1 ? ` · Attempt ${item.attempt}` : ""}
                      </h3>
                      <p className="muted">
                        {sectionStatusLabel(item.status)} · {formatDurationMs(item.audioEndMs - item.audioStartMs)}
                        {item.overlapBeforeMs ? ` · +${Math.round(item.overlapBeforeMs / 1000)}s overlap in` : ""}
                        {item.overlapAfterMs ? ` · +${Math.round(item.overlapAfterMs / 1000)}s overlap out` : ""}
                      </p>
                      <p>{item.scriptText}</p>
                      <span className="scene-meta">
                        {item.errorMessage ||
                          `Continuity hook: ${
                            item.continuationFrameAssetId ? "Continuation frame linked" : "Waiting for continuation frame"
                          }`}
                      </span>
                      {sectionPlan.delivery || sectionPlan.transition || sectionPlan.retakeFocus ? (
                        <details className="setup-ready-details">
                          <summary>Presentation notes</summary>
                          {sectionPlan.delivery ? <div><span>Delivery</span><code>{String(sectionPlan.delivery)}</code></div> : null}
                          {sectionPlan.gaze ? <div><span>Gaze</span><code>{String(sectionPlan.gaze)}</code></div> : null}
                          {sectionPlan.gesture ? <div><span>Gesture</span><code>{String(sectionPlan.gesture)}</code></div> : null}
                          {sectionPlan.pacing ? <div><span>Pacing</span><code>{String(sectionPlan.pacing)}</code></div> : null}
                          {sectionPlan.transition ? <div><span>Transition</span><code>{String(sectionPlan.transition)}</code></div> : null}
                          {sectionPlan.retakeFocus ? <div><span>Retake Focus</span><code>{String(sectionPlan.retakeFocus)}</code></div> : null}
                        </details>
                      ) : null}
                      {Array.isArray(item.versionHistory) && item.versionHistory.length ? (
                        <p className="scene-meta">
                          {item.versionHistory.length} prior version{item.versionHistory.length === 1 ? "" : "s"} preserved for localized retakes
                        </p>
                      ) : null}
                    </div>
                    <div className="avatar-inline-actions avatar-inline-actions--stack">
                      {item.status === "failed" ? (
                        <button
                          type="button"
                          className="primary"
                          disabled={busy}
                          onClick={() => void retrySection(item.id)}
                        >
                          Retry Section
                        </button>
                      ) : null}
                      {(item.status === "completed" || item.status === "approved") && (
                        <>
                          <details className="setup-ready-details">
                            <summary>Retake Actions</summary>
                            <div className="avatar-inline-actions avatar-inline-actions--stack">
                              {RETAKE_ACTIONS.map((action) => (
                                <button
                                  key={`${item.id}-${action.id}`}
                                  type="button"
                                  disabled={
                                    busy ||
                                    (action.id === "repair_lip_sync" &&
                                      (!museTalkProvider || runtimeStatus(museTalkProvider).label === "Not Installed"))
                                  }
                                  onClick={() => void proposeRetake(item.id, action)}
                                >
                                  {action.label}
                                </button>
                              ))}
                              <button type="button" disabled={busy} onClick={() => void proposeReplaceVoice()}>
                                Replace Voice Performance
                              </button>
                              <button
                                type="button"
                                disabled={busy}
                                onClick={() => void proposeTimelineHandoff("selected_section", item.id)}
                              >
                                Send Selected Section
                              </button>
                              <button
                                type="button"
                                disabled={busy}
                                onClick={() => void proposeTimelineHandoff("replace_section", item.id)}
                              >
                                Replace Section
                              </button>
                              <button
                                type="button"
                                disabled={busy}
                                onClick={() => void proposeTimelineHandoff("create_alternate_take", item.id)}
                              >
                                Create Alternate Take
                              </button>
                            </div>
                          </details>
                          <button
                            type="button"
                            className="primary"
                            disabled={busy || item.status === "approved"}
                            onClick={() => void approveSection(item.id)}
                          >
                            {item.status === "approved" ? "Approved" : "Approve Section"}
                          </button>
                        </>
                      )}
                    </div>
                  </article>
                )})}
              </div>
            )}
          </>
        ) : null}

        {reviewTab === "takes" ? (
          <>
            {activeJob && activeSections.length ? (
              <div className="avatar-take-list">
                {activeSections
                  .slice()
                  .sort((a, b) => a.order - b.order)
                  .map((item) => (
                    <article key={`${item.id}-attempt`} className="avatar-take-card">
                      <div>
                        <h3>Section {item.order + 1}</h3>
                        <p className="muted">
                          {sectionStatusLabel(item.status)}
                          {item.retryCount ? ` · ${item.retryCount} retr${item.retryCount === 1 ? "y" : "ies"}` : ""}
                        </p>
                        <span className="scene-meta">
                          Audio window {formatDurationMs(item.audioStartMs)} → {formatDurationMs(item.audioEndMs)}
                        </span>
                      </div>
                      <div className="avatar-inline-actions">
                        {item.status === "failed" ? (
                          <button
                            type="button"
                            className="primary"
                            disabled={busy}
                            onClick={() => void retrySection(item.id)}
                          >
                            Retry Only This Section
                          </button>
                        ) : item.status === "completed" || item.status === "approved" ? (
                          <div className="avatar-inline-actions">
                            <button
                              type="button"
                              disabled={busy}
                              onClick={() =>
                                void proposeRetake(
                                  item.id,
                                  RETAKE_ACTIONS.find((choice) => choice.id === "regenerate_section") || RETAKE_ACTIONS[0],
                                )
                              }
                            >
                              Regenerate Section
                            </button>
                            <button
                              type="button"
                              disabled={busy}
                              onClick={() => void proposeTimelineHandoff("selected_section", item.id)}
                            >
                              Send Selected Section
                            </button>
                          </div>
                        ) : null}
                      </div>
                    </article>
                  ))}
              </div>
            ) : !activeSession.takes.length ? (
              <p className="empty">No takes yet. Generate the presenter section to start review.</p>
            ) : (
              <div className="avatar-take-list">
                {activeSession.takes
                  .slice()
                  .reverse()
                  .map((item) => (
                    <article key={item.id} className="avatar-take-card">
                      <div>
                        <h3>{item.label}</h3>
                        <p className="muted">
                          {item.status}
                          {item.performance_note ? ` · ${item.performance_note}` : ""}
                        </p>
                        <span className="scene-meta">{displayTime(item.created_at)}</span>
                      </div>
                      <div className="avatar-inline-actions">
                        <button
                          type="button"
                          onClick={() => {
                            window.scrollTo({ top: 0, behavior: "smooth" });
                            setMsg("Adjust the section if you want, then generate another take.");
                          }}
                        >
                          Retake
                        </button>
                        <button
                          type="button"
                          className="primary"
                          disabled={!item.asset_id || busy}
                          onClick={() => void sendTakeToDirector(item.id)}
                        >
                          Send to Timeline
                        </button>
                      </div>
                    </article>
                  ))}
              </div>
            )}
          </>
        ) : null}

        {reviewTab === "progress" ? (
          <div className="avatar-review-grid">
            <article className="avatar-review-card">
              <h3>Voice Readiness</h3>
              <p>
                {voiceReadiness?.approvedVoice
                  ? "Voice identity is approved."
                  : "Voice identity still needs approval in Voice Studio."}
              </p>
              <p className="muted">
                {approvedVoices.length
                  ? `${approvedVoices.length} approved take${approvedVoices.length === 1 ? "" : "s"} available for this presenter.`
                  : "No approved voice takes attached to this presenter yet."}
              </p>
              {resolvedAudioAssetId ? (
                <p className="muted">
                  Audio Mix can use the dialogue stem without overwriting the Voice Studio master.
                </p>
              ) : null}
            </article>
            <article className="avatar-review-card">
              <h3>Long-Form Job</h3>
              {activeJob ? (
                <>
                  <p>
                    {sectionStatusLabel(activeJob.status)} · {activeJob.progress?.completedSections || 0}/
                    {activeJob.progress?.totalSections || activeSections.length} sections ready
                  </p>
                  <p className="muted">
                    Assembly: {activeJob.assemblyState.replace(/_/g, " ")} · Completed{" "}
                    {formatDurationMs(activeJob.completedDurationMs || 0)} of{" "}
                    {formatDurationMs(activeJob.requestedDurationMs || 0)}
                  </p>
                  {activeJob.lastError?.message ? (
                    <p className="muted">{activeJob.lastError.message}</p>
                  ) : null}
                </>
              ) : (
                <p>No long-form job has been planned yet.</p>
              )}
            </article>
            <article className="avatar-review-card">
              <h3>Controls</h3>
              {issues.length ? (
                <ul className="health-list">
                  {issues.map((item, index) => (
                    <li key={`${item.text}-${index}`}>
                      <span
                        className={`status-badge ${
                          item.level === "bad" ? "bad" : item.level === "warn" ? "warn" : "ok"
                        }`}
                      >
                        {item.level}
                      </span>{" "}
                      {item.text}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted">
                  {activeJob
                    ? "Pause, resume, validate transitions, or assemble from this real job state."
                    : "Run a quick validation check before planning sections."}
                </p>
              )}
              <div className="avatar-inline-actions">
                <button type="button" onClick={() => void runValidate()} disabled={busy}>
                  Validate Setup
                </button>
                {activeJob ? (
                  <>
                    <button type="button" onClick={() => void pauseActiveJob()} disabled={busy || !canPauseJob}>
                      Pause
                    </button>
                    <button type="button" onClick={() => void resumeActiveJob()} disabled={busy || !canResumeJob}>
                      Resume
                    </button>
                    <button type="button" onClick={() => void cancelActiveJob()} disabled={busy}>
                      Cancel
                    </button>
                    <button type="button" onClick={() => void validateTransitions()} disabled={busy}>
                      Validate Transitions
                    </button>
                    <button
                      type="button"
                      className="primary"
                      onClick={() => void assembleActiveJob()}
                      disabled={busy || !canAssembleJob}
                    >
                      Assemble
                    </button>
                    <button
                      type="button"
                      disabled={busy || !completedSections.length}
                      onClick={() => void proposeTimelineHandoff("full_presentation")}
                    >
                      Full Presentation
                    </button>
                  </>
                ) : null}
                <button type="button" onClick={() => onGo("voicestudio")}>
                  Open Audio Mix
                </button>
                <button type="button" onClick={() => openSetup("musetalk-1-5-local")} title="Open AI Guided Setup for avatar runtimes">
                  Open Runtime Setup
                </button>
              </div>
            </article>
          </div>
        ) : null}

        {reviewTab === "completed" ? (
          <>
            {activeJob ? (
              activeJob.status !== "completed" ? (
                <p className="empty">
                  Final assembly is not complete yet. Finish the remaining sections and run transition
                  validation before assembling.
                </p>
              ) : (
                <div className="avatar-review-grid">
                  <article className="avatar-review-card">
                    <h3>Assembly Status</h3>
                    <p>{activeJob.assembly?.message || "Assembly stub completed."}</p>
                    <p className="muted">
                      Transition validation recorded {displayTime(activeJob.transitionValidation?.updatedAt || null)}.
                    </p>
                    <div className="avatar-inline-actions">
                      <button type="button" disabled={busy} onClick={() => void proposeTimelineHandoff("full_presentation")}>
                        Full Presentation
                      </button>
                      <button type="button" onClick={() => onGo("voicestudio")}>
                        Open Audio Mix
                      </button>
                    </div>
                  </article>
                  <article className="avatar-review-card">
                    <h3>Approved Sections</h3>
                    <p>
                      {approvedSections.length
                        ? `${approvedSections.length} section${approvedSections.length === 1 ? "" : "s"} approved for final assembly.`
                        : "No sections were explicitly approved before assembly."}
                    </p>
                    <p className="muted">
                      This pass keeps final compositor output honest: no composite video asset is claimed yet.
                    </p>
                    {activeJob.timelineProposal ? (
                      <p className="scene-meta">
                        Latest handoff: {String(activeJob.timelineProposal.placementMode || "full_presentation").replace(/_/g, " ")}
                      </p>
                    ) : null}
                  </article>
                </div>
              )
            ) : !completedTakes.length ? (
              <p className="empty">
                No completed videos yet. Timeline handoff stays a proposal and does not write the Timeline
                unless a take already has a real asset.
              </p>
            ) : (
              <div className="avatar-take-list">
                {completedTakes
                  .slice()
                  .reverse()
                  .map((item) => (
                    <article key={`${item.id}-complete`} className="avatar-take-card">
                      <div>
                        <h3>{item.label}</h3>
                        <p className="muted">
                          {item.status === "final" || item.approved ? "Ready for Timeline" : item.status}
                        </p>
                        <span className="scene-meta">{displayTime(item.created_at)}</span>
                      </div>
                      <div className="avatar-inline-actions">
                        <button
                          type="button"
                          className="primary"
                          disabled={!item.asset_id || busy}
                          onClick={() => void sendTakeToDirector(item.id)}
                        >
                          Open in Timeline
                        </button>
                      </div>
                    </article>
                  ))}
              </div>
            )}
          </>
        ) : null}
      </section>
    </div>
  );
}
