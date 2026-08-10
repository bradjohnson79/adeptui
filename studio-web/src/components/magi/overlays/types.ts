export type MagiTextAnimationPreset =
  | "none"
  | "fade"
  | "slide_left"
  | "slide_right"
  | "slide_up"
  | "slide_down"
  | "scale_in"
  | "wipe"
  | null;

export type MagiVectorShape =
  | "rectangle"
  | "rounded_rectangle"
  | "line"
  | "circle"
  | "ellipse"
  | "triangle"
  | "chevron"
  | "accent_bar"
  | "divider";

export type MagiTextStyle = {
  fontFamily: string;
  fontSize: number;
  fontWeight: number;
  fontStyle: "normal" | "italic";
  textDecoration: "none" | "underline";
  color: string;
  alignment: "left" | "center" | "right";
  verticalAlignment: "top" | "middle" | "bottom";
  lineHeight: number;
  letterSpacing: number;
  wordSpacing: number;
  uppercase: boolean;
  maxLines: number | null;
  autoFit: boolean;
  strokeColor: string | null;
  strokeWidth: number;
  shadowEnabled: boolean;
  shadowColor: string;
  shadowBlur: number;
  shadowOffsetX: number;
  shadowOffsetY: number;
};

export type MagiTextBackgroundStyle = {
  enabled: boolean;
  fill: string;
  opacity: number;
  paddingTop: number;
  paddingRight: number;
  paddingBottom: number;
  paddingLeft: number;
  cornerRadius: number;
  borderEnabled: boolean;
  borderColor: string;
  borderWidth: number;
  autoSize: boolean;
  fixedWidth: number | null;
};

export type MagiOverlayElementBase = {
  id: string;
  type: "text" | "vector" | "group";
  name: string;
  visible: boolean;
  locked: boolean;
  opacity: number;
  x: number;
  y: number;
  width: number;
  height: number;
  rotation: number;
  anchorX: number;
  anchorY: number;
  zIndex: number;
  startFrame: number | null;
  endFrame: number | null;
  createdAt: string;
  updatedAt: string;
};

export type MagiTextElement = MagiOverlayElementBase & {
  type: "text";
  text: string;
  textStyle: MagiTextStyle;
  backgroundStyle: MagiTextBackgroundStyle | null;
  animationPreset: MagiTextAnimationPreset;
};

export type MagiVectorElement = MagiOverlayElementBase & {
  type: "vector";
  shape: MagiVectorShape;
  fill: string | null;
  stroke: string | null;
  strokeWidth: number;
  cornerRadius: number;
};

export type MagiOverlayGroup = MagiOverlayElementBase & {
  type: "group";
  children: MagiOverlayElement[];
  groupKind?: "lower_third" | "generic";
};

export type MagiOverlayElement = MagiTextElement | MagiVectorElement | MagiOverlayGroup;

export type MagiOverlayComposition = {
  schemaVersion: 1;
  compositionId: string;
  projectId: string;
  sourceAssetId: string | null;
  canvasWidth: number;
  canvasHeight: number;
  overlays: MagiOverlayElement[];
  safeAreaEnabled: boolean;
  createdAt: string;
  updatedAt: string;
};

export type MagiCommandStage =
  | "NotParsed"
  | "Parsed"
  | "NeedsClarification"
  | "Proposed"
  | "ReadyForApproval"
  | "Blocked"
  | "Enqueued"
  | "Running"
  | "Failed"
  | "CompletedTechnically"
  | "ReviewRequired";

export const DEFAULT_TEXT_STYLE: MagiTextStyle = {
  fontFamily: "dejavu-sans",
  fontSize: 48,
  fontWeight: 700,
  fontStyle: "normal",
  textDecoration: "none",
  color: "#FFFFFF",
  alignment: "left",
  verticalAlignment: "middle",
  lineHeight: 1.2,
  letterSpacing: 0,
  wordSpacing: 0,
  uppercase: false,
  maxLines: null,
  autoFit: false,
  strokeColor: null,
  strokeWidth: 0,
  shadowEnabled: true,
  shadowColor: "#000000",
  shadowBlur: 4,
  shadowOffsetX: 1,
  shadowOffsetY: 1,
};

export const DEFAULT_BG: MagiTextBackgroundStyle = {
  enabled: false,
  fill: "#000000",
  opacity: 0.55,
  paddingTop: 8,
  paddingRight: 14,
  paddingBottom: 8,
  paddingLeft: 14,
  cornerRadius: 4,
  borderEnabled: false,
  borderColor: "#FFFFFF",
  borderWidth: 1,
  autoSize: true,
  fixedWidth: null,
};

function now() {
  return new Date().toISOString();
}

function nid(prefix: string) {
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}`;
}

export function emptyComposition(
  projectId: string,
  sourceAssetId: string | null,
  w = 1920,
  h = 1080
): MagiOverlayComposition {
  const t = now();
  return {
    schemaVersion: 1,
    compositionId: nid("comp"),
    projectId,
    sourceAssetId,
    canvasWidth: w,
    canvasHeight: h,
    overlays: [],
    safeAreaEnabled: true,
    createdAt: t,
    updatedAt: t,
  };
}

export function createTextElement(partial?: Partial<MagiTextElement>): MagiTextElement {
  const t = now();
  return {
    id: nid("txt"),
    type: "text",
    name: "Text",
    visible: true,
    locked: false,
    opacity: 1,
    x: 0.1,
    y: 0.1,
    width: 0.4,
    height: 0.08,
    rotation: 0,
    anchorX: 0,
    anchorY: 0,
    zIndex: 10,
    startFrame: null,
    endFrame: null,
    createdAt: t,
    updatedAt: t,
    text: "MAGI Title",
    textStyle: { ...DEFAULT_TEXT_STYLE },
    backgroundStyle: { ...DEFAULT_BG },
    animationPreset: null,
    ...partial,
  };
}

export function createVectorElement(shape: MagiVectorShape = "rectangle"): MagiVectorElement {
  const t = now();
  return {
    id: nid("vec"),
    type: "vector",
    name: shape,
    visible: true,
    locked: false,
    opacity: 1,
    x: 0.08,
    y: 0.78,
    width: 0.42,
    height: 0.12,
    rotation: 0,
    anchorX: 0,
    anchorY: 0,
    zIndex: 5,
    startFrame: null,
    endFrame: null,
    createdAt: t,
    updatedAt: t,
    shape,
    fill: "#7c3aed",
    stroke: null,
    strokeWidth: 0,
    cornerRadius: shape === "rounded_rectangle" ? 8 : 0,
  };
}

export function createLowerThirdGroup(primary = "ANADRIYA", secondary = "Captain, Venture Command"): MagiOverlayGroup {
  const t = now();
  const bar = createVectorElement("accent_bar");
  bar.id = nid("vec");
  bar.x = 0.06;
  bar.y = 0.78;
  bar.width = 0.46;
  bar.height = 0.11;
  bar.fill = "#111827";
  bar.opacity = 0.82;
  bar.zIndex = 1;
  const accent = createVectorElement("accent_bar");
  accent.id = nid("vec");
  accent.x = 0.06;
  accent.y = 0.78;
  accent.width = 0.01;
  accent.height = 0.11;
  accent.fill = "#a78bfa";
  accent.zIndex = 2;
  const p = createTextElement({
    id: nid("txt"),
    name: "Primary",
    text: primary,
    x: 0.09,
    y: 0.785,
    width: 0.4,
    height: 0.05,
    zIndex: 3,
    textStyle: { ...DEFAULT_TEXT_STYLE, fontSize: 40, uppercase: true },
    backgroundStyle: { ...DEFAULT_BG, enabled: false },
  });
  const s = createTextElement({
    id: nid("txt"),
    name: "Secondary",
    text: secondary,
    x: 0.09,
    y: 0.835,
    width: 0.4,
    height: 0.04,
    zIndex: 4,
    textStyle: { ...DEFAULT_TEXT_STYLE, fontSize: 22, fontWeight: 400 },
    backgroundStyle: { ...DEFAULT_BG, enabled: false },
  });
  return {
    id: nid("grp"),
    type: "group",
    name: "Lower Third",
    visible: true,
    locked: false,
    opacity: 1,
    x: 0.06,
    y: 0.78,
    width: 0.46,
    height: 0.11,
    rotation: 0,
    anchorX: 0,
    anchorY: 0,
    zIndex: 20,
    startFrame: null,
    endFrame: null,
    createdAt: t,
    updatedAt: t,
    groupKind: "lower_third",
    children: [bar, accent, p, s],
  };
}

/** Flatten for timeline projection — only real IDs. */
export function flattenOverlayIds(overlays: MagiOverlayElement[]): MagiOverlayElement[] {
  const out: MagiOverlayElement[] = [];
  for (const el of overlays) {
    out.push(el);
    if (el.type === "group") out.push(...flattenOverlayIds(el.children));
  }
  return out;
}
