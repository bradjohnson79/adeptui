/** One MAGI Final Render title: library label and file stem. */

const INVALID_NAME = /[<>:"/\\|?*\u0000-\u001f]/;
const RESERVED = new Set([
  "CON",
  "PRN",
  "AUX",
  "NUL",
  "COM1",
  "COM2",
  "COM3",
  "COM4",
  "COM5",
  "COM6",
  "COM7",
  "COM8",
  "COM9",
  "LPT1",
  "LPT2",
  "LPT3",
  "LPT4",
  "LPT5",
  "LPT6",
  "LPT7",
  "LPT8",
  "LPT9",
]);

/** Matches the asset tag column so the library can show the whole title. */
export const FINAL_VIDEO_NAME_MAX = 64;

export const FINAL_VIDEO_NAME_CONFLICT = "A file with this name already exists. Choose another name.";
export const FINAL_VIDEO_NAME_EMPTY = "Enter a final video name.";
export const FINAL_VIDEO_NAME_INVALID = "That name uses a character a video file cannot keep.";

export type FinalVideoName = {
  title: string;
  filename: string;
};

type NamedRow = { tag?: string | null; filename?: string | null };

export function suggestedFinalVideoName(sceneName?: string | null, projectName?: string | null): string {
  const base = String(sceneName || projectName || "Scene").trim() || "Scene";
  if (/\bfinal$/i.test(base)) return base.slice(0, FINAL_VIDEO_NAME_MAX);
  const named = `${base} Final`;
  return named.length <= FINAL_VIDEO_NAME_MAX ? named : base.slice(0, FINAL_VIDEO_NAME_MAX);
}

export function normalizeFinalVideoName(raw: string): FinalVideoName | null {
  let title = String(raw || "").trim();
  while (/\.mp4$/i.test(title)) title = title.slice(0, -4).trim();
  if (!title || title === "." || title === "..") return null;
  if (INVALID_NAME.test(title) || title.endsWith(".") || title.endsWith(" ")) return null;
  if (title.length > FINAL_VIDEO_NAME_MAX) return null;
  const reserved = title.split(".")[0]?.toUpperCase() || "";
  if (RESERVED.has(reserved)) return null;
  return { title, filename: `${title}.mp4` };
}

export function finalVideoNameTaken(name: FinalVideoName, assets: NamedRow[]): boolean {
  const title = name.title.toLowerCase();
  const filename = name.filename.toLowerCase();
  return assets.some((asset) => {
    const tag = String(asset.tag || "").trim().toLowerCase();
    const existing = String(asset.filename || "").trim().toLowerCase();
    const stem = existing.endsWith(".mp4") ? existing.slice(0, -4) : existing;
    return tag === title || existing === filename || stem === title;
  });
}

/** Null when Confirm may start. Otherwise the sentence to show beside the field. */
export function finalVideoNameMessage(raw: string, assets: NamedRow[]): string | null {
  const trimmed = String(raw || "").trim();
  if (!trimmed) return FINAL_VIDEO_NAME_EMPTY;
  const name = normalizeFinalVideoName(raw);
  if (!name) {
    const withoutExt = trimmed.replace(/(?:\.mp4)+$/i, "").trim();
    if (!withoutExt) return FINAL_VIDEO_NAME_EMPTY;
    if (withoutExt.length > FINAL_VIDEO_NAME_MAX) return "Use a shorter name.";
    return FINAL_VIDEO_NAME_INVALID;
  }
  if (finalVideoNameTaken(name, assets)) return FINAL_VIDEO_NAME_CONFLICT;
  return null;
}
