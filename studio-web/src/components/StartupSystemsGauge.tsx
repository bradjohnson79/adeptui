/**
 * Startup Systems Gauge — runtime startup display.
 *
 * Appears automatically when Adept UI begins from a cold or incomplete runtime
 * state. Polls the canonical /api/runtime-manager/status contract (same one the
 * Setup Wizard uses — no competing authority). Maps raw service states to
 * human-readable systems, shows an overall gauge, and AUTO-CLOSES when all
 * required systems are ONLINE. On failure it exposes Retry / Details / Continue
 * (only after an actual failure). Warm launches skip the modal entirely.
 *
 * No fake ONLINE: a system is ONLINE only when the status contract says so.
 * Bounded polling: single-flight, backoff, cleanup on unmount.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type RuntimeManagerStatus } from "../api";
import { bootHandoffTarget, rememberFirstRunComplete } from "../setup/firstRun";
import { buildAiGuidedSetupPath } from "../setup/navigation";
import { buildSnapshot, type StartupSnapshot } from "./startupSnapshot";
import { badgeClass, buildStartupBoard, describeFinalStatus, isCloud12 } from "./startupDisplay";
import "./StartupSystemsGauge.css";

const REQUIRED_TIMEOUT_MS = 120_000;
const READY_HOLD_MS = 1200;

type BootCheck = {
  id: string;
  system: string;
  check: string;
  result: string;
  detail: string;
  durationMs?: number;
  required?: boolean;
};

type BootCert = {
  verdict?: "GO" | "NO-GO";
  headline?: string;
  studioApi?: { host: string; port: number; baseUrl: string; runtimeMode: string };
  progressPct?: number;
  checks?: BootCheck[];
  failed?: Array<{ system: string; check: string; detail: string; result: string }>;
  optional?: Array<{ system: string; check: string; detail: string }>;
};

async function loadBootCertification(method: "GET" | "POST" = "GET"): Promise<BootCert | null> {
  try {
    const path = method === "POST" ? "/api/boot/certification/retry" : "/api/boot/certification";
    const res = await fetch(path, { method, cache: "no-store" });
    if (!res.ok) return { verdict: "NO-GO", headline: "ADEPT UI STARTUP — NO-GO", failed: [{ system: "Studio API", check: "certification", detail: "Startup certification did not respond.", result: "FAIL" }] };
    return (await res.json()) as BootCert;
  } catch {
    return null;
  }
}
const POLL_FAST_MS = 1000;
const POLL_SLOW_MS = 2500;

/** Test hook: allow Playwright to shorten the failure timeout. Production stays 120s. */
function resolveTimeoutMs(): number {
  if (typeof window !== "undefined") {
    const override = (window as unknown as { __ADEPT_STARTUP_TIMEOUT_MS?: number }).__ADEPT_STARTUP_TIMEOUT_MS;
    if (typeof override === "number" && override > 0) return override;
  }
  return REQUIRED_TIMEOUT_MS;
}

export function StartupSystemsGauge() {
  const [snapshot, setSnapshot] = useState<StartupSnapshot | null>(null);
  const [visible, setVisible] = useState(false);
  const [handoffCover, setHandoffCover] = useState(true);
  const [failed, setFailed] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);
  const startRef = useRef<number>(Date.now());
  const closedRef = useRef(false);
  const inFlightRef = useRef(false);
  const handoffCheckedRef = useRef(false);
  const navigate = useNavigate();
  const [bootCert, setBootCert] = useState<BootCert | null>(null);
  const [certFailed, setCertFailed] = useState(false);
  const [bootReportOpen, setBootReportOpen] = useState(false);
  const certFailedRef = useRef(false);
  const certRecheckedRef = useRef(false);
  const certEpochRef = useRef(0);

  const offerEssentialsOrClose = useCallback(async () => {
    if (handoffCheckedRef.current) return;
    handoffCheckedRef.current = true;
    void api.setupLifecycleUpdates().catch(() => undefined);
    let target: "/setup" | "/" = "/";
    try {
      const status = await api.setupStatus();
      rememberFirstRunComplete(status.firstRunSetupComplete);
      target = bootHandoffTarget(status.firstRunSetupComplete, false);
    } catch {
      // A failed flag read must not turn an already-complete record into a new first run.
      target = bootHandoffTarget(undefined, true);
    }
    if (target === "/setup") {
      navigate("/setup", { replace: true });
    }
    closedRef.current = true;
    window.setTimeout(() => {
      setHandoffCover(false);
      setVisible(false);
    }, target === "/setup" ? 0 : READY_HOLD_MS);
  }, [navigate]);

  const probeStudioApi = useCallback(async (): Promise<boolean> => {
    try {
      const r = await fetch("/api/healthz", { method: "GET" });
      return r.ok;
    } catch {
      return false;
    }
  }, []);

  const pollOnce = useCallback(async () => {
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    try {
      const studioApiReachable = await probeStudioApi();
      let status: RuntimeManagerStatus | null = null;
      if (studioApiReachable) {
        try {
          status = await api.runtimeManagerStatus();
        } catch (e) {
          setLastError(e instanceof Error ? e.message : String(e));
        }
      }
      const snap = buildSnapshot(status, studioApiReachable);
      setSnapshot(snap);
      let cert: BootCert | null = null;
      // One later read after a NO-GO. A recovered certification closes the
      // dialog. A failure that is still present stays until Retry.
      const shouldReadCert = studioApiReachable && (!certFailedRef.current || !certRecheckedRef.current);
      if (shouldReadCert) {
        if (certFailedRef.current) certRecheckedRef.current = true;
        const epoch = certEpochRef.current;
        cert = (await loadBootCertification()) ?? {
          verdict: "NO-GO",
          headline: "ADEPT UI STARTUP — NO-GO",
          failed: [{ system: "Studio API", check: "certification", detail: "Startup certification did not respond.", result: "FAIL" }],
        };
        if (epoch !== certEpochRef.current || closedRef.current) return;
        setBootCert(cert);
      }
      if (cert?.verdict === "NO-GO") {
        certFailedRef.current = true;
        setCertFailed(true);
        setVisible(true);
        return;
      }
      if (cert?.verdict === "GO") {
        certFailedRef.current = false;
        setCertFailed(false);
      }
      if (snap.allRequiredOnline && cert?.verdict === "GO" && !closedRef.current) {
        await offerEssentialsOrClose();
      }
      const elapsed = Date.now() - startRef.current;
      // FAILED when the status contract reports a required system as error, OR after the timeout.
      if (snap.anyRequiredFailed && !failed) {
        setFailed(true);
      } else if (!snap.allRequiredOnline && elapsed > resolveTimeoutMs() && !failed) {
        setFailed(true);
      }
    } finally {
      inFlightRef.current = false;
    }
  }, [probeStudioApi, failed, offerEssentialsOrClose]);

  // Initial probe: decide whether to show the modal at all (warm -> skip).
  useEffect(() => {
    let cancelled = false;
    startRef.current = Date.now();
    (async () => {
      const studioUp = await probeStudioApi();
      if (cancelled) return;
      let status: RuntimeManagerStatus | null = null;
      if (studioUp) {
        try {
          status = await api.runtimeManagerStatus();
        } catch {
          status = null;
        }
      }
      if (cancelled) return;
      const snap = buildSnapshot(status, studioUp);
      setSnapshot(snap);
      const cert = studioUp
        ? (await loadBootCertification()) ?? {
            verdict: "NO-GO" as const,
            headline: "ADEPT UI STARTUP — NO-GO",
            failed: [{ system: "Studio API", check: "certification", detail: "Startup certification did not respond.", result: "FAIL" }],
          }
        : null;
      if (cancelled) return;
      setBootCert(cert);
      if (cert?.verdict === "NO-GO") {
        certFailedRef.current = true;
        setCertFailed(true);
        setVisible(true);
        return;
      }
      if (snap.allRequiredOnline && cert?.verdict === "GO") {
        await offerEssentialsOrClose();
        return;
      }
      setVisible(true);
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Bounded polling loop while visible and not closed.
  useEffect(() => {
    if (!visible || closedRef.current) return;
    let stop = false;
    const tick = async () => {
      if (stop) return;
      await pollOnce();
      if (stop || closedRef.current) return;
      const delay = snapshot?.studioApiReachable ? POLL_SLOW_MS : POLL_FAST_MS;
      setTimeout(tick, delay);
    };
    const t = setTimeout(tick, POLL_FAST_MS);
    return () => {
      stop = true;
      clearTimeout(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible, pollOnce]);

  const retryCertification = useCallback(async () => {
    setRetrying(true);
    certEpochRef.current += 1;
    certFailedRef.current = false;
    certRecheckedRef.current = false;
    const cert = await loadBootCertification("POST");
    setBootCert(cert);
    if (cert?.verdict === "GO") {
      setCertFailed(false);
      const studioUp = await probeStudioApi();
      let status: RuntimeManagerStatus | null = null;
      if (studioUp) {
        try {
          status = await api.runtimeManagerStatus();
        } catch {
          status = null;
        }
      }
      const snap = buildSnapshot(status, studioUp);
      setSnapshot(snap);
      if (snap.allRequiredOnline) await offerEssentialsOrClose();
    } else {
      certFailedRef.current = true;
      setCertFailed(true);
      setVisible(true);
    }
    setRetrying(false);
  }, [offerEssentialsOrClose, probeStudioApi]);

  const retry = useCallback(async () => {
    setRetrying(true);
    setFailed(false);
    closedRef.current = false;
    startRef.current = Date.now();
    try {
      await api.runtimeManagerStart().catch(() => {});
    } finally {
      setRetrying(false);
    }
  }, []);

  if (!visible && handoffCover) {
    return <div className="startup-gauge-backdrop" data-testid="first-run-handoff" aria-hidden="true" />;
  }

  if (!visible) {
    if (bootCert?.verdict !== "GO") return null;
    return (
      <div className="boot-ready" data-testid="boot-ready">
        <span>ADEPT UI READY — GO</span>
        {(bootCert.optional ?? []).some((row) => !isCloud12(row.system)) && (
          <span data-testid="boot-optional">
            {(bootCert.optional ?? [])
              .filter((row) => !isCloud12(row.system))
              .map((row) => `${row.system}: ${row.detail}`)
              .join(" · ")}
          </span>
        )}
      </div>
    );
  }
  const snap = snapshot;
  const pct = bootCert?.progressPct ?? snap?.overallPct ?? 0;
  const allOnline = snap?.allRequiredOnline ?? false;
  const runtimeFailed = failed && !allOnline;
  const attention = runtimeFailed || certFailed;
  const sections = buildStartupBoard(snap?.rows ?? [], bootCert?.checks ?? []);
  const runtimeGap = (snap?.rows ?? []).find((row) => row.required && row.state !== "online");
  const status = describeFinalStatus({
    verdict: certFailed || runtimeFailed ? "NO-GO" : bootCert?.verdict,
    progressPct: pct,
    failed: certFailed
      ? bootCert?.failed ?? []
      : runtimeFailed
        ? [{ system: runtimeGap?.label || "Adept Core", detail: "could not be brought online", result: "FAIL" }]
        : [],
    setupOptional: [],
    allRequiredOnline: allOnline && !attention,
  });
  const phaseTitle = attention ? (certFailed ? status.phaseTitle : "Startup Failed") : status.phaseTitle;

  return (
    <div className="startup-gauge-backdrop" role="dialog" aria-modal="true" aria-labelledby="startup-gauge-title" data-testid="startup-systems-gauge">
      <div className="startup-gauge">
        <p className="startup-gauge__brand">ADEPT UI</p>
        <h2 id="startup-gauge-title" className="startup-gauge__title">
          {phaseTitle}
        </h2>
        <div className="startup-gauge__bar">
          <div className={`startup-gauge__bar-fill${attention ? " startup-gauge__bar-fill--failed" : ""}`} style={{ width: `${attention ? 100 : pct}%` }} />
        </div>
        <div className="startup-gauge__pct">
          <span>{pct}%</span>
          <span data-testid="startup-progress-label">{attention ? "A required check needs attention" : status.progressLabel}</span>
        </div>
        {sections.map((section) => (
          <section className="startup-gauge__section" key={section.id} data-testid={`startup-section-${section.id}`}>
            <h3 className="startup-gauge__section-title">{section.title}</h3>
            <div className="startup-gauge__rows">
              {section.rows.map((row) => (
                <div className="startup-gauge__row" key={row.id} data-testid={`startup-system-${row.id}`}>
                  <span className="startup-gauge__row-label">{row.label}</span>
                  <span className={`startup-gauge__row-state sg-state--${badgeClass(row.badge)}`}>{row.badge}</span>
                </div>
              ))}
            </div>
          </section>
        ))}
        {status.headline && (
          <div className={`startup-gauge__final startup-gauge__final--${status.itemKind === "required" ? "attention" : "go"}`} data-testid="startup-final-status">
            <p className="startup-gauge__final-headline" data-testid="boot-verdict">{status.headline}</p>
            {status.body && <p className="startup-gauge__final-body">{status.body}</p>}
            {status.message && <p className="startup-gauge__final-message" data-testid="startup-gauge-message">{status.message}</p>}
            {status.optionalNote && <p className="startup-gauge__final-note">{status.optionalNote}</p>}
            {status.itemKind === "required" && status.items.length > 0 && (
              <ul className="startup-gauge__final-list" data-testid="startup-required-missing">
                {status.items.map((item) => <li key={item}>{item}</li>)}
              </ul>
            )}
          </div>
        )}
        {!status.headline && (
          <p className="startup-gauge__progress-message" data-testid="startup-gauge-message">{snap?.message ?? "Checking…"}</p>
        )}
        {certFailed && (
          <div className="startup-gauge__failed-block" data-testid="boot-attention">
            <p className="startup-gauge__failed-title">Startup Requires Attention</p>
            <p className="startup-gauge__failed-msg">
              {(bootCert?.failed ?? []).map((row) => `${row.system}: ${row.detail}`).join(" ") || "A required startup check did not pass."}
            </p>
            <div className="startup-gauge__actions">
              <button type="button" className="primary" data-testid="boot-retry" disabled={retrying} onClick={() => void retryCertification()}>
                {retrying ? "Retrying…" : "Retry Failed Checks"}
              </button>
              <button type="button" data-testid="boot-report-toggle" onClick={() => setBootReportOpen((open) => !open)}>
                {bootReportOpen ? "Hide Report" : "Startup Certification Report"}
              </button>
              <button
                type="button"
                data-testid="boot-setup"
                onClick={() => {
                  setHandoffCover(false);
                  setVisible(false);
                  navigate(buildAiGuidedSetupPath({ source: "workspace_launch", setupSection: "ai" }));
                }}
              >
                Open Setup
              </button>
            </div>
            {bootReportOpen && (
              <pre className="startup-gauge__details" data-testid="boot-report">
                {(bootCert?.checks ?? [])
                  .filter((check) => !isCloud12(check.id) && !isCloud12(check.system))
                  .map((check) => `${check.system} | ${check.check} | ${check.detail} | ${check.durationMs ?? 0}ms | ${check.result}`)
                  .join("\n")}
              </pre>
            )}
          </div>
        )}
        {runtimeFailed && (
          <div className="startup-gauge__failed-block" data-testid="startup-gauge-failed">
            <p className="startup-gauge__failed-title">A required system did not start.</p>
            <p className="startup-gauge__failed-msg">
              {(snap?.rows ?? []).find((r) => r.required && r.state !== "online")?.label || "Adept Core"} could not be
              brought online automatically. {lastError ? `Last error: ${lastError}.` : ""} You can retry, open runtime
              details, or continue in degraded mode.
            </p>
            <div className="startup-gauge__actions">
              <button type="button" className="primary" data-testid="startup-gauge-retry" disabled={retrying} onClick={() => void retry()}>
                {retrying ? "Retrying…" : "Retry Failed System"}
              </button>
              <button type="button" data-testid="startup-gauge-details" onClick={() => setShowDetails((v) => !v)}>
                {showDetails ? "Hide Details" : "Open Runtime Details"}
              </button>
              {!certFailed && (
                <button type="button" data-testid="startup-gauge-exit" onClick={() => { setHandoffCover(false); setVisible(false); }}>
                  Continue in Degraded Mode
                </button>
              )}
            </div>
            {showDetails && (
              <pre className="startup-gauge__details" data-testid="startup-gauge-details-body">
                {JSON.stringify(snap ?? {}, null, 2)}
              </pre>
            )}
          </div>
        )}
        {!attention && !allOnline && (
          <p className="startup-gauge__hint">
            {snap?.studioApiReachable && bootCert?.verdict !== "GO"
              ? "Finalizing system checks..."
              : "Adept is bringing its creative runtime online. No action needed."}
          </p>
        )}
        {bootCert?.studioApi?.baseUrl && (
          <p className="startup-gauge__endpoint" data-testid="boot-studio-api">{bootCert.studioApi.baseUrl}</p>
        )}
      </div>
    </div>
  );
}
