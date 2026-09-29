/**
 * Canonical authority for Timeline Audio / SFX / Music / Ambience /
 * Performance Re-Take (Lip Sync) TITLE + DESCRIPTION + clip-face LABEL.
 *
 * One resolver for Co-Director place paths and Timeline UI (clip face + Inspector).
 * Fallback order is STRICT and never fabricates creative detail:
 *   metadata → job → prompt → asset → filename
 * Unknown → null/empty.
 */

export type MediaClipKind =
  | "audio"
  | "sfx"
  | "music"
  | "ambience"
  | "performance_retake"
  | "lipsync";

export type MediaLabelTierource =
  | "metadata"
  | "job"
  | "prompt"
  | "asset"
  | "filename"
  | "none";

export type MediaClipLabelSources = {
  title: MediaLabelTierource;
  description: MediaLabelTierource;
};

export type MediaClipLabelIds = {
  retakeId?: string | null;
  voiceAssetId?: string | null;
  audioAssetId?: string | null;
  assetId?: string | null;
};

export type MediaClipLabelResult = {
  /** Full title for Inspector (and persistence when written). */
  title: string | null;
  /** Full description for Inspector (ids + dialogue when known). */
  description: string | null;
  /** Truncated clip-face string derived from title (may be ""). */
  label: string;
  sources: MediaClipLabelSources;
  ids: MediaClipLabelIds;
};

export type MediaClipLabelClipFields = {
  title?: string | null;
  description?: string | null;
  label?: string | null;
  line?: string | null;
  character_name?: string | null;
  audio_asset_id?: string | null;
  asset_id?: string | null;
  retake_id?: string | null;
  retakeId?: string | null;
  voice_asset_id?: string | null;
  voiceAssetId?: string | null;
  id?: string | null;
};

export type MediaClipLabelAssetFields = {
  tag?: string | null;
  filename?: string | null;
  prompt_meta?: string | null;
  labels?: string[] | null;
};

export type MediaClipLabelPromptContext = {
  prompts?: string[] | null;
  promptSegments?: Array<{ text?: string | null; start?: number; length?: number }> | null;
  clipStart?: number | null;
  clipLength?: number | null;
};

export type MediaClipLabelInput = {
  kind: MediaClipKind;
  clip?: MediaClipLabelClipFields | null;
  job?: Record<string, unknown> | null;
  asset?: MediaClipLabelAssetFields | null;
  promptContext?: MediaClipLabelPromptContext | null;
  /** Clip-face truncation length (ellipsis). Default 36. */
  maxLabelChars?: number;
};

const DEFAULT_MAX_LABEL = 36;

const GENERIC_LABELS = new Set(
  [
    "audio",
    "sfx",
    "music",
    "ambience",
    "lip sync clip",
    "lipsync clip",
    "timeline audio",
    "music cue",
    "ambience bed",
  ].map((s) => s.toLowerCase()),
);

function trimStr(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function isGenericLabel(label: string): boolean {
  const t = label.trim();
  if (!t) return true;
  if (GENERIC_LABELS.has(t.toLowerCase())) return true;
  // "{Name} line" with no real dialogue is a placeholder, not a title.
  if (/^.+\s+line$/i.test(t)) return true;
  return false;
}

/** Truncate for clip face; full string unchanged when short enough. */
export function truncateClipFaceLabel(text: string, maxChars = DEFAULT_MAX_LABEL): string {
  const t = (text || "").trim();
  if (!t) return "";
  if (maxChars < 4) return t.slice(0, Math.max(0, maxChars));
  if (t.length <= maxChars) return t;
  return `${t.slice(0, maxChars - 1).trimEnd()}…`;
}

/**
 * Extract speaker → dialogue from prompt text when clearly present.
 * Accepts patterns like: Name says, "line."  /  Name: "line"
 * Never invents lines.
 */
export function extractQuotedDialogueFromPrompt(
  prompt: string,
  speakerHint?: string | null,
): Array<{ speaker: string; line: string }> {
  const text = trimStr(prompt);
  if (!text) return [];
  const out: Array<{ speaker: string; line: string }> = [];
  const patterns = [
    /([A-Za-z][A-Za-z0-9_ '-]{0,40}?)\s+says?,?\s*[\u201c\u201d"](.+?)[\u201c\u201d"]/giu,
    /([A-Za-z][A-Za-z0-9_ '-]{0,40}?)\s*:\s*[\u201c\u201d"](.+?)[\u201c\u201d"]/giu,
  ];
  for (const re of patterns) {
    re.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = re.exec(text)) !== null) {
      const speaker = trimStr(m[1]);
      const line = trimStr(m[2]);
      if (!speaker || !line) continue;
      if (out.some((x) => x.speaker === speaker && x.line === line)) continue;
      out.push({ speaker, line });
    }
  }
  const hint = trimStr(speakerHint);
  if (hint) {
    const matched = out.filter((x) => x.speaker.toLowerCase() === hint.toLowerCase());
    if (matched.length) return matched;
  }
  return out;
}

function promptsForClip(ctx: MediaClipLabelPromptContext | null | undefined): string[] {
  if (!ctx) return [];
  const collected: string[] = [];
  for (const p of ctx.prompts || []) {
    const t = trimStr(p);
    if (t) collected.push(t);
  }
  const segs = ctx.promptSegments || [];
  const clipStart = ctx.clipStart;
  const clipLength = ctx.clipLength;
  const hasWindow =
    typeof clipStart === "number" &&
    typeof clipLength === "number" &&
    Number.isFinite(clipStart) &&
    Number.isFinite(clipLength);
  for (const seg of segs) {
    const text = trimStr(seg?.text);
    if (!text) continue;
    if (hasWindow) {
      const s = Number(seg.start ?? 0);
      const l = Number(seg.length ?? 0);
      const clipEnd = (clipStart as number) + (clipLength as number);
      const segEnd = s + l;
      // Overlap or no timing on segment → include
      if (l > 0 && !(s < clipEnd && segEnd > (clipStart as number))) continue;
    }
    collected.push(text);
  }
  return collected;
}

function firstNonEmpty(...values: unknown[]): string | null {
  for (const v of values) {
    const t = trimStr(v);
    if (t) return t;
  }
  return null;
}

function filenameStem(filename: string | null | undefined): string | null {
  const f = trimStr(filename);
  if (!f) return null;
  const base = f.split(/[/\\]/).pop() || f;
  const stem = base.replace(/\.[^.]+$/, "").trim();
  return stem || null;
}

function jobString(job: Record<string, unknown> | null | undefined, keys: string[]): string | null {
  if (!job) return null;
  for (const key of keys) {
    const v = job[key];
    if (typeof v === "string" && v.trim()) return v.trim();
    if (v && typeof v === "object" && !Array.isArray(v)) {
      const nested = v as Record<string, unknown>;
      for (const nk of ["title", "description", "label", "line", "prompt"]) {
        const nv = nested[nk];
        if (typeof nv === "string" && nv.trim()) return nv.trim();
      }
    }
  }
  return null;
}

function isRetakeKind(kind: MediaClipKind): boolean {
  return kind === "performance_retake" || kind === "lipsync";
}

function buildRetakeDescription(line: string | null, ids: MediaClipLabelIds): string | null {
  const parts: string[] = [];
  if (line) parts.push(line);
  const idBits: string[] = [];
  if (ids.retakeId) idBits.push(`retakeId=${ids.retakeId}`);
  if (ids.voiceAssetId) idBits.push(`voiceAssetId=${ids.voiceAssetId}`);
  if (ids.audioAssetId) idBits.push(`audio_asset_id=${ids.audioAssetId}`);
  if (ids.assetId && ids.assetId !== ids.audioAssetId) idBits.push(`assetId=${ids.assetId}`);
  if (idBits.length) parts.push(idBits.join("; "));
  if (!parts.length) return null;
  return parts.join("\n");
}

/**
 * Resolve title / description / truncated label for a media clip.
 * Never fabricates dialogue or creative detail.
 */
export function resolveMediaClipLabels(input: MediaClipLabelInput): MediaClipLabelResult {
  const kind = input.kind;
  const clip = input.clip || {};
  const maxChars = input.maxLabelChars ?? DEFAULT_MAX_LABEL;
  const ids: MediaClipLabelIds = {
    retakeId: firstNonEmpty(clip.retakeId, clip.retake_id, isRetakeKind(kind) ? clip.id : null),
    voiceAssetId: firstNonEmpty(clip.voiceAssetId, clip.voice_asset_id),
    audioAssetId: firstNonEmpty(clip.audio_asset_id),
    assetId: firstNonEmpty(clip.asset_id, input.asset ? undefined : null),
  };
  if (!ids.assetId && input.asset) {
    // asset id may only live on clip
  }

  let title: string | null = null;
  let description: string | null = null;
  let titleSource: MediaLabelTierource = "none";
  let descriptionSource: MediaLabelTierource = "none";

  const metaTitle = firstNonEmpty(clip.title);
  const metaDescription = firstNonEmpty(clip.description);
  const metaLine = firstNonEmpty(clip.line);
  const metaLabel = firstNonEmpty(clip.label);
  const speaker = firstNonEmpty(clip.character_name);

  // ── 1. metadata ──────────────────────────────────────────────────────────
  if (isRetakeKind(kind)) {
    if (speaker && metaLine) {
      title = `${speaker}: ${metaLine}`;
      titleSource = "metadata";
      description = buildRetakeDescription(metaLine, ids);
      descriptionSource = "metadata";
    } else if (metaTitle) {
      title = metaTitle;
      titleSource = "metadata";
      description = metaDescription || buildRetakeDescription(metaLine, ids);
      descriptionSource = metaDescription ? "metadata" : description ? "metadata" : "none";
    } else if (metaLabel && !isGenericLabel(metaLabel) && metaLine) {
      title = speaker ? `${speaker}: ${metaLine}` : metaLabel;
      titleSource = "metadata";
      description = buildRetakeDescription(metaLine, ids);
      descriptionSource = "metadata";
    }
  } else {
    if (metaTitle) {
      title = metaTitle;
      titleSource = "metadata";
    } else if (metaLabel && !isGenericLabel(metaLabel)) {
      title = metaLabel;
      titleSource = "metadata";
    }
    if (metaDescription) {
      description = metaDescription;
      descriptionSource = "metadata";
    }
  }

  // ── 2. job metadata ──────────────────────────────────────────────────────
  if (!title) {
    const jobTitle = jobString(input.job, ["title", "label", "clipLabel", "name"]);
    if (jobTitle && !isGenericLabel(jobTitle)) {
      title = jobTitle;
      titleSource = "job";
    }
  }
  if (!description) {
    const jobDesc = jobString(input.job, ["description", "line", "dialogue", "prompt"]);
    if (jobDesc) {
      description = jobDesc;
      descriptionSource = "job";
    }
  }
  if (isRetakeKind(kind) && !title) {
    const jobLine = jobString(input.job, ["line", "dialogue"]);
    const jobSpeaker = jobString(input.job, ["character_name", "speaker", "characterName"]) || speaker;
    if (jobSpeaker && jobLine) {
      title = `${jobSpeaker}: ${jobLine}`;
      titleSource = "job";
      if (!description) {
        description = buildRetakeDescription(jobLine, ids);
        descriptionSource = "job";
      }
    }
  }

  // ── 3. prompt-derived (speaker + quoted dialogue only) ───────────────────
  if (isRetakeKind(kind) && (!title || !(metaLine || jobString(input.job, ["line", "dialogue"])))) {
    const promptTexts = promptsForClip(input.promptContext);
    let found: { speaker: string; line: string } | null = null;
    for (const p of promptTexts) {
      const hits = extractQuotedDialogueFromPrompt(p, speaker);
      if (hits.length) {
        found = hits[0];
        break;
      }
    }
    if (found) {
      // Only overwrite empty/placeholder titles; never invent when metadata already had real title+line
      if (!title || isGenericLabel(metaLabel || "") || !metaLine) {
        title = `${found.speaker}: ${found.line}`;
        titleSource = "prompt";
      }
      if (!description || !metaLine) {
        description = buildRetakeDescription(found.line, ids);
        descriptionSource = "prompt";
      }
    }
  }

  // ── 4. asset ─────────────────────────────────────────────────────────────
  if (!title && input.asset) {
    const fromAsset = firstNonEmpty(
      input.asset.tag,
      (input.asset.labels || []).find((x) => trimStr(x)),
      input.asset.prompt_meta,
    );
    if (fromAsset && !isGenericLabel(fromAsset)) {
      title = fromAsset;
      titleSource = "asset";
    }
  }
  if (!description && input.asset) {
    const d = firstNonEmpty(input.asset.prompt_meta);
    if (d && d !== title) {
      description = d;
      descriptionSource = "asset";
    }
  }

  // ── 5. filename stem ─────────────────────────────────────────────────────
  if (!title && input.asset) {
    const stem = filenameStem(input.asset.filename);
    if (stem) {
      title = stem;
      titleSource = "filename";
    }
  }

  // Retake description should still carry ids even when line unknown
  if (isRetakeKind(kind) && !description) {
    const idOnly = buildRetakeDescription(null, ids);
    if (idOnly) {
      description = idOnly;
      descriptionSource = descriptionSource === "none" ? "metadata" : descriptionSource;
    }
  }

  const label = truncateClipFaceLabel(title || "", maxChars);
  return {
    title,
    description,
    label,
    sources: { title: titleSource, description: descriptionSource },
    ids,
  };
}

/** Apply resolved fields onto a clip-shaped object (does not invent writes beyond title/description/label/line). */
export function applyResolvedMediaClipLabels<T extends Record<string, unknown>>(
  clip: T,
  resolved: MediaClipLabelResult,
  opts?: { setLineFromTitle?: boolean; speaker?: string | null; persistTruncatedLabel?: boolean },
): T & { title: string | null; description: string | null; label: string } {
  const persistedLabel = opts?.persistTruncatedLabel
    ? resolved.label || trimStr(clip.label) || ""
    : trimStr(resolved.title) || trimStr(clip.label) || resolved.label || "";
  const next: Record<string, unknown> = {
    ...clip,
    title: resolved.title,
    description: resolved.description,
    label: persistedLabel,
  };
  if (opts?.setLineFromTitle && resolved.title) {
    const speaker = trimStr(opts.speaker);
    let line = "";
    if (speaker && resolved.title.startsWith(`${speaker}:`)) {
      line = resolved.title.slice(speaker.length + 1).trim();
    } else {
      const idx = resolved.title.indexOf(":");
      if (idx > 0) line = resolved.title.slice(idx + 1).trim();
    }
    if (line && !trimStr(clip.line as string)) {
      next.line = line;
    }
  }
  return next as T & { title: string | null; description: string | null; label: string };
}
