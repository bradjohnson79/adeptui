import { apiUrl } from "../../runtime/apiBase";

export type LibraryThumbKind = "video" | "image" | "audio" | "music" | "sfx" | string;

export function libraryThumbKind(kind: LibraryThumbKind | undefined): "video" | "image" | "audio" {
  if (kind === "video") return "video";
  if (kind === "audio" || kind === "music" || kind === "sfx") return "audio";
  return "image";
}

/** Canonical project-scoped thumb. Audio never hits /thumb. */
export function libraryThumbUrl(
  projectId: string | null | undefined,
  assetId: string | null | undefined,
  kind: LibraryThumbKind | undefined,
): string | null {
  const pid = String(projectId || "").trim();
  const aid = String(assetId || "").trim();
  if (!pid || !aid) return null;
  if (libraryThumbKind(kind) === "audio") return null;
  return apiUrl(`/api/projects/${encodeURIComponent(pid)}/assets/${encodeURIComponent(aid)}/thumb?w=256`);
}
