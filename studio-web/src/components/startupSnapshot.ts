/**
 * Pure startup-snapshot logic — no React/CSS/api imports, so it is unit-testable
 * in the node vitest environment. The modal component imports from here.
 */
import type { RuntimeManagerStatus } from "../api";

export type SystemState = "checking" | "starting" | "online" | "degraded" | "failed" | "on_demand";

export interface SystemRow {
  id: string;
  label: string;
  state: SystemState;
  required: boolean;
  detail?: string;
}

export interface StartupSnapshot {
  rows: SystemRow[];
  overallPct: number;
  allRequiredOnline: boolean;
  anyRequiredFailed: boolean;
  studioApiReachable: boolean;
  message: string;
}

/** Map a raw service status to a system state. error/crashed/port_conflict → failed. */
function mapRequiredState(
  up: boolean,
  starting: boolean,
  rawStatus: string | undefined,
  rawState: string | undefined,
): SystemState {
  if (up) return "online";
  if (rawStatus === "error" || rawState === "crashed" || rawState === "port_conflict") return "failed";
  if (starting || rawStatus === "starting") return "starting";
  return "starting"; // offline/stopped during boot = still coming up (failed only after timeout)
}

function logicalAvailability(status: RuntimeManagerStatus | null, id: string): string | undefined {
  const row = status?.logicalServices?.[id];
  const value = row && typeof row.availability === "string" ? row.availability : undefined;
  return value;
}

function mapLogicalAvailability(availability: string | undefined, fallback: SystemState): SystemState {
  switch ((availability || "").toUpperCase()) {
    case "ONLINE":
      return "online";
    case "STARTING":
      return "starting";
    case "ON_DEMAND":
      return "on_demand";
    case "DEGRADED":
      return "degraded";
    case "FAILED":
      return "failed";
    default:
      return fallback;
  }
}

/** Build the human-readable system rows from the canonical status contract. */
export function buildSnapshot(status: RuntimeManagerStatus | null, studioApiReachable: boolean): StartupSnapshot {
  const adept = status?.adeptRuntime;
  const managerUp = Boolean(adept?.managerPid) || studioApiReachable;
  const studioUp = studioApiReachable || adept?.studioApiHealth === "healthy" || status?.studioApi?.status === "running";
  const comfyUp = status?.comfyui?.status === "running" || adept?.comfyState === "ready" || adept?.comfyState === "busy";
  const comfyStarting = status?.comfyui?.status === "starting" || adept?.comfyState === "starting";
  const ollamaUp = status?.ollama?.status === "running" || Boolean(status?.ollama?.daemonOnline);
  const ollamaStarting = status?.ollama?.status === "starting";
  const ollamaConfigured = status?.ollama?.configured !== false && status?.ollama?.status !== "not_configured";
  const ollamaFailed = status?.ollama?.status === "error";
  const localAiRequired = !status || ollamaConfigured || ollamaStarting || ollamaUp;
  const localAiState: SystemState = ollamaUp
    ? "online"
    : ollamaFailed
      ? "failed"
      : !status || ollamaStarting || (ollamaConfigured && status.ollama?.status === "stopped")
        ? "starting"
        : "on_demand";
  const localAiDetail = ollamaUp
    ? status?.ollama?.modelReady
      ? "model ready"
      : "online — model still loading"
    : localAiState === "starting"
      ? "starting"
      : status?.ollama?.configured === false
        ? "not installed"
        : "on demand";
  const routeAUp = status?.routeA?.status === "running";
  const tunnelUp = status?.tunnel?.status === "running";
  const comfyLogical = logicalAvailability(status, "runtime.comfy");
  const videoLogical = logicalAvailability(status, "runtime.video");
  const creatorState = mapLogicalAvailability(
    comfyLogical,
    mapRequiredState(comfyUp, comfyStarting, status?.comfyui?.status, adept?.comfyState),
  );
  const videoState = mapLogicalAvailability(videoLogical, routeAUp ? "online" : "on_demand");

  const rows: SystemRow[] = [
    { id: "adept_core", label: "Adept Core", required: true, state: managerUp ? "online" : "starting", detail: adept?.managerPid ? `manager pid ${adept.managerPid}` : undefined },
    { id: "studio_api", label: "Studio API", required: true, state: mapRequiredState(studioUp, status?.studioApi?.status === "starting", status?.studioApi?.status, adept?.studioApiHealth), detail: adept?.studioApiPid ? `pid ${adept.studioApiPid}` : undefined },
    { id: "creator_engine", label: "Creator Engine", required: true, state: creatorState, detail: adept?.comfyState ? `comfy ${adept.comfyState}` : undefined },
    { id: "codirector", label: "Co-Director Runtime", required: false, state: studioUp ? "online" : "starting" },
    { id: "local_ai", label: "Local AI Runtime", required: localAiRequired, state: localAiState, detail: localAiDetail },
    { id: "comfy_mcp", label: "Comfy MCP", required: false, state: comfyUp || creatorState === "online" ? "online" : "starting", detail: comfyUp || creatorState === "online" ? "attached" : "waiting for Creator Engine" },
    { id: "video_runtime", label: "Video Runtime", required: false, state: videoState, detail: videoState === "online" ? "route A ready" : "on demand" },
    { id: "remote_access", label: "Remote Access", required: false, state: tunnelUp ? "online" : "on_demand" },
  ];

  if (!studioApiReachable && status === null) {
    for (const r of rows) if (r.required) r.state = "starting";
  }

  const required = rows.filter((r) => r.required);
  const onlineCount = required.filter((r) => r.state === "online").length;
  const overallPct = Math.round((onlineCount / required.length) * 100);
  const allRequiredOnline = required.every((r) => r.state === "online");
  const anyRequiredFailed = required.some((r) => r.state === "failed");

  let message = "Bringing Creative Systems Online";
  if (allRequiredOnline) message = "ALL SYSTEMS ONLINE";
  else if (anyRequiredFailed) message = "STARTUP FAILED";

  return { rows, overallPct, allRequiredOnline, anyRequiredFailed, studioApiReachable, message };
}
