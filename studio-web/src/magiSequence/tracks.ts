import {
  DEFAULT_TRACK_BLUEPRINT,
  PRIMARY_MAGI_TRACK_KINDS,
  type MagiClip,
  type MagiObjectsSlot,
  type MagiSequenceDocument,
  type MagiTrack,
  type MagiTrackKind,
} from "./types";

const PRIMARY_KIND_SET = new Set<string>([...PRIMARY_MAGI_TRACK_KINDS, "graphics"]);

const OBJECTS_LABEL_ALIASES = new Set([
  "GRAPHICS",
  "TEXT",
  "T1",
  "GFX",
  "OBJECTS",
  "OBJECTS 1",
  "OBJECTS 2",
]);

function uid(prefix: string): string {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

export function isPrimaryMagiTrackKind(kind: MagiTrackKind | string): boolean {
  return PRIMARY_KIND_SET.has(kind);
}

export function isObjectsTrackKind(kind: MagiTrackKind | string | undefined): boolean {
  return kind === "objects" || kind === "graphics";
}

/** Header control for a MAGI track. Audio stems mute. Picture and Objects show or hide. */
export function magiTrackHeaderControl(kind: MagiTrackKind | string | undefined): "mute" | "eye" | null {
  if (kind === "audio" || kind === "music" || kind === "sfx") return "mute";
  if (kind === "video" || kind === "image" || kind === "objects" || kind === "graphics") return "eye";
  return null;
}

export function objectsTrackLabel(slot: MagiObjectsSlot): string {
  return slot === 2 ? "OBJECTS 2" : "OBJECTS 1";
}

export function objectsSlotOf(track: MagiTrack | undefined | null): MagiObjectsSlot | null {
  if (!track) return null;
  if (!isObjectsTrackKind(track.kind) && !OBJECTS_LABEL_ALIASES.has(track.label.toUpperCase())) {
    return null;
  }
  if (track.objectsSlot === 1 || track.objectsSlot === 2) return track.objectsSlot;
  const label = track.label.toUpperCase();
  if (label.includes("2")) return 2;
  return 1;
}

export function isObjectsCandidate(track: MagiTrack): boolean {
  return isObjectsTrackKind(track.kind) || OBJECTS_LABEL_ALIASES.has(track.label.toUpperCase());
}

export function findObjectsTrack(tracks: MagiTrack[], slot: MagiObjectsSlot): MagiTrack | undefined {
  return tracks.find((track) => objectsSlotOf(track) === slot);
}

export function createObjectsTrack(slot: MagiObjectsSlot, order: number, id?: string): MagiTrack {
  return {
    id: id || uid(`trk_objects_${slot}`),
    kind: "objects",
    label: objectsTrackLabel(slot),
    order,
    objectsSlot: slot,
  };
}

export function normalizeObjectsTrack(track: MagiTrack, slot: MagiObjectsSlot): MagiTrack {
  return {
    ...track,
    kind: "objects",
    label: objectsTrackLabel(slot),
    objectsSlot: slot,
  };
}

export function canAddObjectsTrack(tracks: MagiTrack[]): boolean {
  return !findObjectsTrack(tracks, 2);
}

export function addOptionalObjectsTrack(doc: MagiSequenceDocument): MagiSequenceDocument {
  if (findObjectsTrack(doc.tracks, 2)) return doc;
  const o2 = createObjectsTrack(2, 0);
  const tracks = [o2, ...doc.tracks.map((track, index) => ({ ...track, order: index + 1 }))];
  return { ...doc, tracks };
}

export function removeOptionalObjectsTrack(doc: MagiSequenceDocument): MagiSequenceDocument {
  const tracks = doc.tracks
    .filter((track) => objectsSlotOf(track) !== 2)
    .map((track, index) => ({ ...track, order: index }));
  if (tracks.length === doc.tracks.length) return doc;
  return { ...doc, tracks };
}

/** Frozen visible stack: OBJECTS 2 (optional), OBJECTS 1, VIDEO, AUDIO, MUSIC, SFX. */
export function visibleMagiTracks(tracks: MagiTrack[]): MagiTrack[] {
  const out: MagiTrack[] = [];
  const o2 = findObjectsTrack(tracks, 2);
  const o1 = findObjectsTrack(tracks, 1);
  if (o2) out.push(normalizeObjectsTrack(o2, 2));
  if (o1) out.push(normalizeObjectsTrack(o1, 1));
  for (const kind of ["video", "audio", "music", "sfx"] as const) {
    const found = tracks.find((track) => track.kind === kind);
    if (found) out.push({ ...found, label: kind.toUpperCase() });
  }
  return out;
}

function pickCanonicalTrack(
  tracks: MagiTrack[],
  kind: MagiTrackKind,
  aliases: string[],
): MagiTrack | undefined {
  return (
    tracks.find((track) => track.kind === kind) ||
    tracks.find((track) => aliases.includes(track.label.toUpperCase()))
  );
}

function resolveClipKind(
  clip: MagiClip,
  track: MagiTrack | undefined,
  musicAssetId?: string,
  sfxAssetId?: string,
): MagiTrackKind | "keep" {
  if (clip.assetId && musicAssetId && clip.assetId === musicAssetId) return "music";
  if (clip.assetId && sfxAssetId && clip.assetId === sfxAssetId) return "sfx";
  const kind = track?.kind;
  if (kind === "music") return "music";
  if (kind === "sfx" || kind === "fx") return "sfx";
  if (kind === "audio") return "audio";
  if (kind === "video" || kind === "image") return "video";
  if (isObjectsTrackKind(kind) || kind === "text" || kind === "mask" || kind === "adjustment") return "keep";
  return "video";
}

export function migrateToPostProductionTracks(doc: MagiSequenceDocument): MagiSequenceDocument {
  const existing = [...doc.tracks];
  const candidates = existing.filter(isObjectsCandidate);
  const slot2Src =
    candidates.find((track) => objectsSlotOf(track) === 2) ||
    (candidates.length > 1 ? candidates[1] : undefined);
  const slot1Src = candidates.find((track) => !slot2Src || track.id !== slot2Src.id);

  const objects1 = normalizeObjectsTrack(
    slot1Src || {
      id: uid("trk_objects_1"),
      kind: "objects",
      label: "OBJECTS 1",
      order: 0,
    },
    1,
  );
  const objects2 = slot2Src ? normalizeObjectsTrack(slot2Src, 2) : undefined;

  const video =
    pickCanonicalTrack(existing, "video", ["VIDEO", "V1"]) || {
      id: uid("trk_video"),
      kind: "video" as const,
      label: "VIDEO",
      order: 0,
    };
  const audio =
    pickCanonicalTrack(existing, "audio", ["AUDIO", "A1"]) || {
      id: uid("trk_audio"),
      kind: "audio" as const,
      label: "AUDIO",
      order: 0,
    };
  const music =
    pickCanonicalTrack(existing, "music", ["MUSIC"]) || {
      id: uid("trk_music"),
      kind: "music" as const,
      label: "MUSIC",
      order: 0,
    };
  const sfx =
    pickCanonicalTrack(existing, "sfx", ["SFX"]) ||
    existing.find((track) => track.kind === "fx" && track.label.toUpperCase() === "FX") || {
      id: uid("trk_sfx"),
      kind: "sfx" as const,
      label: "SFX",
      order: 0,
    };

  const canonical: MagiTrack[] = [];
  let order = 0;
  if (objects2) canonical.push({ ...objects2, order: order++ });
  canonical.push({ ...objects1, order: order++ });
  canonical.push({ ...video, kind: "video", label: "VIDEO", order: order++ });
  canonical.push({ ...audio, kind: "audio", label: "AUDIO", order: order++ });
  canonical.push({ ...music, kind: "music", label: "MUSIC", order: order++ });
  canonical.push({ ...sfx, kind: "sfx", label: "SFX", order: order++ });

  const idByKind: Record<"video" | "audio" | "music" | "sfx", string> = {
    video: video.id,
    audio: audio.id,
    music: music.id,
    sfx: sfx.id,
  };

  const musicAssetId = doc.finishing?.audio?.musicAssetId;
  const sfxAssetId = doc.finishing?.audio?.sfxAssetId;
  const trackById = new Map(existing.map((track) => [track.id, track]));

  const clips = doc.clips.map((clip) => {
    const nextKind = resolveClipKind(clip, trackById.get(clip.trackId), musicAssetId, sfxAssetId);
    if (nextKind === "keep") return clip;
    return { ...clip, trackId: idByKind[nextKind] };
  });

  const canonicalIds = new Set(canonical.map((track) => track.id));
  const leftovers = existing
    .filter((track) => !canonicalIds.has(track.id) && !isObjectsCandidate(track))
    .map((track, index) => ({ ...track, order: order + index }));
  const tracks = [...canonical, ...leftovers];

  const sameTracks =
    doc.tracks.length === tracks.length &&
    doc.tracks.every((track, index) => {
      const next = tracks[index];
      return (
        track.id === next.id &&
        track.kind === next.kind &&
        track.label === next.label &&
        track.order === next.order &&
        track.objectsSlot === next.objectsSlot
      );
    });
  const sameClips = doc.clips.every((clip, index) => clip.trackId === clips[index]?.trackId);
  if (sameTracks && sameClips) return doc;

  return { ...doc, tracks, clips };
}

export function createCanonicalTracks(): MagiTrack[] {
  return DEFAULT_TRACK_BLUEPRINT.map((item, index) => ({
    id: uid(item.objectsSlot ? `trk_objects_${item.objectsSlot}` : `trk_${item.kind}`),
    kind: item.kind,
    label: item.label,
    order: index,
    objectsSlot: item.objectsSlot,
  }));
}
