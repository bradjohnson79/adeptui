export const PREVIEW_APPROVE_AS_KINDS = ["character", "environment", "prop", "scene_frame"] as const;

export type PreviewApproveAsKind = (typeof PREVIEW_APPROVE_AS_KINDS)[number];

export const PREVIEW_APPROVE_AS_OPTIONS: { kind: PreviewApproveAsKind; label: string }[] = [
  { kind: "character", label: "Character" },
  { kind: "environment", label: "Environment" },
  { kind: "prop", label: "Prop" },
  { kind: "scene_frame", label: "Scene Frame" },
];

export function canApproveLibraryImage(args: {
  showingLibrary: boolean;
  mediaKind?: "image" | "video" | "audio" | null;
  assetKind?: string | null;
  filename?: string | null;
}): boolean {
  if (!args.showingLibrary) return false;
  if (args.mediaKind === "audio" || args.mediaKind === "video") return false;
  const kind = String(args.assetKind || "").toLowerCase();
  const filename = String(args.filename || "");
  if (kind === "audio" || /\.(wav|mp3|ogg|m4a|aac|flac)(\?|$)/i.test(filename)) return false;
  if (kind === "video" || /\.(mp4|webm|mov)(\?|$)/i.test(filename)) return false;
  return kind === "" || kind === "image" || kind === "img" || kind === "still";
}

export function labelForApproveAsKind(kind: PreviewApproveAsKind): string {
  return PREVIEW_APPROVE_AS_OPTIONS.find((item) => item.kind === kind)?.label || "Character";
}
