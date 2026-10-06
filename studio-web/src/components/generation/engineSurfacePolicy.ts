import type { EngineName } from "../../types";

export type GeneratorSurface = "text-to-video" | "one-frame" | "three-frame" | "timeline";

export type EngineSurfaceDecision = {
  visible: boolean;
  disabled: boolean;
  reason: string;
};

/** Per-surface workflow truth from the backend authority. */
export type WorkflowCapability = {
  supported?: boolean;
  executable?: boolean;
  readiness?: string;
  reason?: string;
  runtime?: string | null;
  workflowKey?: string | null;
};

/** Map the UI surface to the workflow record key. */
export function surfaceWorkflowKey(surface: GeneratorSurface): "t2v" | "i2v" | "multiFrame" | "r2v" {
  if (surface === "text-to-video") return "t2v";
  if (surface === "one-frame") return "i2v";
  if (surface === "three-frame") return "multiFrame";
  return "r2v";
}

/** True Text-to-Video engines (words only). Local LTX 2.5 + MiniMax, then hosted. */
export const T2V_ENGINE_NAMES: readonly EngineName[] = [
  "ltx-2.5",
  "minimax-h3",
  "seedance-2.0",
  "seedance-2.5",
  "fal_kling",
  "fal_veo",
  "fal_runway",
];

export function decideEngineOnSurface(args: {
  engine: EngineName;
  surface: GeneratorSurface;
  executable: boolean;
  supportsTextToVideo: boolean;
  requiresLastFrame: boolean;
  disabledReason?: string;
  /** Per-surface workflow truth from the backend. When present, this is the authority. */
  workflowCapability?: WorkflowCapability;
}): EngineSurfaceDecision {
  const { engine, surface, executable, supportsTextToVideo, requiresLastFrame, disabledReason, workflowCapability } = args;
  if (engine === "auto") {
    return { visible: true, disabled: false, reason: "" };
  }
  // Per-workflow authority: surface + model + workflow, never Timeline flags.
  if (workflowCapability) {
    if (!workflowCapability.supported) {
      return { visible: false, disabled: true, reason: workflowCapability.reason || "No workflow for this surface" };
    }
    const readiness = String(workflowCapability.readiness || "");
    const onDemand = readiness.toLowerCase().includes("on demand");
    return {
      visible: true,
      disabled: !workflowCapability.executable && !onDemand,
      reason: workflowCapability.reason || disabledReason || "Requires setup",
    };
  }

  if (surface === "text-to-video") {
    if (!supportsTextToVideo) {
      return { visible: false, disabled: true, reason: "Reference/Image-to-Video only — use 1 Frame, 3 Frame, or Timeline" };
    }
    return {
      visible: true,
      disabled: !executable,
      reason: disabledReason || "Requires setup",
    };
  }
  if (surface === "one-frame" && requiresLastFrame) {
    return {
      visible: true,
      disabled: true,
      reason: "First and last frame required — use 3 Frame or Timeline",
    };
  }
  // CREATE I2V / multi-frame: Timeline executable=false must not gray out a
  // local engine whose I2V workflow is installed. Missing authority (options
  // still loading) keeps known I2V engines selectable.
  if (surface === "one-frame" && (engine === "minimax-h3" || engine === "ltx-2.5")) {
    return { visible: true, disabled: false, reason: "" };
  }
  if (surface === "three-frame" && engine === "minimax-h3") {
    return { visible: true, disabled: false, reason: "" };
  }
  if (surface === "three-frame" && engine === "ltx-2.5") {
    return {
      visible: engine === "ltx-2.5",
      disabled: true,
      reason: "3 Frame needs a proven first + last still workflow. Ordinary Image-to-Video is not enough.",
    };
  }
  if (
    surface === "three-frame" &&
    (engine === "seedance-2.0" || engine === "seedance-2.5" || engine === "fal_seedance")
  ) {
    return {
      visible: false,
      disabled: true,
      reason: "This generator does not accept three stills",
    };
  }
  return {
    visible: true,
    disabled: !executable,
    reason: disabledReason || "Unsupported in this workflow",
  };
}

export function currentWorkspaceSurface(search: string = typeof window !== "undefined" ? window.location.search : ""): GeneratorSurface {
  const workspace = new URLSearchParams(search).get("workspace") || "";
  if (workspace === "txt2vid") return "text-to-video";
  if (workspace === "one") return "one-frame";
  if (workspace === "three") return "three-frame";
  if (workspace === "timeline") return "timeline";
  return "timeline";
}
