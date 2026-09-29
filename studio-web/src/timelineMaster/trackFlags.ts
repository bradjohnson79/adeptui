/** Track hide / lock / mute / solo — persisted on DirectorTimeline.track_flags. */

export type TrackControl = "eye" | "lock" | "mute" | "solo";

export type TrackFlagState = {
  hidden?: boolean;
  locked?: boolean;
  muted?: boolean;
  solo?: boolean;
};

export type TrackFlagMap = Record<string, TrackFlagState>;

const CONTROL_FIELD: Record<TrackControl, keyof TrackFlagState> = {
  eye: "hidden",
  lock: "locked",
  mute: "muted",
  solo: "solo",
};

export function isAudioLikeTrack(trackKey: string): boolean {
  return trackKey === "audio" || trackKey === "sfx" || trackKey.startsWith("lipsync:");
}

export function toggleTrackFlag(
  flags: TrackFlagMap | undefined,
  trackKey: string,
  control: TrackControl,
): TrackFlagMap {
  const field = CONTROL_FIELD[control];
  const current = flags?.[trackKey] || {};
  const nextValue = !current[field];
  const next: TrackFlagMap = {
    ...(flags || {}),
    [trackKey]: { ...current, [field]: nextValue },
  };
  if (field === "solo" && nextValue) {
    for (const key of Object.keys(next)) {
      if (key !== trackKey && isAudioLikeTrack(key)) {
        next[key] = { ...next[key], solo: false };
      }
    }
  }
  return next;
}

export function effectiveTrackFlags(flags: TrackFlagMap | undefined, trackKey: string): TrackFlagState {
  const own = flags?.[trackKey] || {};
  if (!isAudioLikeTrack(trackKey)) return own;
  const anySolo = Object.entries(flags || {}).some(([key, state]) => isAudioLikeTrack(key) && state.solo);
  if (anySolo && !own.solo) {
    return { ...own, muted: true };
  }
  return own;
}

export function trackControlLabel(control: TrackControl, active: boolean, trackName: string): string {
  if (control === "eye") {
    return active ? `Show the ${trackName} track` : `Hide the ${trackName} track`;
  }
  if (control === "lock") {
    return active ? `Unlock the ${trackName} track` : `Lock the ${trackName} track so clips cannot move`;
  }
  if (control === "mute") {
    return active ? `Unmute the ${trackName} track` : `Mute the ${trackName} track`;
  }
  return active ? `Turn off solo for ${trackName}` : `Solo the ${trackName} track`;
}
