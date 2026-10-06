import { normalizeTimelineMediaKind } from "../../timelineMediaTypes";

/** Infer the Library asset kind from a user-picked file. */
export function inferLibraryUploadKind(file: File): "image" | "video" | "audio" | "document" {
  const mime = (file.type || "").toLowerCase();
  if (mime.startsWith("image/")) return "image";
  if (mime.startsWith("video/")) return "video";
  if (mime.startsWith("audio/")) return "audio";
  const fromName = normalizeTimelineMediaKind(null, file.name);
  return fromName ?? "document";
}

export function libraryUploadTag(file: File): string {
  const stem = file.name.replace(/\.[^.]+$/, "").replace(/[^A-Za-z0-9._-]+/g, "-").replace(/^[._-]+|[._-]+$/g, "");
  return (stem || "upload").slice(0, 64);
}
