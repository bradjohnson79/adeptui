/**
 * Shared per-project jobs polling store.
 *
 * Multiple React panels used to independently poll GET /api/projects/{id}/jobs,
 * causing a request storm. This module provides ONE polling source per project
 * that all subscribers reuse. It mirrors the singleton + listeners + emit style
 * of studioApiConnection.ts.
 */

import { useCallback, useSyncExternalStore } from "react";
import { api } from "../api";
import type { Job } from "../types";
import { onStudioApiRecovered, shouldSuspendDependentPolling } from "./studioApiConnection";

export type ProjectJobsSnapshot = {
  jobs: Job[];
  lastFetchedAt: number | null;
};

type ProjectJobsListener = (snapshot: ProjectJobsSnapshot) => void;

type ProjectJobsEntry = {
  projectId: string;
  listeners: Set<ProjectJobsListener>;
  snapshot: ProjectJobsSnapshot;
  interval: number | null;
  inFlight: Promise<Job[]> | null;
  hasActiveJob: boolean;
};

const ACTIVE_INTERVAL_MS = 2000;
const IDLE_INTERVAL_MS = 5000;

/**
 * Stable empty snapshot used when projectId is falsy. React's
 * useSyncExternalStore requires getSnapshot to return a referentially
 * stable value when nothing has changed — returning a new object literal
 * on every call causes an infinite render loop ("Maximum update depth
 * exceeded"). This constant ensures the falsy-projectId path always
 * returns the same reference.
 */
export const EMPTY_SNAPSHOT: ProjectJobsSnapshot = { jobs: [], lastFetchedAt: null };

const store = new Map<string, ProjectJobsEntry>();

let recoveryHandlerRegistered = false;

function hasActiveJob(jobs: Job[]): boolean {
  return jobs.some((j) => j.status === "queued" || j.status === "running");
}

function getEntry(projectId: string): ProjectJobsEntry {
  let entry = store.get(projectId);
  if (!entry) {
    entry = {
      projectId,
      listeners: new Set(),
      snapshot: { jobs: [], lastFetchedAt: null },
      interval: null,
      inFlight: null,
      hasActiveJob: false,
    };
    store.set(projectId, entry);
  }
  return entry;
}

function emit(entry: ProjectJobsEntry) {
  const snapshot = entry.snapshot;
  for (const listener of entry.listeners) {
    try {
      listener(snapshot);
    } catch {
      /* ignore subscriber errors */
    }
  }
}

function scheduleInterval(entry: ProjectJobsEntry) {
  if (typeof window === "undefined") return;
  if (entry.interval !== null) {
    window.clearInterval(entry.interval);
  }
  const delay = entry.hasActiveJob ? ACTIVE_INTERVAL_MS : IDLE_INTERVAL_MS;
  entry.interval = window.setInterval(() => {
    void tick(entry);
  }, delay);
}

async function tick(entry: ProjectJobsEntry) {
  if (typeof document !== "undefined" && document.visibilityState === "hidden") return;
  if (shouldSuspendDependentPolling()) return;
  if (entry.inFlight) return;

  entry.inFlight = api.listJobs(entry.projectId);
  try {
    const jobs = await entry.inFlight;
    const active = hasActiveJob(jobs);
    const changed = active !== entry.hasActiveJob;
    entry.hasActiveJob = active;
    entry.snapshot = { jobs, lastFetchedAt: Date.now() };
    emit(entry);
    if (changed) scheduleInterval(entry);
  } catch {
    /* ignore - the outage coordinator owns failure handling */
  } finally {
    entry.inFlight = null;
  }
}

function ensureRecoveryHandler() {
  if (recoveryHandlerRegistered) return;
  recoveryHandlerRegistered = true;
  onStudioApiRecovered(() => {
    for (const entry of store.values()) {
      void tick(entry);
    }
  });
}

export function subscribeProjectJobs(
  projectId: string,
  listener: ProjectJobsListener,
): () => void {
  const entry = getEntry(projectId);
  entry.listeners.add(listener);
  listener(entry.snapshot);
  ensureRecoveryHandler();
  if (entry.interval === null) {
    void tick(entry);
    scheduleInterval(entry);
  }
  return () => {
    entry.listeners.delete(listener);
    if (entry.listeners.size === 0) {
      if (entry.interval !== null && typeof window !== "undefined") {
        window.clearInterval(entry.interval);
      }
      store.delete(projectId);
    }
  };
}

export function refreshProjectJobs(projectId: string): void {
  const entry = store.get(projectId);
  if (!entry) return;
  void tick(entry);
}

export function useProjectJobs(
  projectId: string | undefined | null,
): { jobs: Job[]; refresh: () => void } {
  const subscribe = useCallback(
    (listener: ProjectJobsListener) => {
      if (!projectId) return () => {};
      return subscribeProjectJobs(projectId, listener);
    },
    [projectId],
  );
  const snapshot = useSyncExternalStore(
    subscribe,
    () => {
      if (!projectId) return EMPTY_SNAPSHOT;
      return getEntry(projectId).snapshot;
    },
    () => EMPTY_SNAPSHOT,
  );
  const refresh = useCallback(() => {
    if (!projectId) return;
    refreshProjectJobs(projectId);
  }, [projectId]);
  return { jobs: snapshot.jobs, refresh };
}
