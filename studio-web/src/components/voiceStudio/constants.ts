export type StudioMethod = "existing" | "create" | "clone" | "upload";
export type StudioPhase = "method" | "create" | "select" | "performance" | "approve";

export const METHOD_CARDS: {
  id: StudioMethod;
  label: string;
  description: string;
  legacyId: "LIBRARY" | "DESIGN" | "CLONE" | "UPLOAD";
}[] = [
  {
    id: "existing",
    label: "Use Existing Voice",
    description: "Use a voice already approved or saved for this character.",
    legacyId: "LIBRARY",
  },
  {
    id: "create",
    label: "Create New Voice",
    description: "Generate a brand-new voice from a description.",
    legacyId: "DESIGN",
  },
  {
    id: "clone",
    label: "Clone from Recording",
    description: "Create a reusable voice from an authorized speaker sample.",
    legacyId: "CLONE",
  },
  {
    id: "upload",
    label: "Upload Voice",
    description: "Import a reusable voice package or audio reference.",
    legacyId: "UPLOAD",
  },
];

export const VOICE_TYPES = ["Female", "Male", "Androgynous", "Custom"] as const;
export const AGES = ["Child", "Teenager", "Young Adult", "Middle-aged", "Senior", "Custom"] as const;
export const ARCHETYPES = [
  "Hero",
  "Rebel",
  "Mentor",
  "Leader",
  "Explorer",
  "Scientist",
  "Mystic",
  "Trickster",
  "Royal",
  "Villain",
  "Antihero",
  "Caregiver",
  "Outsider",
  "Custom",
] as const;
export const ACCENTS = [
  "Neutral Contemporary English",
  "American",
  "Canadian",
  "British",
  "Australian",
  "Irish",
  "Scottish",
  "Custom",
  "No specific accent",
] as const;

export const FINE_TUNE_SLIDERS: { key: "pitch" | "energy" | "warmth" | "playfulness" | "confidence" | "speakingSpeed"; label: string; tip: string }[] = [
  { key: "pitch", label: "Pitch", tip: "How high or low the voice sounds." },
  { key: "energy", label: "Energy", tip: "How lively and driven the delivery feels." },
  { key: "warmth", label: "Warmth", tip: "How friendly and soft the tone feels." },
  { key: "playfulness", label: "Playfulness", tip: "How teasing or lighthearted the voice feels." },
  { key: "confidence", label: "Confidence", tip: "How sure and steady the speaker sounds." },
  { key: "speakingSpeed", label: "Speaking Speed", tip: "How quickly the character tends to talk." },
];

export const SAMPLE_LINE_OPTIONS = [
  { id: "neutral", label: "Neutral introduction" },
  { id: "personality", label: "Character personality" },
  { id: "contrast", label: "Emotional contrast" },
  { id: "custom", label: "Custom text" },
] as const;

export const MOODS = [
  "Neutral",
  "Happy",
  "Playful",
  "Sarcastic",
  "Annoyed",
  "Serious",
  "Vulnerable",
  "Excited",
  "Defiant",
  "Warm",
] as const;

export const KORRI_MOOD_PRIORITY = ["Playful", "Sarcastic", "Defiant", "Annoyed", "Warm", "Vulnerable"];

export const DELIVERY_SPEED = ["Slow", "Natural", "Fast"] as const;
export const DELIVERY_STRENGTH = ["Soft", "Natural", "Strong"] as const;
export const DELIVERY_STYLE = [
  "Conversational",
  "Dry",
  "Warm",
  "Excited",
  "Dramatic",
  "Restrained",
] as const;

export const REACTION_ACTIONS: { id: string; label: string; reaction: string; pauseMs: number }[] = [
  { id: "pause-brief", label: "Pause Briefly", reaction: "", pauseMs: 220 },
  { id: "pause-long", label: "Long Pause", reaction: "", pauseMs: 480 },
  { id: "laugh", label: "Small Laugh", reaction: "laugh", pauseMs: 220 },
  { id: "scoff", label: "Scoff", reaction: "scoff", pauseMs: 220 },
  { id: "sigh", label: "Sigh", reaction: "exhale", pauseMs: 280 },
  { id: "whisper", label: "Whisper", reaction: "breath", pauseMs: 180 },
];

export const ADJUSTMENT_CHIPS = [
  "More sarcastic",
  "Less exaggerated",
  "Softer",
  "Faster",
  "Slower",
  "More emotional",
  "Add Pause",
  "Remove Reaction",
] as const;

export const CODIRECTOR_CHIPS = [
  "Make Korri more sarcastic",
  "Warmer delivery",
  "Younger voice",
  "Sharper comic timing",
  "Add playful scoff",
  "Soften final line",
] as const;

export const UPLOAD_KINDS: { id: string; label: string; hint: string }[] = [
  {
    id: "reusable_character_voice",
    label: "Reusable character voice",
    hint: "Becomes a selectable Character Voice Version after consent.",
  },
  {
    id: "voice_reference",
    label: "Voice reference",
    hint: "Used for cloning — does not become an identity by itself.",
  },
  {
    id: "audition_sample",
    label: "Audition sample",
    hint: "For listening and evaluation only.",
  },
  {
    id: "finished_dialogue_performance",
    label: "Finished dialogue performance",
    hint: "A finished line — never silently becomes a reusable voice identity.",
  },
];

export const READINESS_LABELS = {
  none: "Voice not created",
  generatingVoices: "Generating voices",
  chooseVoice: "Choose a voice",
  readyPerformance: "Ready for performance",
  generatingPerf: "Generating performances",
  chooseTake: "Choose a take",
  readyApprove: "Ready to approve",
  approved: "Approved",
  needsAttention: "Needs attention",
} as const;

export function moodToEmotionId(mood: string): string {
  const m = mood.toLowerCase();
  const map: Record<string, string> = {
    neutral: "neutral",
    happy: "happy",
    playful: "playful",
    sarcastic: "sarcastic",
    annoyed: "annoyed",
    serious: "sincere",
    vulnerable: "vulnerable",
    excited: "surprised",
    defiant: "defiant",
    warm: "sincere",
  };
  return map[m] || "neutral";
}

export function speedToPace(speed: string): "slow" | "normal" | "fast" {
  if (speed === "Slow") return "slow";
  if (speed === "Fast") return "fast";
  return "normal";
}

export function strengthToDelivery(strength: string, style: string): string {
  const base =
    strength === "Soft" ? "soft" : strength === "Strong" ? "sharp" : "natural";
  return `${base}, ${style.toLowerCase()}`;
}
