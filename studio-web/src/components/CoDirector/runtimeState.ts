/** M41 Wave 1 — Co-Director runtime connection state machine. */

export type CoDirectorRuntimeState =
  | "Connected"
  | "Loading Model"
  | "Ollama Unavailable"
  | "Model Unavailable"
  | "Reconnecting"
  | "Degraded"
  | "Tool Execution Unavailable";

export type HealthLike = {
  status?: string;
  reachable?: boolean;
  modelAvailable?: boolean;
  selectedModel?: string | null;
  code?: string | null;
  testOnly?: boolean;
  honesty?: string | null;
  providerId?: string;
  displayName?: string;
} | null;

export type RuntimeStateInput = {
  health: HealthLike;
  healthPending?: boolean;
  reconnecting?: boolean;
  modelLoading?: boolean;
  projectId?: string | null;
  toolsBlocked?: boolean;
};

export function deriveRuntimeState(input: RuntimeStateInput): CoDirectorRuntimeState {
  const { health, healthPending, reconnecting, modelLoading, projectId, toolsBlocked } = input;

  if (reconnecting) return "Reconnecting";
  if (healthPending && !health) return "Loading Model";
  if (modelLoading) return "Loading Model";

  if (!health) return "Ollama Unavailable";

  const code = (health.code || "").toUpperCase();
  const status = health.status || "";

  if (!health.reachable || status === "Not Running" || code === "CONNECTION_REFUSED" || code === "PROVIDER_UNAVAILABLE") {
    return "Ollama Unavailable";
  }

  if (
    status === "Model Missing" ||
    status === "No Models" ||
    status === "Not Configured" ||
    code === "MODEL_NOT_FOUND" ||
    code === "MODEL_NOT_SELECTED" ||
    code === "NO_MODELS_INSTALLED" ||
    (health.reachable && !health.modelAvailable)
  ) {
    return "Model Unavailable";
  }

  if (status === "Degraded" || code === "PROVIDER_RESPONSE_INVALID") {
    return "Degraded";
  }

  if (status === "Ready" && health.modelAvailable) {
    if (toolsBlocked || !projectId) {
      // Connected for chat, but production tools unavailable without a project.
      if (!projectId || toolsBlocked) return "Tool Execution Unavailable";
    }
    return "Connected";
  }

  return "Degraded";
}

export function runtimeStateLabel(state: CoDirectorRuntimeState): string {
  return state;
}

export function isConnectedLike(state: CoDirectorRuntimeState): boolean {
  return state === "Connected" || state === "Tool Execution Unavailable";
}

export function runtimeChipText(opts: {
  state: CoDirectorRuntimeState;
  model?: string | null;
  projectName?: string | null;
  testOnly?: boolean;
}): string {
  const model = opts.model?.trim() || "No model";
  const project = opts.projectName?.trim() || "No Project Selected";
  const suffix = opts.testOnly ? " · test" : "";
  return `${model} · ${opts.state} · ${project}${suffix}`;
}
