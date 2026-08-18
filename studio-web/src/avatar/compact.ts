/**
 * Avatar Studio compact creator helpers.
 * Main path: source → speaker(s) → dialogue → generator → aspect → generate.
 */
import type { AvatarSession } from "./types";

export const AVATAR_GENERATOR_IDS = [
  "infinitetalk-local",
  "longcat-video-avatar-1-5-local",
] as const;

export const AVATAR_EXCLUDED_GENERATOR_IDS = [
  "musetalk-1-5-local",
  "echomimic-v2-local",
  "minimax-h3",
  "minimax-hailuo",
  "ltx_2_5_distilled",
  "ltx-2-5-distilled",
] as const;

export const AVATAR_ASPECT_RATIOS = ["1:1", "4:5", "3:2", "16:9", "9:16", "21:9"] as const;

export const AVATAR_STYLE_OPTIONS = [
  { id: "direct_presenter", label: "Direct Presenter" },
  { id: "warm_host", label: "Warm Host" },
  { id: "guided_explainer", label: "Guided Explainer" },
  { id: "stylized_performance", label: "Stylized Performance" },
] as const;

export const AVATAR_FRAMING_OPTIONS = [
  { id: "tight_headline", label: "Tight Headline" },
  { id: "medium_presenter", label: "Presenter Frame" },
  { id: "desk_or_podium", label: "Desk or Podium" },
  { id: "full_stage", label: "Full Stage" },
] as const;

export const AVATAR_BACKGROUND_OPTIONS = [
  { id: "studio_gradient", label: "Studio" },
  { id: "branded_set", label: "Branded Set" },
  { id: "soft_environment", label: "Environment" },
  { id: "graphic_canvas", label: "Graphic Canvas" },
] as const;

export const AVATAR_DURATION_OPTIONS = [
  { id: "quick_update", label: "Quick Update" },
  { id: "story_section", label: "Story Section" },
  { id: "chapter_pass", label: "Chapter Pass" },
] as const;


export type AvatarSourceKind = "character" | "library" | "still" | "video";
export type AvatarModeKind = "single" | "conversation";
export type AvatarConversationOrder = "a_then_b" | "b_then_a";

export type AvatarSpeaker = {
  id: string;
  label: string;
  character_id?: string | null;
  bbox?: { x: number; y: number; w: number; h: number } | null;
  mask_asset_id?: string | null;
};

export type AvatarConversationTurn = {
  speakerId: string;
  dialogue: string;
};

export type AvatarConversation = {
  order: AvatarConversationOrder;
  turns: AvatarConversationTurn[];
};

export type AvatarLoraSelection = {
  loraId: string;
  name: string;
  strength: number;
} | null;

export type AvatarRuntimeCapabilities = {
  id: string;
  displayName: string;
  listedAsAvatarGenerator: boolean;
  supportsSpeakerSelection: boolean;
  supportsConversation: boolean;
  supportsNativeMultiSpeaker: boolean;
  supportsAudio: boolean;
  supportsLoRA: boolean;
  supportedAspectRatios: string[];
  loraModelFamily: string;
};

export const AVATAR_COMPACT_MAIN_TESTIDS = [
  "avatar-source-kind",
  "avatar-mode-kind",
  "avatar-speaker-a",
  "avatar-dialogue",
  "avatar-generator",
  "avatar-aspect",
  "avatar-generate-button",
] as const;

export function defaultSpeakers(session?: Partial<AvatarSession> | null): AvatarSpeaker[] {
  const characterId = session?.character_profile_id || null;
  const label = characterId && session?.character_name ? session.character_name : "Person 1";
  return [
    {
      id: "speaker-a",
      label,
      character_id: characterId,
      bbox: null,
      mask_asset_id: null,
    },
  ];
}

export function defaultConversation(session?: Partial<AvatarSession> | null): AvatarConversation {
  const dialogue = String(session?.dialogue_original || session?.dialogue_spoken || "");
  return {
    order: "a_then_b",
    turns: [{ speakerId: "speaker-a", dialogue }],
  };
}

export function inferSourceKind(session: Partial<AvatarSession> | null | undefined): AvatarSourceKind {
  const explicit = session?.source_kind;
  if (explicit === "character" || explicit === "library" || explicit === "still" || explicit === "video") {
    return explicit;
  }
  if (session?.source_video_asset_id) return "video";
  if (session?.character_profile_id) return "character";
  if (session?.source_still_asset_id) return "library";
  return "character";
}

export function speakerLabel(speaker: AvatarSpeaker | undefined, fallbackIndex: 1 | 2): string {
  const label = String(speaker?.label || "").trim();
  if (label) return label;
  return fallbackIndex === 1 ? "Person 1" : "Person 2";
}

export function conversationTurnsInOrder(conversation: AvatarConversation | null | undefined): AvatarConversationTurn[] {
  const turns = [...(conversation?.turns || [])];
  const order = conversation?.order || "a_then_b";
  const first = order === "b_then_a" ? "speaker-b" : "speaker-a";
  const second = first === "speaker-a" ? "speaker-b" : "speaker-a";
  const byId = new Map(turns.map((turn) => [turn.speakerId, turn]));
  return [first, second]
    .map((id) => byId.get(id) || { speakerId: id, dialogue: "" })
    .filter((turn) => turn.dialogue.trim() || byId.has(turn.speakerId));
}

export function compiledDialogueFromConversation(session: AvatarSession): string {
  if (session.mode_kind !== "conversation") {
    return session.dialogue_original || session.dialogue_spoken || "";
  }
  return conversationTurnsInOrder(session.conversation)
    .map((turn) => turn.dialogue.trim())
    .filter(Boolean)
    .join("\n\n");
}

export function loraFamilyForGenerator(generatorId: string): string {
  if (generatorId === "longcat-video-avatar-1-5-local") return "longcat";
  if (generatorId === "infinitetalk-local") return "wan";
  return "video";
}

export function isListedAvatarGenerator(id: string): boolean {
  return (AVATAR_GENERATOR_IDS as readonly string[]).includes(id);
}

export function runtimeGateLine(name: string, label: string): string {
  const runtimeName = name.trim() || "InfiniteTalk";
  if (label === "Not Installed") {
    return `${runtimeName} is not installed. Open Runtime Setup to install it.`;
  }
  if (label === "Choose Runtime") {
    return "No avatar runtime selected. Open Runtime Setup.";
  }
  return `${runtimeName} needs repair — Open Runtime Setup`;
}

export function hydrateCompactSession<T extends AvatarSession>(session: T): T {
  const source_kind = inferSourceKind(session);
  const speakers =
    Array.isArray(session.speakers) && session.speakers.length ? session.speakers : defaultSpeakers(session);
  const conversation =
    session.conversation && Array.isArray(session.conversation.turns)
      ? session.conversation
      : defaultConversation(session);
  const look = {
    ...session.look,
    aspect: session.look?.aspect || session.camera?.aspect || "16:9",
  };
  const camera = {
    ...session.camera,
    aspect: session.camera?.aspect || look.aspect || "16:9",
  };
  const modelId = isListedAvatarGenerator(session.model_id)
    ? session.model_id
    : session.provider_choice && isListedAvatarGenerator(session.provider_choice)
      ? session.provider_choice
      : "infinitetalk-local";
  return {
    ...session,
    source_kind,
    mode_kind: session.mode_kind === "conversation" ? "conversation" : "single",
    speakers,
    conversation,
    lora: session.lora ?? null,
    direction_prompt: session.direction_prompt || "",
    look,
    camera,
    model_id: modelId,
    provider_choice: session.provider_choice && isListedAvatarGenerator(session.provider_choice)
      ? session.provider_choice
      : session.provider_choice && (AVATAR_EXCLUDED_GENERATOR_IDS as readonly string[]).includes(session.provider_choice)
        ? null
        : session.provider_choice || modelId,
  };
}
