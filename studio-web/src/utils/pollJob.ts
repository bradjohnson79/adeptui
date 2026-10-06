export type PollJobOptions<T extends { status: string }> = {
  getJob: (jobId: string) => Promise<T>;
  intervalMs: number;
  onUpdate: (job: T) => void;
  onTerminal?: (job: T, status: string) => void;
  terminalStatuses?: string[];
};

const DEFAULT_TERMINAL_STATUSES = [
  "done",
  "failed",
  "cancelled",
  "canceled",
  "timed_out",
];

/**
 * Poll a single job until it reaches a terminal status, then stop.
 *
 * The caller is responsible for clearing the returned stop function on
 * unmount or when the watched job id changes. This helper only fixes the
 * lifecycle gating: it never polls when idle and it stops automatically at
 * a terminal status so the interval does not outlive the job.
 */
export function pollJob<T extends { status: string }>(
  jobId: string,
  options: PollJobOptions<T>,
): () => void {
  const { getJob, intervalMs, onUpdate, onTerminal } = options;
  const terminal = new Set(
    options.terminalStatuses ?? DEFAULT_TERMINAL_STATUSES,
  );

  let timer: number | undefined;
  let active = true;

  const stop = () => {
    active = false;
    if (timer !== undefined) {
      clearInterval(timer);
      timer = undefined;
    }
  };

  const tick = async () => {
    if (!active) return;
    try {
      const job = await getJob(jobId);
      if (!active) return;
      onUpdate(job);
      if (terminal.has(job.status)) {
        onTerminal?.(job, job.status);
        stop();
      }
    } catch {
      /* keep polling */
    }
  };

  timer = setInterval(() => void tick(), intervalMs);
  // Fire an immediate first tick so the first progress update is not delayed
  // by a full interval (callers previously ticked immediately on mount).
  void tick();
  return stop;
}
