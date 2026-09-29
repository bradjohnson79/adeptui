import { api } from "../api";

export type TimelineMediaBody = {
  mediaType: string;
  assetId: string;
  assetUrl?: string;
  targetTrackType?: string;
  startTime?: number;
  durationSec?: number;
  shotId?: string;
  label?: string;
  metadata?: Record<string, unknown>;
};

/** Every Add to Timeline and drag-drop path uses this command. */
export function addToTimeline(projectId: string, sceneId: string, body: TimelineMediaBody) {
  return api.filmTimelineAddMedia(projectId, sceneId, body);
}
