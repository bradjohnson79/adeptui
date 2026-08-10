import type { InstallJob } from "../contracts/installJobs";
import { installJobBadge } from "../contracts/installJobs";

type Listener = () => void;

let jobs: InstallJob[] = [];
const listeners = new Set<Listener>();

export function setInstallJobsSnapshot(next: InstallJob[]) {
  jobs = Array.isArray(next) ? next : [];
  listeners.forEach((listener) => listener());
}

export function getInstallJobsSnapshot(): InstallJob[] {
  return jobs;
}

export function subscribeInstallJobs(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getInstallJobForComponent(componentId: string): InstallJob | undefined {
  return jobs.find((job) => job.componentId === componentId);
}

export function getInstallBadgeForComponent(componentId: string): string {
  return installJobBadge(getInstallJobForComponent(componentId));
}
