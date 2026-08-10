/** MAGI Command → operation / overlay proposal (no execution). */

export type MagiCommandProposal = {
  kind: "image_edit" | "overlay";
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
  if (/\b(remove|erase|delete|inpaint)\b/.test(t) && /\b(object|person|people|background|thing)\b/.test(t)) {
    return {
      kind: "image_edit",
      operation: "image.object_remove",
      actionId: "object_remove",
      label: "Remove Object / Inpaint",
      requiresMask: true,
      confidence: "high",
    };
  }
  if (/\binpaint\b/.test(t)) {
    return {
      kind: "image_edit",
      operation: "image.inpaint",
      actionId: "inpaint",
      label: "Inpaint",
      requiresMask: true,
      confidence: "high",
    };
  }
  if (/\b(outpaint|extend|expand|canvas)\b/.test(t)) {
    return {
      kind: "image_edit",
      operation: "image.outpaint",
      actionId: "outpaint",
      label: "Outpaint",
      requiresMask: false,
      confidence: "high",
    };
  }
  if (/\b(upscale|enhance resolution|2x|4k)\b/.test(t)) {
    return {
      kind: "image_edit",
      operation: "image.upscale",
      actionId: "upscale",
      label: "Upscale",
      requiresMask: false,
      confidence: "high",
    };
  }
  if (/\b(reference|style|look like)\b/.test(t)) {
    return {
      kind: "image_edit",
      operation: "image.reference_edit",
      actionId: "reference_edit",
      label: "Reference Edit",
      requiresMask: false,
      confidence: "medium",
    };
  }
  if (/\b(relight|lighting|moonlight)\b/.test(t)) {
    return {
      kind: "image_edit",
      operation: "image.relight",
      actionId: "relight",
      label: "Relight",
      requiresMask: false,
      confidence: "medium",
    };
  }
  if (/\b(face|hands|repair)\b/.test(t)) {
    return {
      kind: "image_edit",
      operation: "image.face_restore",
      actionId: "face_restore",
      label: "Repair Face",
      requiresMask: false,
      confidence: "medium",
    };
  }
  return {
    kind: "image_edit",
    operation: "image.inpaint",
    actionId: "inpaint",
    label: "Inpaint (default proposal)",
    requiresMask: true,
    confidence: "low",
  };
}
