import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import type { SceneTimelineMaster } from "./contracts";

/**
 * Always-on Timeline Preflight (event-driven — NO polling).
 *
 * Watches a stable signature over exactly what the backend `run_preflight`
 * reads (batch generatorId / plannedDuration / promptSegments / references /
 * sourceAnchors, master.turboLora, master.sceneGeneratorId, Master camera /
 * prompt segments) and re-runs the cheap pure-DB preflight check
 * when that signature changes. Both Preflight buttons converge on this hook's
 * single state, so the Generate gate and the Inspector can never diverge.
 *
 * Patterns: 400ms debounce (useDraftField), single-flight + trailing rerun
 * (requestCache), stale-token guard (masterLoadTokenRef). The expensive
 * runtime_dependency staging probe stays generate-time only — never here.
 */

export interface TimelinePreflightFinding {
  severity: string;
  message: string;
  code?: string;
  batchBlockId?: string | null;
}

export type TimelinePreflightStatus = "idle" | "checking" | "ready" | "blocked" | "error";

export interface TimelinePreflightState {
  status: TimelinePreflightStatus;
  summary: string;
  blockingCount: number;
  findings: TimelinePreflightFinding[];
  /** Manual Preflight — bypasses the debounce, still single-flight. */
  recheckNow: () => Promise<void>;
}

const BLOCKING_SEVERITIES = new Set(["error", "critical", "blocker"]);
const ADVISORY_SEVERITIES = new Set(["warning", "advisory"]);
const INFO_SEVERITIES = new Set(["info"]);

/** Project exactly the fields run_preflight reads into a stable string. */
export function buildPreflightSignature(
  master: SceneTimelineMaster | null,
  lipsyncTracksJson?: string | null,
): string {
  const batches = (master?.batchBlocks ?? []).map((b) => ({
    id: b.id,
    g: b.generatorId ?? null,
    d: b.duration?.plannedDuration ?? null,
    h: b.h3Resolution ? [b.h3Resolution.mode, b.h3Resolution.megapixels] : null,
    p: (b.promptSegments ?? []).map((s) => [
      s.start,
      s.length,
      s.text,
      s.role,
      (s.referenceBindingIds ?? []).join(","),
    ]),
    r: (b.references ?? []).map((r) => [
      (r.assetId ?? r.asset_id ?? null) as unknown,
      r.required ? 1 : 0,
      (r.role ?? r.referenceRole ?? null) as unknown,
    ]),
    a: (b.sourceAnchors ?? []).map((a) => a.kind),
  }));
  const cameras = (master?.batchBlocks ?? []).flatMap((b) =>
    (b.cameraInstructions ?? []).map((c) => [c.id, c.start, c.length, c.motion_type || c.text]),
  );
  // SINGLE-STORE: prompt segments hash from Master batch.promptSegments only.
  const masterPrompts = (master?.batchBlocks ?? []).flatMap((b) =>
    (b.promptSegments ?? []).map((s) => [
      s.id,
      s.start,
      s.length,
      s.text,
      (s.referenceBindingIds ?? []).join(","),
    ]),
  );
  return JSON.stringify({
    b: batches,
    t: master?.turboLora ? 1 : 0,
    sg: master?.sceneGeneratorId ?? null,
    cam: cameras,
    ls: lipsyncTracksJson || "",
    mp: masterPrompts,
  });
}

export function summarizePreflightFindings(findings: TimelinePreflightFinding[]): {
  blockingCount: number;
  summary: string;
  status: TimelinePreflightStatus;
} {
  const blocking = findings.filter((f) =>
    BLOCKING_SEVERITIES.has(String(f.severity || "").toLowerCase()),
  );
  const advisories = findings.filter((f) =>
    ADVISORY_SEVERITIES.has(String(f.severity || "").toLowerCase()),
  );
  const infos = findings.filter((f) =>
    INFO_SEVERITIES.has(String(f.severity || "").toLowerCase()),
  );
  const parts: string[] = [];
  if (blocking.length) {
    const codes = [...new Set(blocking.map((f) => f.code || f.severity).filter(Boolean))];
    parts.push(`${blocking.length} blocking (${codes.join(", ")})`);
  }
  if (advisories.length) {
    parts.push(`${advisories.length} advisory`);
  }
  if (infos.length) {
    parts.push(`${infos.length} additional info`);
  }
  const summary = blocking.length
    ? `Blocked: ${parts.join(" · ")}`
    : findings.length
      ? `Ready with ${parts.join(" · ") || `${findings.length} finding(s)`}`
      : "Ready";
  return {
    blockingCount: blocking.length,
    summary,
    status: blocking.length ? "blocked" : "ready",
  };
}

export function useTimelinePreflight(opts: {
  projectId: string;
  sceneId: string | null | undefined;
  master: SceneTimelineMaster | null;
  lipsyncTracksJson?: string | null;
  debounceMs?: number;
}): TimelinePreflightState {
  const { projectId, sceneId, master, lipsyncTracksJson } = opts;
  const debounceMs = opts.debounceMs ?? 400;

  const [status, setStatus] = useState<TimelinePreflightStatus>("idle");
  const [summary, setSummary] = useState("");
  const [blockingCount, setBlockingCount] = useState(0);
  const [findings, setFindings] = useState<TimelinePreflightFinding[]>([]);

  const signature = useMemo(
    () => buildPreflightSignature(master, lipsyncTracksJson),
    [master, lipsyncTracksJson],
  );

  const tokenRef = useRef(0);
  const inFlightRef = useRef(false);
  const pendingRef = useRef(false);
  const timerRef = useRef<number | null>(null);
  const lastRunSignatureRef = useRef<string | null>(null);
  // Latest-signature ref so the trailing rerun always uses fresh state.
  const latestSignatureRef = useRef(signature);
  latestSignatureRef.current = signature;

  const runCheck = useCallback(
    async (sig: string) => {
      if (!sceneId) return;
      if (inFlightRef.current) {
        // Single-flight: remember that a rerun is needed after the current one.
        pendingRef.current = true;
        return;
      }
      inFlightRef.current = true;
      const token = ++tokenRef.current;
      lastRunSignatureRef.current = sig;
      setStatus((prev) => (prev === "idle" || prev === "checking" ? "checking" : prev));
      try {
        const result = await api.directorTimelinePreflight(projectId, sceneId);
        if (token !== tokenRef.current) return; // stale — a newer run owns state
        const next = summarizePreflightFindings(
          (result.findings || []) as TimelinePreflightFinding[],
        );
        setFindings((result.findings || []) as TimelinePreflightFinding[]);
        setBlockingCount(next.blockingCount);
        setSummary(next.summary);
        setStatus(next.status);
      } catch {
        if (token !== tokenRef.current) return;
        // Honest failure, fail-open for the gate (matches manual-button history):
        // a transient preflight error must not block Generate by itself.
        setStatus("error");
        setSummary("Preflight unavailable — check Runtime, then Re-check now.");
      } finally {
        inFlightRef.current = false;
        if (pendingRef.current) {
          pendingRef.current = false;
          const latest = latestSignatureRef.current;
          if (latest && latest !== lastRunSignatureRef.current) {
            void runCheck(latest);
          }
        }
      }
    },
    [projectId, sceneId],
  );

  // Event-driven trigger: scene open + signature change, debounced.
  useEffect(() => {
    if (!sceneId) return;
    if (signature === lastRunSignatureRef.current) return;
    setStatus("checking");
    if (timerRef.current != null) window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => {
      timerRef.current = null;
      void runCheck(signature);
    }, debounceMs);
    return () => {
      if (timerRef.current != null) {
        window.clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [signature, sceneId, debounceMs, runCheck]);

  const recheckNow = useCallback(async () => {
    if (timerRef.current != null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    setStatus("checking");
    await runCheck(latestSignatureRef.current);
  }, [runCheck]);

  return { status, summary, blockingCount, findings, recheckNow };
}
