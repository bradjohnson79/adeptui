export type MagiPaneId =
  | "project"
  | "media"
  | "assets"
  | "graphics"
  | "actions"
  | "command"
  | "recipes"
  | "inspector"
  | "renderQueue";

export type MagiWorkspacePreset =
  | "default"
  | "viewer-focus"
  | "image-editing"
  | "mask-editing"
  | "compare-review"
  | "custom";

/** @deprecated alias */
export type MagiPreset = MagiWorkspacePreset;

export type MagiWorkspaceLayoutV1 = {
  schemaVersion: 1;
  leftDockWidth: number;
  rightDockWidth: number;
  timelineHeight: number;
  leftDockCollapsed: boolean;
  rightDockCollapsed: boolean;
  timelineCollapsed: boolean;
  leftPaneOrder: MagiPaneId[];
  rightPaneOrder: MagiPaneId[];
  accordionState: Record<string, boolean>;
  activePreset: MagiWorkspacePreset;
  renderQueueOpen: boolean;
};

const STORAGE_KEY = "adept_magi_workspace_layout_v1";

export const LAYOUT_LIMITS = {
  leftMin: 220,
  leftMaxPct: 0.32,
  rightMin: 240,
  rightMaxPct: 0.34,
  viewerMinPct: 0.42,
  viewerMinPx: 480,
  timelineMin: 250,
  timelineDefault: 280,
  timelineMaxVh: 0.48,
} as const;

export const DEFAULT_LAYOUT: MagiWorkspaceLayoutV1 = {
  schemaVersion: 1,
  leftDockWidth: 280,
  rightDockWidth: 300,
  timelineHeight: LAYOUT_LIMITS.timelineDefault,
  leftDockCollapsed: false,
  rightDockCollapsed: false,
  timelineCollapsed: false,
  leftPaneOrder: [
    "project",
    "media",
    "assets",
    "recipes",
    "graphics",
    "actions",
    "command",
  ],
  rightPaneOrder: ["inspector"],
  accordionState: {
    project: false,
    media: true,
    assets: false,
    recipes: false,
    graphics: false,
    actions: false,
    command: false,
    transform: true,
    color: true,
    prompt: true,
    lighting: false,
    effects: false,
    audio: false,
    clipProperties: false,
    export: false,
    compare: false,
    aiAssist: false,
    overlayText: true,
    overlayTypography: true,
    overlayBackground: false,
    overlayStroke: false,
    overlayTransform: true,
    overlayLayer: false,
    overlayTiming: false,
    overlayAnimation: false,
    overlayLowerThird: true,
  },
  activePreset: "default",
  renderQueueOpen: false,
};

function normalizeLegacyPane(value: unknown): MagiPaneId | null {
  if (value === "textGraphics") return "graphics";
  if (value === "project" || value === "media" || value === "assets" || value === "graphics") return value;
  if (value === "recipes" || value === "actions" || value === "command" || value === "inspector") return value;
  if (value === "renderQueue") return value;
  return null;
}

function migrateAccordionState(state: Record<string, boolean> | undefined): Record<string, boolean> {
  const next = { ...(state || {}) };
  if (typeof next.textGraphics === "boolean" && typeof next.graphics !== "boolean") {
    next.graphics = next.textGraphics;
  }
  if (typeof next.colorPrompt === "boolean") {
    if (typeof next.color !== "boolean") next.color = next.colorPrompt;
    if (typeof next.prompt !== "boolean") next.prompt = next.colorPrompt;
  }
  if (typeof next.lightRelight === "boolean" && typeof next.lighting !== "boolean") {
    next.lighting = next.lightRelight;
  }
  if (typeof next.compareVersions === "boolean" && typeof next.compare !== "boolean") {
    next.compare = next.compareVersions;
  }
  if (typeof next.metadata === "boolean" && typeof next.clipProperties !== "boolean") {
    next.clipProperties = next.metadata;
  }
  return {
    ...DEFAULT_LAYOUT.accordionState,
    ...next,
  };
}

function clamp(n: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, n));
}

export function clampLeftWidth(n: number, upperWidth = 1400): number {
  const max = Math.max(LAYOUT_LIMITS.leftMin, Math.floor(upperWidth * LAYOUT_LIMITS.leftMaxPct));
  return clamp(n, LAYOUT_LIMITS.leftMin, max);
}

export function clampRightWidth(n: number, upperWidth = 1400): number {
  const max = Math.max(LAYOUT_LIMITS.rightMin, Math.floor(upperWidth * LAYOUT_LIMITS.rightMaxPct));
  return clamp(n, LAYOUT_LIMITS.rightMin, max);
}

export function clampTimelineHeight(n: number, viewportH = 900): number {
  const max = Math.max(
    LAYOUT_LIMITS.timelineMin,
    Math.floor(viewportH * LAYOUT_LIMITS.timelineMaxVh)
  );
  return clamp(n, LAYOUT_LIMITS.timelineMin, max);
}

export function validateMagiLayout(raw: unknown): MagiWorkspaceLayoutV1 | null {
  if (!raw || typeof raw !== "object") return null;
  const parsed = raw as Record<string, unknown>;
  const schemaVersion = parsed.schemaVersion ?? parsed.version;
  if (schemaVersion !== 1) return null;

  // Migrate legacy field names
  const leftPaneOrder = (parsed.leftPaneOrder || parsed.leftDock) as unknown[] | undefined;
  const rightPaneOrder = (parsed.rightPaneOrder || parsed.rightDock) as unknown[] | undefined;
  if (!Array.isArray(leftPaneOrder) || !Array.isArray(rightPaneOrder)) return null;

  const left = leftPaneOrder.map(normalizeLegacyPane).filter((p): p is MagiPaneId => Boolean(p));
  const right = rightPaneOrder.map(normalizeLegacyPane).filter((p): p is MagiPaneId => Boolean(p));

  const seen = new Set<string>();
  for (const p of [...left, ...right]) {
    if (seen.has(p)) return null;
    seen.add(p);
  }

  const leftDockWidth = Number(parsed.leftDockWidth ?? parsed.leftWidth);
  const rightDockWidth = Number(parsed.rightDockWidth ?? parsed.rightWidth);
  const timelineHeight = Number(parsed.timelineHeight);
  if (![leftDockWidth, rightDockWidth, timelineHeight].every((n) => Number.isFinite(n))) return null;
  if (leftDockWidth < LAYOUT_LIMITS.leftMin || rightDockWidth < LAYOUT_LIMITS.rightMin) return null;
  if (timelineHeight < LAYOUT_LIMITS.timelineMin) return null;

  return {
    schemaVersion: 1,
    leftDockWidth: clampLeftWidth(leftDockWidth),
    rightDockWidth: clampRightWidth(rightDockWidth),
    timelineHeight: clampTimelineHeight(timelineHeight),
    leftDockCollapsed: Boolean(parsed.leftDockCollapsed),
    rightDockCollapsed: Boolean(parsed.rightDockCollapsed),
    timelineCollapsed: Boolean(parsed.timelineCollapsed),
    leftPaneOrder: left.length ? left : [...DEFAULT_LAYOUT.leftPaneOrder],
    rightPaneOrder: right.length ? right : [...DEFAULT_LAYOUT.rightPaneOrder],
    accordionState: migrateAccordionState((parsed.accordionState as Record<string, boolean>) || {}),
    activePreset: (parsed.activePreset || parsed.preset || "custom") as MagiWorkspacePreset,
    renderQueueOpen: Boolean(parsed.renderQueueOpen),
  };
}

export function loadMagiLayout(): MagiWorkspaceLayoutV1 {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_LAYOUT, accordionState: { ...DEFAULT_LAYOUT.accordionState } };
    const validated = validateMagiLayout(JSON.parse(raw));
    if (!validated) {
      return { ...DEFAULT_LAYOUT, accordionState: { ...DEFAULT_LAYOUT.accordionState } };
    }
    return validated;
  } catch {
    return { ...DEFAULT_LAYOUT, accordionState: { ...DEFAULT_LAYOUT.accordionState } };
  }
}

export function saveMagiLayout(layout: MagiWorkspaceLayoutV1): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(layout));
  } catch {
    /* ignore */
  }
}

export function applyPreset(
  preset: MagiWorkspacePreset,
  current: MagiWorkspaceLayoutV1
): MagiWorkspaceLayoutV1 {
  const base = { ...current, activePreset: preset, accordionState: { ...current.accordionState } };
  switch (preset) {
    case "viewer-focus":
      return {
        ...base,
        leftDockCollapsed: true,
        rightDockCollapsed: true,
        timelineHeight: LAYOUT_LIMITS.timelineMin,
      };
    case "image-editing":
      return {
        ...base,
        leftDockCollapsed: false,
        rightDockCollapsed: false,
        accordionState: {
          ...base.accordionState,
          project: false,
          media: true,
          recipes: false,
          graphics: false,
          actions: true,
          command: true,
          transform: true,
          color: true,
          prompt: true,
          compare: false,
        },
        timelineHeight: 260,
      };
    case "mask-editing":
      return {
        ...base,
        leftDockCollapsed: false,
        rightDockCollapsed: false,
        accordionState: {
          ...base.accordionState,
          media: true,
          graphics: true,
          transform: true,
          prompt: false,
        },
        timelineHeight: LAYOUT_LIMITS.timelineMin,
      };
    case "compare-review":
      return {
        ...base,
        accordionState: {
          ...base.accordionState,
          media: false,
          compare: true,
          clipProperties: true,
          color: true,
        },
        timelineHeight: 260,
      };
    case "default":
      return { ...DEFAULT_LAYOUT, accordionState: { ...DEFAULT_LAYOUT.accordionState } };
    default:
      return { ...base, activePreset: "custom" };
  }
}
