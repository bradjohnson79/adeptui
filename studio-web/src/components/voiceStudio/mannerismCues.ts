/** Controlled mannerism cues for Voice Performance — direction, never spoken TTS text. */

export type MannerismCueId =
  | "sigh"
  | "chuckle"
  | "laugh"
  | "soft_laugh"
  | "gasp"
  | "breath_in"
  | "breath_out"
  | "whisper"
  | "pause"
  | "hesitate"
  | "scoff"
  | "nervous_breath";

export type MannerismPosition = "before" | "during" | "after";
export type MannerismIntensity = "light" | "medium" | "strong";

export type MannerismCue = {
  id: MannerismCueId;
  label: string;
  position: MannerismPosition;
  intensity: MannerismIntensity;
  source?: string;
  nativeSupport?: boolean;
  approximationMode?: string;
  approximationNote?: string;
};

export const MANNERISM_CUE_OPTIONS: { id: MannerismCueId; label: string }[] = [
  { id: "sigh", label: "Sigh" },
  { id: "chuckle", label: "Chuckle" },
  { id: "laugh", label: "Laugh" },
  { id: "soft_laugh", label: "Soft Laugh" },
  { id: "gasp", label: "Gasp" },
  { id: "breath_in", label: "Breath In" },
  { id: "breath_out", label: "Breath Out" },
  { id: "whisper", label: "Whisper" },
  { id: "pause", label: "Pause" },
  { id: "hesitate", label: "Hesitate" },
  { id: "scoff", label: "Scoff" },
  { id: "nervous_breath", label: "Nervous Breath" },
];

export const MANNERISM_POSITION_OPTIONS: { id: MannerismPosition; label: string }[] = [
  { id: "before", label: "Before line" },
  { id: "during", label: "During line" },
  { id: "after", label: "After line" },
];

export const MANNERISM_INTENSITY_OPTIONS: { id: MannerismIntensity; label: string }[] = [
  { id: "light", label: "Light" },
  { id: "medium", label: "Medium" },
  { id: "strong", label: "Strong" },
];

const ALIAS_TO_ID: Record<string, MannerismCueId> = {
  sigh: "sigh",
  sighs: "sigh",
  chuckled: "chuckle",
  chuckle: "chuckle",
  chuckles: "chuckle",
  laugh: "laugh",
  laughs: "laugh",
  laughed: "laugh",
  laughter: "laugh",
  "soft laugh": "soft_laugh",
  soft_laugh: "soft_laugh",
  softlaugh: "soft_laugh",
  giggle: "soft_laugh",
  gasp: "gasp",
  gasps: "gasp",
  gasped: "gasp",
  "breath in": "breath_in",
  breath_in: "breath_in",
  inhale: "breath_in",
  "breath out": "breath_out",
  breath_out: "breath_out",
  exhale: "breath_out",
  whisper: "whisper",
  whispers: "whisper",
  whispered: "whisper",
  whispering: "whisper",
  pause: "pause",
  pauses: "pause",
  hesitate: "hesitate",
  hesitation: "hesitate",
  hesitant: "hesitate",
  scoff: "scoff",
  scoffs: "scoff",
  scoffed: "scoff",
  "nervous breath": "nervous_breath",
  nervous_breath: "nervous_breath",
};

const LABEL_BY_ID: Record<MannerismCueId, string> = Object.fromEntries(
  MANNERISM_CUE_OPTIONS.map((o) => [o.id, o.label]),
) as Record<MannerismCueId, string>;

const BRACKET_RE = /\[([^\]]+)\]/g;
const TAG_SHAPE_RE = /^[A-Za-z][A-Za-z0-9 _\-]{0,40}$/;

export function resolveMannerismId(raw: string): MannerismCueId | null {
  const key = String(raw || "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
  if (!key) return null;
  if (ALIAS_TO_ID[key]) return ALIAS_TO_ID[key];
  for (const prefix of ["reaction:", "mannerism:", "cue:", "action:"]) {
    if (key.startsWith(prefix)) return resolveMannerismId(key.slice(prefix.length));
  }
  return null;
}

export function makeMannerismCue(
  id: MannerismCueId,
  opts?: Partial<Pick<MannerismCue, "position" | "intensity" | "source">>,
): MannerismCue {
  return {
    id,
    label: LABEL_BY_ID[id] || id,
    position: opts?.position || "before",
    intensity: opts?.intensity || "medium",
    source: opts?.source || "structured",
    nativeSupport: false,
    approximationMode: ["whisper", "pause", "hesitate"].includes(id) ? "emo_text" : "vocal_event",
    approximationNote: ["whisper", "pause", "hesitate"].includes(id)
      ? "Delivery cue: approximated via local IndexTTS2 / QwenEmotion emo_text or structural pause."
      : "Discrete local vocal-event audio is generated and stitched into the take (not spoken cue words; not speaker-cloned).",
  };
}

export function normalizeMannerismCues(raw: unknown): MannerismCue[] {
  const list = Array.isArray(raw) ? raw : raw && typeof raw === "object" ? [raw] : [];
  const out: MannerismCue[] = [];
  const seen = new Set<string>();
  for (const item of list) {
    if (!item || typeof item !== "object") continue;
    const rec = item as Record<string, unknown>;
    const id = resolveMannerismId(String(rec.id || rec.cue || rec.label || ""));
    if (!id) continue;
    const position = String(rec.position || "before").toLowerCase();
    const pos: MannerismPosition =
      position.includes("during") || position === "mid" ? "during" : position.includes("after") ? "after" : "before";
    const intensityRaw = String(rec.intensity || "medium").toLowerCase();
    const intensity: MannerismIntensity =
      intensityRaw === "light" || intensityRaw === "low" || intensityRaw === "soft"
        ? "light"
        : intensityRaw === "strong" || intensityRaw === "high" || intensityRaw === "heavy"
          ? "strong"
          : "medium";
    const key = `${id}:${pos}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(makeMannerismCue(id, { position: pos, intensity, source: String(rec.source || "structured") }));
  }
  return out;
}

/** Strip recognized / tag-shaped brackets from dialogue for display preview of spoken text. */
export function extractSpokenDialogue(source: string): {
  spokenText: string;
  mannerismCues: MannerismCue[];
  notices: string[];
} {
  const text = source || "";
  const cues: MannerismCue[] = [];
  const notices: string[] = [];
  let spoken = "";
  let pos = 0;
  let match: RegExpExecArray | null;
  const re = new RegExp(BRACKET_RE.source, "g");
  while ((match = re.exec(text))) {
    spoken += text.slice(pos, match.index);
    const body = match[1] || "";
    let intensity: MannerismIntensity = "medium";
    let base = body;
    for (const sep of [":", "|", "/"]) {
      if (body.includes(sep)) {
        const [left, right] = body.split(sep);
        const knownLeft = resolveMannerismId(left || "");
        if (knownLeft && right) {
          base = left || "";
          const ir = right.trim().toLowerCase();
          intensity = ir === "light" || ir === "low" ? "light" : ir === "strong" || ir === "high" ? "strong" : "medium";
        }
        break;
      }
    }
    const cueId = resolveMannerismId(base);
    if (cueId) {
      const before = spoken.trim();
      const after = text.slice(match.index + match[0].length).trimStart();
      const position: MannerismPosition = !before ? "before" : !after || after.startsWith("\n") ? "after" : "during";
      cues.push(makeMannerismCue(cueId, { position, intensity, source: "bracket" }));
    } else if (TAG_SHAPE_RE.test(body.trim()) && body.trim().split(/\s+/).length <= 3) {
      notices.push(`Unsupported mannerism cue [${body.trim()}] was removed from spoken dialogue.`);
    } else {
      spoken += match[0];
    }
    pos = match.index + match[0].length;
  }
  spoken += text.slice(pos);
  spoken = spoken.replace(/[ \t]{2,}/g, " ").replace(/ *\n */g, "\n").trim();
  return { spokenText: spoken, mannerismCues: cues, notices };
}

export function mergeMannerismCues(a: MannerismCue[] | null | undefined, b: MannerismCue[] | null | undefined): MannerismCue[] {
  return normalizeMannerismCues([...(a || []), ...(b || [])]);
}
