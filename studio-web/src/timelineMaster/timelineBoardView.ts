/** Derived Timeline presentation from SceneTimelineMaster. Not a persist store. */

import type { TimelineBoardView } from "../components/DirectorTracks";
import { masterPromptSegmentToView } from "../components/DirectorTracks";
import { flattenMasterPrompts, projectMasterPreviewClips } from "./masterTimelineMutate";
import type { SceneTimelineMaster } from "./contracts";

export type { TimelineBoardView };

export function deriveTimelineBoardView(
  master: SceneTimelineMaster | null | undefined,
  extras?: {
    playhead?: number;
    durationSec?: number;
    mediaMode?: "image" | "video";
    guidancePriority?: TimelineBoardView["guidance_priority"];
  },
): TimelineBoardView {
  const projected = projectMasterPreviewClips(master);
  return {
    media_mode: extras?.mediaMode ?? (projected.videoClips.length ? "video" : "image"),
    duration_sec: extras?.durationSec ?? 0,
    imageClips: projected.imageClips as TimelineBoardView["imageClips"],
    videoClips: projected.videoClips as TimelineBoardView["videoClips"],
    audioClips: projected.audioClips as TimelineBoardView["audioClips"],
    sfxClips: projected.sfxClips as TimelineBoardView["sfxClips"],
    promptSegments: flattenMasterPrompts(master).map(masterPromptSegmentToView),
    cameraClips: [],
    video_reference_clips: [],
    image_reference_clips: [],
    lipsync: { tracks: [] },
    playhead: extras?.playhead ?? 0,
    guidance_priority: extras?.guidancePriority ?? "visual_first",
  };
}
