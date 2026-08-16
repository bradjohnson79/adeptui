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
    title: "Add Batch",
    body: "Creates a new Batch Block as a stable production container on this scene. Does not start generation.",
    scope: "scene",
  },
  preflight: {
    id: "preflight",
    title: "Co-Director Preflight",
    body: "Inspects prompts, references, duration, continuity, runtime readiness, and generator compatibility before generation.",
    scope: "scene",
  },
  generate_full_scene: {
    id: "generate_full_scene",
    title: "Generate Full Scene",
    body: "Runs all ready Batch Blocks through the selected scene generator and assembles the results in order.",
    scope: "scene",
    approvalRequired: true,
  },
  generate_current: {
    id: "generate_current",
    title: "Generate Current",
    body: "Generates only the currently selected Batch Block.",
    scope: "batch",
    approvalRequired: true,
  },
  generate_selected: {
    id: "generate_selected",
    title: "Generate Selected",
    body: "Generates only the Batch Blocks currently selected in Timeline Master.",
    scope: "selected",
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
    body: "Continues only Batches that have not completed. Successful Batches are not regenerated.",
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
    title: "Edit Batch Duration",
    body: "Changes the planned duration of this Batch. Generator limits will be checked before saving.",
    scope: "batch",
  },
  switch_video: {
    id: "switch_video",
    title: "Switch to Video Finishing",
    body: "Switches Timeline Master to Video Finishing Mode. Batch Blocks are preserved.",
    scope: "scene",
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
    body: "Controls how Visual Anchors, Timed Prompts, and Camera guidance are weighted when compiling generation intents. Recorded in provenance; does not rewrite past jobs.",
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
    title: "Add as Reference",
    body: "Attaches this asset as optional supporting guidance for identity, wardrobe, props, or environment. Distinct from placing it on the Timeline.",
    scope: "item",
  },
  camera_motion: {
    id: "camera_motion",
    title: "Camera Motion",
    body: "Choose the movement the shot should feel. Search by film language, or use Custom to preserve your own phrase honestly.",
    scope: "item",
  },
  camera_rig: {
    id: "camera_rig",
    title: "Camera Rig",
    body: "Choose the support or capture setup for the shot. Use Custom when the setup needs your own wording.",
    scope: "item",
  },
  camera_execution_strategy: {
    id: "camera_execution_strategy",
    title: "Execution Strategy",
    body: "Shows how honestly the selected camera note can be executed: native, workflow-mapped, prompt-guided, approximate, or unsupported.",
    scope: "item",
  },
  draft_mode: {
    id: "draft_mode",
    title: "Draft Mode",
    body: "Makes a cheaper preview first so you can check the motion before spending a full-quality generation. Promote starts a new Final generation from the same prompt and references.",
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
