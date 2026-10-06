import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import "./ComfyManager.css";

type JobRow = {
  adeptJobId: string;
  projectId: string;
  projectName: string;
  sceneId?: string | null;
  shotId?: string | null;
  source: string;
  workspace?: string | null;
  model?: string;
  status: string;
  statusLabel?: string;
  reconciliation?: string;
  reconciliationLabel?: string;
  resultMissing?: boolean;
  progress?: number;
  message?: string;
  elapsedSec?: number | null;
  lastProgressAt?: string | null;
  currentNode?: string | null;
  width?: number | null;
  height?: number | null;
  durationSec?: number | null;
  megapixels?: number | null;
  stall?: string;
  comfyPromptId?: string;
  outputPath?: string;
  problem?: { summary?: string; technical?: string; nextAction?: string } | null;
};

type QueueRow = {
  lane: string;
  promptId: string;
  ownership: string;
  label: string;
  source?: string;
  projectName?: string;
  adeptJobId?: string;
  model?: string;
};

type Problem = {
  job: JobRow;
  whatHappened: string;
  likelyCause: string;
  nextAction: string;
  technical: string;
};

type Snapshot = {
  header: {
    state: string;
    label: string;
    host: string;
    pid: number | null;
    running: number;
    queued: number;
    vramTotal?: number | null;
    vramFree?: number | null;
    gpu?: string | null;
    submissionsPaused: boolean;
    checkedAt: string;
  };
  active: JobRow[];
  queue: QueueRow[];
  history: JobRow[];
  problems: Problem[];
  diagnostics: Record<string, unknown>;
  cleanup: { items: unknown[]; bytes: number; note: string };
};

const TABS = ["Active", "Queue", "History", "Problems", "Diagnostics"] as const;

function formatElapsed(seconds?: number | null): string {
  if (seconds == null || Number.isNaN(seconds)) return "—";
  const whole = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(whole / 60);
  const rest = whole % 60;
  return `${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
}

function shortId(value?: string | null): string {
  if (!value) return "—";
  return value.length > 12 ? `${value.slice(0, 8)}…` : value;
}

function formatVram(bytes?: number | null): string {
  if (!bytes) return "—";
  return `${(bytes / 1073741824).toFixed(1)} GB`;
}

async function readSnapshot(): Promise<Snapshot> {
  const res = await fetch("/api/comfy-manager/snapshot", { cache: "no-store" });
  if (!res.ok) throw new Error("Comfy Manager could not read the studio.");
  return res.json();
}

export function ComfyManager() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<(typeof TABS)[number]>("Active");
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [technical, setTechnical] = useState<string | null>(null);
  const mounted = useRef(true);
  const chain = useRef(Promise.resolve());

  const refresh = useCallback(async () => {
    const run = chain.current.then(async () => {
      try {
        const next = await readSnapshot();
        if (mounted.current) {
          setSnap(next);
          setError("");
        }
      } catch (err) {
        if (mounted.current) setError(err instanceof Error ? err.message : "Refresh failed");
      }
    });
    chain.current = run.then(() => undefined, () => undefined);
    await run;
  }, []);

  useEffect(() => {
    mounted.current = true;
    void refresh();
    return () => {
      mounted.current = false;
    };
  }, [refresh]);

  useEffect(() => {
    let stopped = false;
    let timer = 0;
    const schedule = () => {
      timer = window.setTimeout(() => {
        if (!stopped && !document.hidden) void refresh();
        if (!stopped) schedule();
      }, document.hidden ? 10000 : 2000);
    };
    schedule();
    const onVisible = () => {
      if (!document.hidden) void refresh();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      stopped = true;
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [refresh]);

  async function post(path: string): Promise<string> {
    setBusy(true);
    setNotice("");
    try {
      const res = await fetch(path, { method: "POST" });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = typeof body?.detail === "string" ? body.detail : "That action did not complete.";
        setNotice(detail);
        return detail;
      }
      if (typeof body?.note === "string") setNotice(body.note);
      await refresh();
      return "";
    } finally {
      setBusy(false);
    }
  }

  function openSource(job: JobRow) {
    if (!job.projectId || !job.workspace) return;
    const params = new URLSearchParams({ workspace: job.workspace });
    if (job.sceneId && job.workspace === "timeline") params.set("scene", job.sceneId);
    navigate(`/project/${job.projectId}?${params.toString()}`);
  }

  async function copyId(value?: string) {
    if (!value) return;
    try {
      await navigator.clipboard.writeText(value);
      setNotice("Copied.");
    } catch {
      setNotice(value);
    }
  }

  function jobDetails(job: JobRow) {
    return (
      <details className="comfy-manager__details">
        <summary>Details</summary>
        <p>Adept job {shortId(job.adeptJobId)} <button type="button" onClick={() => void copyId(job.adeptJobId)}>Copy</button></p>
        <p>Comfy prompt {shortId(job.comfyPromptId)} <button type="button" onClick={() => void copyId(job.comfyPromptId)}>Copy</button></p>
        <p>Recorded state: {job.status}</p>
      </details>
    );
  }

  const header = snap?.header;
  return (
    <div className="comfy-manager" data-testid="comfy-manager">
      <header className="comfy-manager__header">
        <div>
          <p className="comfy-manager__kicker">ComfyUI</p>
          <h1 data-testid="comfy-manager-status">{header?.label ?? "Checking"}</h1>
          <p>{header?.host ?? "127.0.0.1:8188"}{header?.pid ? ` · PID ${header.pid}` : ""}</p>
        </div>
        <dl>
          <div><dt>Running</dt><dd>{header?.running ?? "—"}</dd></div>
          <div><dt>Queued</dt><dd>{header?.queued ?? "—"}</dd></div>
          <div><dt>GPU</dt><dd>{header?.gpu || "—"}</dd></div>
          <div><dt>VRAM free</dt><dd>{formatVram(header?.vramFree)} / {formatVram(header?.vramTotal)}</dd></div>
        </dl>
        <p className="comfy-manager__checked">Last health check {header?.checkedAt ? new Date(header.checkedAt).toLocaleTimeString() : "—"}</p>
        <div className="comfy-manager__actions">
          <button type="button" onClick={() => void refresh()} disabled={busy}>Refresh status</button>
          {header?.submissionsPaused ? (
            <button type="button" data-testid="comfy-manager-resume" onClick={() => void post("/api/comfy-manager/resume")} disabled={busy}>Resume Adept queue</button>
          ) : (
            <button type="button" data-testid="comfy-manager-pause" onClick={() => void post("/api/comfy-manager/pause")} disabled={busy}>Pause Adept queue</button>
          )}
          <button type="button" data-testid="comfy-manager-cleanup" onClick={() => void post("/api/comfy-manager/cleanup/preview")} disabled={busy}>Review safe cleanup</button>
        </div>
        {header?.submissionsPaused && <p>Adept will not send more work. The job already rendering continues. Comfy stays up.</p>}
        {error && <p role="alert">{error}</p>}
        {notice && <p role="status" data-testid="comfy-manager-notice">{notice}</p>}
      </header>
      <nav className="comfy-manager__tabs" aria-label="Comfy Manager">
        {TABS.map((name) => (
          <button key={name} type="button" className={tab === name ? "is-selected" : ""} onClick={() => setTab(name)} data-testid={`comfy-tab-${name.toLowerCase()}`}>
            {name}
          </button>
        ))}
      </nav>
      {tab === "Active" && (
        <section>
          {(snap?.active ?? []).length === 0 && <p>No Adept job is generating right now.</p>}
          {(snap?.active ?? []).map((job) => (
            <article key={job.adeptJobId} className="comfy-manager__job" data-testid="comfy-active-job">
              <h2>{job.source}{job.model ? ` · ${job.model}` : ""}</h2>
              <p>
                {job.durationSec ? `${job.durationSec} sec` : ""}
                {job.megapixels ? ` · ${job.megapixels} MP` : ""}
                {job.width && job.height ? ` · ${job.width}×${job.height}` : ""}
              </p>
              <p>Project: {job.projectName}</p>
              <p>{job.statusLabel || job.status}{typeof job.progress === "number" ? ` — ${Math.round(job.progress * 100)}%` : ""} · Elapsed {formatElapsed(job.elapsedSec)}</p>
              {job.stall === "possible" && <p>Possible stall. Comfy still has this job.</p>}
              {job.stall === "stalled" && <p>Stalled. Comfy is no longer moving this job.</p>}
              {job.reconciliationLabel && <p data-testid={job.resultMissing ? "comfy-result-missing" : "comfy-state-mismatch"}>{job.reconciliationLabel}</p>}
              {job.currentNode && <p>Stage node {job.currentNode}</p>}
              {jobDetails(job)}
              <div className="comfy-manager__actions">
                <button type="button" onClick={() => navigate(`/project/${job.projectId}`)}>Open project</button>
                {job.workspace && <button type="button" onClick={() => openSource(job)}>Open source</button>}
                {(job.reconciliation === "mismatch" || job.resultMissing) && (
                  <button type="button" data-testid="comfy-reconcile" disabled={busy} onClick={() => void post("/api/comfy-manager/reconcile")}>Reconcile status</button>
                )}
                <button type="button" data-testid="comfy-cancel" disabled={busy} onClick={() => void post(`/api/comfy-manager/jobs/${job.adeptJobId}/cancel`)}>Cancel</button>
              </div>
            </article>
          ))}
        </section>
      )}
      {tab === "Queue" && (
        <section>
          {(snap?.queue ?? []).length === 0 && <p>Comfy’s queue is empty.</p>}
          {(snap?.queue ?? []).map((row) => (
            <article key={`${row.lane}-${row.promptId}`} className="comfy-manager__job">
              <h2>{row.lane === "running" ? "Running" : "Pending"} · {row.label}</h2>
              <p>{row.source || "Not submitted by Adept"}{row.projectName ? ` · ${row.projectName}` : ""}</p>
              {row.ownership === "external" && <p>This work belongs to something outside Adept. It will not be cancelled or retried from here.</p>}
            </article>
          ))}
        </section>
      )}
      {tab === "History" && (
        <section>
          {(snap?.history ?? []).map((job) => (
            <article key={job.adeptJobId} className="comfy-manager__job">
              <h2 data-testid="comfy-history-status">{job.source} · {job.statusLabel || job.status}</h2>
              <p>{job.projectName}{job.model ? ` · ${job.model}` : ""}</p>
              {jobDetails(job)}
              <div className="comfy-manager__actions">
                <button type="button" onClick={() => navigate(`/project/${job.projectId}`)}>Open project</button>
                {job.workspace && <button type="button" onClick={() => openSource(job)}>Open source</button>}
                <button type="button" onClick={() => navigate(`/project/${job.projectId}?workspace=library`)}>Open in Library</button>
                {(job.status === "failed" || job.status === "cancelled" || job.status === "interrupted") && (
                  <button type="button" data-testid="comfy-retry" disabled={busy} onClick={() => void post(`/api/comfy-manager/jobs/${job.adeptJobId}/retry`)}>Retry</button>
                )}
              </div>
            </article>
          ))}
        </section>
      )}
      {tab === "Problems" && (
        <section>
          {(snap?.problems ?? []).length === 0 && <p>Nothing needs attention.</p>}
          {(snap?.problems ?? []).map((problem) => (
            <article key={problem.job.adeptJobId} className="comfy-manager__job">
              <h2>{problem.whatHappened}</h2>
              <p>{problem.likelyCause}</p>
              <p>{problem.nextAction}</p>
              <button type="button" onClick={() => setTechnical(technical === problem.technical ? null : problem.technical)}>Technical details</button>
              {technical === problem.technical && <pre>{problem.technical || "No raw error was stored."}</pre>}
            </article>
          ))}
        </section>
      )}
      {tab === "Diagnostics" && (
        <section className="comfy-manager__job" data-testid="comfy-diagnostics">
          <p>Health response: {String(snap?.diagnostics?.healthHttp ?? "—")}</p>
          <p>Queue response: {String(snap?.diagnostics?.queueHttp ?? "—")}</p>
          <p data-testid="comfy-history-read">History response: {String(snap?.diagnostics?.historyHttp ?? "—")}</p>
          <p>Process: {String(snap?.diagnostics?.pid ?? "—")}</p>
          <p>{String(snap?.diagnostics?.progressChannel ?? "")}</p>
          <p>{snap?.cleanup?.note}</p>
          <button type="button" onClick={() => void refresh()}>Refresh diagnostics</button>
        </section>
      )}
    </div>
  );
}
