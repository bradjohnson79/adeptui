/** Shared Timeline help — UI tooltips and Co-Director timeline.explain_control must match. */

export type TimelineHelpEntry = {
  id: string;
  title: string;
  body: string;
  scope?: "batch" | "selected" | "scene" | "item";
  destructive?: boolean;
  approvalRequired?: boolean;
  shortcut?: string;
};

export const TIMELINE_HELP: Record<string, TimelineHelpEntry> = {
  add_batch: {
    id: "add_batch",
    title: "Execution windows",
    body: "Creator Timeline no longer has a Batch track. Execution windows come from the Co-Director plan and rematerialize — they are not authored as batches.",
    scope: "scene",
  },
  preflight: {
    id: "preflight",
    title: "Preflight",
    body: "Checks this scene now — Cast, Location, References, Voice, generator, and prompts. You do not need to open Co-Director.",
    scope: "scene",
  },
  generate_full_scene: {
    id: "generate_full_scene",
    title: "Generate Full Scene",
    body: "Rematerializes execution windows from the Co-Director plan (minting a SceneTake on generator switch if required), then generates the full scene in order.",
    scope: "scene",
    approvalRequired: true,
  },
  generate_current: {
    id: "generate_current",
    title: "Generate Current",
    body: "Per-batch generate was removed from creator Timeline. Use Generate Full Scene (rematerialize + generate).",
    scope: "scene",
    approvalRequired: true,
  },
  generate_selected: {
    id: "generate_selected",
    title: "Generate Selected",
    body: "Selected-batch generate was removed from creator Timeline. Use Generate Full Scene (rematerialize + generate).",
    scope: "scene",
    approvalRequired: true,
  },
  stop_remaining: {
    id: "stop_remaining",
    title: "Stop Remaining Jobs",
    body: "Stops pending work while preserving every Batch that has already completed.",
    scope: "scene",
  },
  resume_incomplete: {
    id: "resume_incomplete",
    title: "Resume Incomplete Jobs",
    body: "Requeues batches that have not finished. This does not resume a generation that is already drawing frames. Successful batches are left alone. Hosted engines may still finish a remote job even after you cancel here.",
    scope: "scene",
  },
  mark_repair_range: {
    id: "mark_repair_range",
    title: "Mark Repair Range",
    body: "Marks a selected interval for Re-Take, Re-Prompt, InPaint, or Background Repair. The original media is preserved.",
    scope: "batch",
    destructive: false,
  },
  edit_duration: {
    id: "edit_duration",
    title: "Scene duration",
    body: "Scene length is authored on the Timeline. Execution window lengths come from rematerialize against the Co-Director plan — not a creator Batch track.",
    scope: "scene",
  },
  switch_video: {
    id: "switch_video",
    title: "Switch to Video Finishing",
    body: "Switches Timeline Master to Video Finishing Mode. Batch Blocks are preserved.",
    scope: "scene",
  },
  stitch_batches: {
    id: "stitch_batches",
    title: "Stitch",
    body: "Joins every finished batch into one continuous clip you can play from start to finish. The original batches stay on the Timeline so you can keep reviewing and extending.",
    scope: "scene",
    approvalRequired: true,
  },
  switch_image: {
    id: "switch_image",
    title: "Switch to Image Planning",
    body: "Switches Timeline Master to Image Planning Mode. Batch Blocks are preserved.",
    scope: "scene",
  },
  timeline_settings: {
    id: "timeline_settings",
    title: "Timeline Settings",
    body: "Adjust display mode, snapping, track density, guidance priority, and playhead behavior. Does not change Adept UI theme.",
    scope: "scene",
  },
  guidance_priority: {
    id: "guidance_priority",
    title: "Guidance Priority",
    body: "Controls how Visual Anchors and Timed Prompt guidance (including camera direction written in Timed Prompt) are weighted when compiling generation intents. Timed Prompt is the sole camera authority. Recorded in provenance; does not rewrite past jobs.",
    scope: "scene",
  },
  remove_item: {
    id: "remove_item",
    title: "Remove from Timeline",
    body: "Removes this item from the Timeline. Source assets remain in Project Library. Undo restores position and bindings.",
    scope: "item",
    destructive: false,
  },
  optional_references: {
    id: "optional_references",
    title: "Supporting References",
    body: "The primary image is your visual anchor. Supporting references are optional and may improve identity consistency. Missing optional references do not block generation unless the generator requires them.",
    scope: "batch",
  },
  reference_name: {
    id: "reference_name",
    title: "Reference Name",
    body: "Give this asset a short name so it can be recognized in prompts and reference lists. Leave empty to auto-generate a safe name. Use in prompts as @name.",
    scope: "item",
  },
  add_to_timeline: {
    id: "add_to_timeline",
    title: "Add to Timeline",
    body: "Places this asset as a Timeline visual or media clip (primary content on a track).",
    scope: "item",
  },
  add_as_reference: {
    id: "add_as_reference",
    title: "Add to References",
    body: "Gives this Library item a reference name so Timeline can use it. Does not place it on a playback track. Removing the name does not delete the Library file.",
    scope: "item",
  },
  camera_motion: {
    id: "camera_motion",
    title: "Camera Motion",
    body: "Describe the movement the shot should feel in Timed Prompt. Film-language motion vocabulary remains available as knowledge; the Camera track lane is retired.",
    scope: "item",
  },
  camera_rig: {
    id: "camera_rig",
    title: "Camera Rig",
    body: "Describe support or capture setup in Timed Prompt when needed. Rig vocabulary remains available as knowledge; the Camera track lane is retired.",
    scope: "item",
  },
  camera_execution_strategy: {
    id: "camera_execution_strategy",
    title: "Execution Strategy",
    body: "Camera execution honesty (native / workflow-mapped / prompt-guided) remains a knowledge concern for Timed Prompt camera language. The Camera track lane is retired.",
    scope: "item",
  },
  draft_mode: {
    id: "draft_mode",
    title: "Draft Mode",
    body: "Makes a cheaper preview first so you can check the motion before spending a full-quality generation. Promote starts a new Final generation from the same prompt and references. On LTX 2.5 this is Fast versus Quality at the same picture size.",
    scope: "batch",
  },
  video_reference: {
    id: "video_reference",
    title: "Video Reference",
    body: "A short clip that shows how the shot should move or perform. The image still says who and what; this clip says how it moves. Match the still’s framing to the video when you can. If the selected generator cannot use video reference, generation stays blocked until you remove the clip or switch generators.",
    scope: "scene",
  },
  picture_shape: {
    id: "picture_shape",
    title: "Picture Shape",
    body: "The production frame for this scene: square, classic, widescreen, or extra-wide. Draft and Final share this shape. The Viewer shows the real canvas — it does not fake a wider picture by cropping.",
    scope: "scene",
  },
  transport_in: {
    id: "transport_in",
    title: "Go to In",
    body: "Moves the playhead to the beginning of the current Batch.",
    scope: "scene",
    shortcut: "Home",
  },
  transport_play: {
    id: "transport_play",
    title: "Play / Pause",
    body: "Plays or pauses the Timeline from the current playhead.",
    scope: "scene",
    shortcut: "Space",
  },
  transport_out: {
    id: "transport_out",
    title: "Go to Out",
    body: "Moves the playhead to the end of the current Batch.",
    scope: "scene",
    shortcut: "End",
  },
  promote_final: {
    id: "promote_final",
    title: "Promote to Final",
    body: "Starts a new full-quality generation from the same prompt and references. It does not continue the preview job.",
    scope: "batch",
    approvalRequired: true,
  },
};

export function getTimelineHelp(id: string): TimelineHelpEntry {
  return (
    TIMELINE_HELP[id] || {
      id,
      title: id,
      body: "Timeline control.",
    }
  );
}
