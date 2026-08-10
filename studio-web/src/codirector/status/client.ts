import { api } from "../../api";
import type { StatusCheckRequest, StatusRegistryCheck, StatusRun } from "./types";

export async function fetchStatusRegistry(): Promise<StatusRegistryCheck[]> {
  const payload = await api.codirectorStatusRegistry();
  return payload.checks;
}

export async function runStatusCheck(body: StatusCheckRequest): Promise<StatusRun> {
  return api.codirectorStatusCheck(body);
}

export async function runStatusCheckComponent(checkId: string, body: StatusCheckRequest): Promise<StatusRun> {
  return api.codirectorStatusCheckComponent(checkId, body);
}

export async function runDeepDiagnostic(body: StatusCheckRequest & { confirm: boolean }): Promise<StatusRun> {
  return api.codirectorDeepDiagnostic(body);
}

export async function fetchLatestStatus(projectId?: string, sceneId?: string): Promise<StatusRun | null> {
  const payload = await api.codirectorStatusLatest({ projectId, sceneId });
  return payload.run;
}

export async function fetchStatusHistory(projectId?: string, sceneId?: string, limit = 20): Promise<StatusRun[]> {
  const payload = await api.codirectorStatusHistory({ projectId, sceneId, limit });
  return payload.runs;
}

export function statusEventsUrl(): string {
  return "/api/codirector/status/events";
}
