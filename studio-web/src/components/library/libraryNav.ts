/** Library navigation shown to creators. Taxonomy owners stay in the API. */

export type LibraryTypeNav =
  | "all"
  | "images"
  | "video"
  | "audio"
  | "characters"
  | "props"
  | "scenes"
  | "environments"
  | "storyboards"
  | "scripts"
  | "scene_image";

/** Folders with no current placement owner, or deferred 3D / preset shelves. */
const HIDDEN_LIBRARY_KEYS = new Set([
  "audio.music_track",
  "audio.music_loop",
  "audio.music_stem",
  "audio.sound_effect",
  "audio.transition",
  "audio.room_tone",
]);

const TYPE_ROOT: Partial<Record<LibraryTypeNav, string>> = {
  video: "video",
  audio: "audio",
  characters: "characters",
  props: "props",
  scenes: "scenes",
  environments: "scenes",
  storyboards: "storyboards",
  scripts: "scripts",
  scene_image: "scenes",
};

export function libraryFolderVisible(systemKey?: string, displayName?: string): boolean {
  const key = String(systemKey || "");
  const name = String(displayName || "");
  if (name.startsWith("3D (Coming")) return false;
  if (!key) return true;
  if (key === "templates_presets" || key.startsWith("templates_presets.")) return false;
  if (key === "three_d" || key.startsWith("three_d.") || key.endsWith(".three_d")) return false;
  return !HIDDEN_LIBRARY_KEYS.has(key);
}

export type LibraryFolderNode = {
  folderId?: string;
  systemKey?: string;
  displayName?: string;
  children?: LibraryFolderNode[];
};

export function sidebarFoldersForType(folders: LibraryFolderNode[], type: LibraryTypeNav): LibraryFolderNode[] {
  const visible = folders
    .filter((folder) => libraryFolderVisible(folder.systemKey, folder.displayName))
    .map((folder) => ({
      ...folder,
      children: (folder.children || []).filter((child) => libraryFolderVisible(child.systemKey, child.displayName)),
    }));
  if (type === "images") {
    return visible.filter((folder) => folder.systemKey !== "video" && folder.systemKey !== "audio");
  }
  const root = TYPE_ROOT[type];
  if (!root) return visible;
  return visible.filter((folder) => folder.systemKey === root);
}
