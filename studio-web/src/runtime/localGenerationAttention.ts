/**
 * Shared Local-generation attention. One poll for the whole Adept UI.
 * Hosted API jobs never raise this bar.
 */

import { api } from "../api";
import { shouldSuspendDependentPolling } from "./studioApiConnection";

export const LOCAL_GENERATION_ATTENTION =
  "A local generation is in progress. Finish or cancel it before starting another.";

export type LocalGenerationSnapshot = {
  active: boolean;
  jobId: string | null;
  projectId: string | null;
  feature: string | null;
  cancelable: boolean;
};

const IDLE: LocalGenerationSnapshot = {
  active: false,
  jobId: null,
  projectId: null,
  feature: null,
  cancelable: false,
};

type Listener = (snap: LocalGenerationSnapshot) => void;

let snapshot: LocalGenerationSnapshot = { ...IDLE };
const listeners = new Set<Listener>();
let timer: number | null = null;
let inFlight: Promise<void> | null = null;
let started = false;

const IDLE_MS = 6_000;
const ACTIVE_MS = 2_500;

function emit() {
  for (const listener of listeners) {
    try {
      listener(snapshot);
    } catch {
      /* ignore */
    }
  }
}

function setSnapshot(next: LocalGenerationSnapshot) {
  const changed =
    next.active !== snapshot.active ||
    next.jobId !== snapshot.jobId ||
    next.projectId !== snapshot.projectId ||
    next.feature !== snapshot.feature ||
    next.cancelable !== snapshot.cancelable;
  snapshot = next;
  if (changed) emit();
}

export function getLocalGenerationAttention(): LocalGenerationSnapshot {
  return snapshot;
}

export function subscribeLocalGenerationAttention(listener: Listener): () => void {
  listeners.add(listener);
  listener(snapshot);
  return () => {
    listeners.delete(listener);
  };
}

export function localGenerationBlocksStart(): boolean {
  return snapshot.active;
}

async function probe(): Promise<void> {
  if (inFlight) return inFlight;
  inFlight = (async () => {
    if (shouldSuspendDependentPolling()) return;
    try {
      const next = await api.getLocalGeneration();
      setSnapshot({
        active: Boolean(next.active),
        jobId: next.jobId || null,
        projectId: next.projectId || null,
        feature: next.feature || null,
        cancelable: Boolean(next.cancelable),
      });
    } catch {
      /* keep last snapshot — outage banner owns connectivity */
    }
  })().finally(() => {
    inFlight = null;
  });
  return inFlight;
}

function schedule() {
  if (timer != null) window.clearTimeout(timer);
  const delay = snapshot.active ? ACTIVE_MS : IDLE_MS;
  timer = window.setTimeout(() => {
    void probe().finally(schedule);
  }, delay);
}

export function ensureLocalGenerationMonitor(): void {
  if (started || typeof window === "undefined") return;
  started = true;
  void probe().finally(schedule);
}

export async function refreshLocalGenerationAttention(): Promise<void> {
  await probe();
}
