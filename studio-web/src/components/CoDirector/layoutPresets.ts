export type CoDirectorLayoutPreset = "chat-focus" | "balanced" | "project-focus";

export const CODIRECTOR_SPLIT_STORAGE_KEY = "adept_codirector_split_primary";
export const CODIRECTOR_SPLIT_PRESET_KEY = "adept_codirector_split_preset";

/** Chat (primary) share of the workspace width. */
export const LAYOUT_PRESET_RATIOS: Record<CoDirectorLayoutPreset, number> = {
  "chat-focus": 0.7,
  balanced: 0.5,
  "project-focus": 0.3,
};

export const LAYOUT_PRESET_LABELS: Record<CoDirectorLayoutPreset, string> = {
  "chat-focus": "Chat Focus",
  balanced: "Balanced",
  "project-focus": "Project Focus",
};

export const LAYOUT_PRESET_ORDER: CoDirectorLayoutPreset[] = [
  "chat-focus",
  "balanced",
  "project-focus",
];

export function loadLayoutPreset(): CoDirectorLayoutPreset {
  try {
    const raw = localStorage.getItem(CODIRECTOR_SPLIT_PRESET_KEY);
    if (raw === "chat-focus" || raw === "balanced" || raw === "project-focus") return raw;
  } catch {
    /* ignore */
  }
  return "balanced";
}

export function saveLayoutPreset(preset: CoDirectorLayoutPreset): void {
  try {
    localStorage.setItem(CODIRECTOR_SPLIT_PRESET_KEY, preset);
  } catch {
    /* ignore */
  }
}

export function primarySizeForPreset(containerWidth: number, preset: CoDirectorLayoutPreset): number {
  const ratio = LAYOUT_PRESET_RATIOS[preset];
  return Math.round(Math.max(280, containerWidth * ratio));
}
