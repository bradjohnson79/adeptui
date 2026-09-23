/** MAGI Command → finishing proposal (no production generation / inpaint). */

export type MagiCommandProposal = {
  kind: "image_edit" | "overlay" | "audio" | "color" | "render";
  operation: string;
  actionId: string;
  label: string;
  requiresMask: boolean;
  confidence: "high" | "medium" | "low";
  overlayOp?:
    | "overlay.proposeCreateText"
    | "overlay.proposeCreateLowerThird"
    | "overlay.proposeCreateShape"
    | "overlay.proposeUpdateStyle"
    | "overlay.proposeMove"
    | "overlay.proposeDelete"
    | "overlay.proposeApplyPreset";
  overlayPayload?: Record<string, unknown>;
};

export function proposeFromCommand(text: string): MagiCommandProposal | null {
  const t = text.trim().toLowerCase();
  if (!t) return null;

  if (/\b(re-?take|inpaint|mask\s*repair|timed\s*prompt)\b/.test(t)) {
    return null;
  }

  if (/\b(lower\s*third|name\s*plate|identifier)\b/.test(t)) {
    const primary = (text.match(/identifying\s+([A-Za-z][\w\s-]{0,40})/i) || [])[1]?.trim() || "NAME";
    const secondary =
      (text.match(/as\s+([A-Za-z][\w\s,]{0,60})/i) || [])[1]?.trim() || "Role";
    return {
      kind: "overlay",
      operation: "overlay.createLowerThird",
      actionId: "overlay_lower_third",
      label: "Add Lower Third",
      requiresMask: false,
      confidence: "high",
      overlayOp: "overlay.proposeCreateLowerThird",
      overlayPayload: { primary, secondary },
    };
  }
  if (/\b(add|create|place)\b.*\b(title|text|caption|watermark|quote)\b/.test(t) || /\btitle\s+reading\b/.test(t)) {
    const quoted = text.match(/[“"]([^”"]+)[”"]/) || text.match(/'([^']+)'/);
    const content = quoted?.[1] || "Title";
    return {
      kind: "overlay",
      operation: "overlay.createText",
      actionId: "overlay_text",
      label: "Add Text Overlay",
      requiresMask: false,
      confidence: "high",
      overlayOp: "overlay.proposeCreateText",
      overlayPayload: {
        text: content,
        background: /\b(translucent|background|black)\b/.test(t),
        align: /\bcenter(ed)?\b/.test(t) ? "center" : "left",
      },
    };
  }
  if (/\b(add|create)\b.*\b(shape|rectangle|bar)\b/.test(t)) {
    return {
      kind: "overlay",
      operation: "overlay.createShape",
      actionId: "overlay_shape",
      label: "Add Shape",
      requiresMask: false,
      confidence: "medium",
      overlayOp: "overlay.proposeCreateShape",
      overlayPayload: { shape: "rectangle" },
    };
  }

  if (/\b(delete|remove|clear)\b/.test(t) && /\b(overlay|text|caption|title|lower\s*third|shape|selected)\b/.test(t)) {
    return {
      kind: "overlay",
      operation: "overlay.delete",
      actionId: "overlay_delete",
      label: "Delete Selected Overlay",
      requiresMask: false,
      confidence: "high",
      overlayOp: "overlay.proposeDelete",
      overlayPayload: {},
    };
  }
  if (/\b(no music|without music|music:?\s*none)\b/.test(t)) {
    return {
      kind: "audio",
      operation: "magi.music.none",
      actionId: "music_none",
      label: "No Music",
      requiresMask: false,
      confidence: "high",
    };
  }
  if (/\b(keep original audio|original audio untouched|do not (change|touch) (the )?audio)\b/.test(t)) {
    return {
      kind: "audio",
      operation: "magi.audio.keep_original",
      actionId: "keep_audio",
      label: "Keep Original Audio",
      requiresMask: false,
      confidence: "high",
    };
  }
  if (/\bprofessionally finish\b/.test(t) || /\bfinish this scene\b/.test(t)) {
    return {
      kind: "render",
      operation: "magi.propose_finish",
      actionId: "propose_finish",
      label: "Finish Scene",
      requiresMask: false,
      confidence: "high",
    };
  }
  if (/\b(upscale|enhance resolution|2k|4k|2x)\b/.test(t)) {
    return {
      kind: "image_edit",
      operation: "image.upscale",
      actionId: "upscale",
      label: "Upscale",
      requiresMask: false,
      confidence: "high",
    };
  }
  if (/\b(grade|color|exposure|contrast|saturation|cinematic|look)\b/.test(t)) {
    return {
      kind: "color",
      operation: "magi.color.apply",
      actionId: "color_grade",
      label: "Color Grade",
      requiresMask: false,
      confidence: "high",
    };
  }
  if (/\b(music|soundtrack|score|ambience|sfx|sound\s*mix)\b/.test(t)) {
    return {
      kind: "audio",
      operation: "magi.audio.generate",
      actionId: "audio_finish",
      label: "Audio Finish",
      requiresMask: false,
      confidence: "medium",
    };
  }
  if (/\b(render|export|deliver|finish|publish)\b/.test(t)) {
    return {
      kind: "render",
      operation: "magi.render",
      actionId: "render",
      label: "Final Render",
      requiresMask: false,
      confidence: "medium",
    };
  }
  return null;
}
