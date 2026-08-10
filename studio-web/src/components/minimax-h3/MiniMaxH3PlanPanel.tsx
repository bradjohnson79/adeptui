import { useEffect, useRef, useState } from "react";
import { api } from "../../api";
import type { AdeptMiniMaxH3Request, H3Mode, H3Plan, H3SourceSurface } from "../../contracts/minimaxH3";
import { resolveMiniMaxH3Territory } from "../../core/minimaxH3Territory";

type JobState = {
  jobId: string;
  status: string;
  stage: string;
  errorCode?: string | null;
  errorMessage?: string | null;
  outputPath?: string | null;
  media?: Record<string, unknown>;
  provenance?: Record<string, unknown>;
  cancelled?: boolean;
};

type Props = {
  projectId: string;
  prompt: string;
  mode: H3Mode;
  sourceSurface: H3SourceSurface;
  durationSec?: number;
  sceneId?: string;
  shotId?: string;
  startAssetId?: string | null;
  middleAssetId?: string | null;
  endAssetId?: string | null;
  territory?: string;
  retake?: boolean;
  sourceTakeId?: string | null;
  deltaInstruction?: string | null;
  originalPrompt?: string | null;
  onJobTerminal?: (job: JobState) => void;
};

type ReadinessState = {
  ok: boolean;
  ready: boolean;
  privateLocalEnabled: boolean;
  ownerOnly: boolean;
  creatorStatus?: string;
  profile?: {
    label: string;
    width: number;
    height: number;
    length: number;
    steps: number;
    nativeAudio: boolean;
  } | null;
  missingFiles?: string[];
  missingNodes?: string[];
};

function buildAssignments(props: Props) {
  const out: NonNullable<AdeptMiniMaxH3Request["referenceAssignments"]> = [];
  if (props.startAssetId) {
    out.push({ role: "start", assetId: props.startAssetId, displayName: "Start Frame" });
  }
  if (props.middleAssetId) {
    out.push({ role: "middle", assetId: props.middleAssetId, displayName: "Middle Guidance Frame" });
  }
  if (props.endAssetId) {
    out.push({ role: "end", assetId: props.endAssetId, displayName: "End Frame" });
  }
  return out;
}

export function MiniMaxH3PlanPanel(props: Props) {
  const [plan, setPlan] = useState<H3Plan | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [readiness, setReadiness] = useState<ReadinessState | null>(null);
  const [job, setJob] = useState<JobState | null>(null);
  const pollRef = useRef<number | null>(null);
  const territory = resolveMiniMaxH3Territory(props.territory);

  useEffect(() => {
    let cancelled = false;
    api.minimaxH3
      .readiness()
      .then((r) => {
        if (!cancelled) setReadiness(r);
      })
      .catch(() => {
        if (!cancelled)
          setReadiness({ ok: false, ready: false, privateLocalEnabled: false, ownerOnly: true });
      });
    return () => {
      cancelled = true;
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, []);

  function stopPolling() {
    if (pollRef.current) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  function startPolling(projectId: string, jobId: string) {
    stopPolling();
    pollRef.current = window.setInterval(async () => {
      try {
        const res = await api.minimaxH3.getJob(projectId, jobId);
        const next = res.job;
        if (next) {
          setJob(next);
          if (
            next.status === "completed" ||
            next.status === "failed" ||
            next.status === "cancelled"
          ) {
            stopPolling();
            setBusy(false);
            props.onJobTerminal?.(next);
          }
        }
      } catch {
        // keep polling on transient errors
      }
    }, 2500);
  }

  async function prepare() {
    if (!props.prompt.trim()) {
      setMessage("Write a motion prompt first.");
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      const combinedPrompt = props.deltaInstruction
        ? `${props.originalPrompt || props.prompt.trim()}\n\nRe-take change: ${props.deltaInstruction}`
        : props.prompt.trim();
      const body: AdeptMiniMaxH3Request = {
        projectId: props.projectId,
        prompt: combinedPrompt,
        mode: props.mode,
        sourceSurface: props.sourceSurface,
        deployment: "local_weights",
        territory,
        durationSec: props.durationSec || 5,
        referenceAssignments: buildAssignments(props),
        timelineContext:
          props.sceneId || props.shotId
            ? { sceneId: props.sceneId || null, shotId: props.shotId || null, notes: [] }
            : null,
        retake: Boolean(props.retake),
        sourceTakeId: props.sourceTakeId || null,
        deltaInstruction: props.deltaInstruction || null,
        originalPrompt: props.originalPrompt || props.prompt.trim(),
      };
      const result = await api.minimaxH3.preparePlan(body);
      setPlan(result.plan);
      setMessage(result.creatorPreview || result.plan.creatorSummary);
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function generate() {
    if (!plan) return;
    setBusy(true);
    setMessage(null);
    setJob(null);
    try {
      const result = await api.minimaxH3.createJob(props.projectId, plan.planId);
      if (result.ok && result.jobId) {
        setJob({
          jobId: result.jobId,
          status: result.status,
          stage: result.stage || "Starting MiniMax H3",
        });
        setMessage("MiniMax H3 generation started on the Experimental Private Profile.");
        startPolling(props.projectId, result.jobId);
        // Keep Generate disabled via job.status === "running"; clear busy so Cancel stays usable.
        setBusy(false);
      } else if (result.status === "duplicate") {
        setMessage(result.message || "A generation is already running for this plan.");
        setBusy(false);
      } else {
        setMessage(result.message || "MiniMax H3 could not start right now.");
        setBusy(false);
      }
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : String(error));
      setBusy(false);
    }
  }

  async function cancelJob() {
    if (!plan || !job) return;
    setBusy(true);
    try {
      const result = await api.minimaxH3.cancelJob(
        props.projectId,
        plan.planId,
        job.jobId,
        "creator",
      );
      setPlan(result.plan);
      setMessage(result.message || "MiniMax H3 generation cancelled.");
      stopPolling();
      setJob((prev) => (prev ? { ...prev, status: "cancelled", stage: "Cancelled" } : prev));
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function acceptLtxFallback() {
    if (!plan) return;
    setBusy(true);
    setMessage(null);
    try {
      const result = await api.minimaxH3.acceptLtxFallback(props.projectId, plan.planId);
      setPlan(result.plan);
      setMessage(result.message || "LTX fallback recorded. MiniMax H3 did not auto-switch.");
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  const preflight = plan?.preflight;
  const fallback = preflight?.fallbackOffer || plan?.fallbackOffer;
  const three = plan?.threeFramePlan;
  const privateReady = readiness?.ready && readiness?.privateLocalEnabled;
  const profile = readiness?.profile;
  const stageText = job?.stage || (privateReady ? "Ready to generate" : "Checking MiniMax H3");
  const jobDone =
    job?.status === "completed" || job?.status === "failed" || job?.status === "cancelled";

  return (
    <section className="card" data-testid="minimax-h3-plan-panel" style={{ marginTop: "0.9rem" }}>
      <h3 style={{ marginTop: 0 }}>MiniMax H3 Plan</h3>
      <p className="muted" style={{ marginTop: 0 }}>
        Prepare a project-aware MiniMax H3 plan through Adept UI. The video engine stays behind the
        scenes.
      </p>
      <p className="muted" style={{ marginTop: "-0.35rem" }}>
        Local availability is checked for <strong>{territory}</strong> right now.
      </p>

      <div className="row-actions" style={{ gap: "0.4rem", flexWrap: "wrap" }}>
        {readiness?.privateLocalEnabled ? (
          <span className="pill" data-testid="minimax-h3-badge-private" title="This profile runs only on your owner machine.">
            Private Local
          </span>
        ) : null}
        {readiness?.ownerOnly ? (
          <span className="pill" data-testid="minimax-h3-badge-owner" title="Only the project owner can use this profile.">
            Owner Only
          </span>
        ) : null}
        {privateReady ? (
          <span className="pill" data-testid="minimax-h3-badge-experimental" title="This is an early, short motion draft profile with native audio.">
            Experimental
          </span>
        ) : null}
        {profile ? (
          <span className="pill" data-testid="minimax-h3-badge-profile">
            {profile.label}
          </span>
        ) : null}
      </div>

      {message ? (
        <p className="pill warn" data-testid="minimax-h3-message">
          {message}
        </p>
      ) : null}

      <div className="row-actions">
        <button
          type="button"
          className="primary"
          data-testid="minimax-h3-prepare"
          disabled={busy || !props.prompt.trim()}
          onClick={() => void prepare()}
        >
          {busy ? "Preparing…" : "Prepare MiniMax H3 Plan"}
        </button>
        {plan && privateReady && props.mode === "text-to-video" ? (
          <button
            type="button"
            className="primary"
            data-testid="minimax-h3-generate"
            disabled={busy || job?.status === "running"}
            onClick={() => void generate()}
          >
            {job?.status === "running" ? "Generating…" : "Generate on Experimental Private Profile"}
          </button>
        ) : null}
      </div>

      {plan ? (
        <div style={{ marginTop: "0.75rem" }}>
          <p data-testid="minimax-h3-summary">
            <strong>{plan.creatorSummary}</strong>
          </p>
          <p className="muted" data-testid="minimax-h3-disclosure">
            {plan.creatorDisclosure}
          </p>
          {preflight ? (
            <div data-testid="minimax-h3-preflight" style={{ marginTop: "0.55rem" }}>
              <div className="pill">
                Preflight: <strong>{preflight.status}</strong>
              </div>
              {preflight.blockers?.length ? (
                <ul data-testid="minimax-h3-blockers">
                  {preflight.blockers.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}
          {job ? (
            <div data-testid="minimax-h3-job" style={{ marginTop: "0.6rem" }}>
              <div className="pill" data-testid="minimax-h3-job-status">
                {stageText} — <strong>{job.status}</strong>
              </div>
              {job.status === "completed" && job.outputPath ? (
                <p className="muted" data-testid="minimax-h3-job-output">
                  Saved to your project Library. Open the Library to place it on the Timeline.
                </p>
              ) : null}
              {job.status === "failed" ? (
                <p className="muted" data-testid="minimax-h3-job-error">
                  {job.errorMessage || "MiniMax H3 could not finish this generation."}
                </p>
              ) : null}
              {job.status === "running" || job.status === "queued" || job.status === "starting" ? (
                <button
                  type="button"
                  className="ghost"
                  data-testid="minimax-h3-cancel"
                  disabled={busy}
                  onClick={() => void cancelJob()}
                >
                  Cancel generation
                </button>
              ) : null}
              {jobDone ? (
                <button
                  type="button"
                  className="ghost"
                  data-testid="minimax-h3-clear-job"
                  onClick={() => setJob(null)}
                >
                  Clear
                </button>
              ) : null}
            </div>
          ) : null}
          {three ? (
            <div data-testid="minimax-h3-three-frame" style={{ marginTop: "0.55rem" }}>
              <p>
                Three Frame strategy: <strong>Start → Middle</strong> then{" "}
                <strong>Middle → End</strong>
              </p>
              <p className="muted">{three.disclosureText}</p>
              <ol>
                {three.intervals.map((interval) => (
                  <li key={interval.intervalId}>{interval.label}</li>
                ))}
              </ol>
            </div>
          ) : null}
          {fallback ? (
            <div data-testid="minimax-h3-ltx-fallback" style={{ marginTop: "0.75rem" }}>
              <p>
                {fallback.reason ||
                  "MiniMax H3 cannot run under the current setup. LTX can generate this shot locally, but native synchronized audio and some reference controls may differ."}
              </p>
              <button
                type="button"
                className="ghost"
                data-testid="minimax-h3-accept-ltx"
                disabled={busy}
                onClick={() => void acceptLtxFallback()}
              >
                Use LTX for this generation
              </button>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
