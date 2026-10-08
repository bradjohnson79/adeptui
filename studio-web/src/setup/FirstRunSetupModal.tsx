import { useEffect, useState } from "react";
import { formatBytes } from "./helpers";
import type { FirstRunScan } from "./firstRun";
import { scanAllowsCompletion } from "./firstRun";
import type { SetupComponentStatus, SetupStatusResponse } from "./types";

type WizardStep = "welcome" | "scan" | "needs" | "review" | "install" | "verify" | "done" | "blocked";

function plainNeed(item: { id: string; name: string }): string {
  if (item.id.startsWith("workflow:image")) {
    return "The essential image workflow still needs a check.";
  }
  if (item.id.startsWith("workflow:")) {
    return "The essential video workflow still needs a check.";
  }
  return `${item.name} still needs to be installed.`;
}

function lineState(component: SetupComponentStatus | undefined, ready: boolean): string {
  if (!component) return ready ? "Ready" : "Needed";
  if (component.status === "ready") return "Ready";
  if (component.status === "installing" || component.status === "checking") {
    return component.stage?.trim() || "Installing";
  }
  if (component.status === "error") return "Needs another try";
  return "Needed";
}

export function FirstRunSetupModal({
  status,
  scanning,
  installing,
  onRescan,
  onBegin,
  onFinish,
}: {
  status: SetupStatusResponse;
  scanning: boolean;
  installing: boolean;
  onRescan: () => Promise<SetupStatusResponse | null>;
  onBegin: () => Promise<void>;
  onFinish: () => void;
}) {
  const [step, setStep] = useState<WizardStep>("welcome");
  const [exitAsk, setExitAsk] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const scan: FirstRunScan | undefined = status.firstRunScan;
  const needed = scan?.essentialNeeded ?? [];
  const already = scan?.alreadyReady ?? [];
  const byId = new Map(status.components.map((component) => [component.id, component]));

  const askToLeave = () => {
    if (step === "done") return;
    setExitAsk(true);
  };

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") askToLeave();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  });

  const progressValues = [...already, ...needed]
    .map((item) => byId.get(item.id)?.progress)
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  const overall = progressValues.length
    ? Math.round(
      progressValues.reduce((sum, value) => sum + (value <= 1 ? value * 100 : value), 0) / progressValues.length,
    )
    : null;

  const conclude = (next: SetupStatusResponse | null) => {
    setStep(scanAllowsCompletion(next?.firstRunScan) ? "done" : "blocked");
  };

  const runInstall = async () => {
    setStep("install");
    if (needed.length > 0) await onBegin();
    let sawWork = false;
    for (let pass = 0; pass < 180; pass += 1) {
      const next = await onRescan();
      const working = (next?.components ?? []).some((component) =>
        component.status === "installing" || component.status === "checking",
      ) || next?.overall_status === "preparing" || Boolean(next?.active_operation);
      if (working) sawWork = true;
      if (scanAllowsCompletion(next?.firstRunScan)) {
        setStep("done");
        return;
      }
      if (!working && (sawWork || pass > 0)) {
        conclude(next);
        return;
      }
      await new Promise((resolve) => window.setTimeout(resolve, 3000));
    }
    setStep("blocked");
  };

  return (
    <div
      className="setup-dialog-backdrop"
      role="presentation"
      data-testid="setup-wizard-modal"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) askToLeave();
      }}
    >
      <section
        className="setup-dialog setup-installer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="setup-wizard-title"
      >
        <header className="setup-dialog-header">
          <h2 id="setup-wizard-title">Adept UI Setup</h2>
        </header>

        {exitAsk && step !== "done" ? (
          <>
            <p>Adept UI needs its essential setup completed before the production workspace is ready.</p>
            <div className="row-actions">
              <button type="button" className="primary" onClick={() => setExitAsk(false)}>
                Continue Setup
              </button>
            </div>
          </>
        ) : null}

        {!exitAsk && step === "welcome" && (
          <>
            <p>Welcome to Adept UI.</p>
            <p>We'll prepare the essential systems needed to use Adept UI.</p>
            <div className="row-actions">
              <button
                type="button"
                className="primary"
                data-testid="setup-wizard-next"
                onClick={() => {
                  setStep("scan");
                  void onRescan();
                }}
              >
                Next
              </button>
            </div>
          </>
        )}

        {!exitAsk && step === "scan" && (
          <>
            <h3>System scan</h3>
            {scanning || !scan ? <p role="status">Scanning your computer…</p> : (
              <ul>
                <li>{scan.nodeCatalogChecked ? "✓" : "○"} ComfyUI node catalogue</li>
                <li>{scan.baselineImageWorkflow === "ready" ? "✓" : "○"} Image generation</li>
                <li>{scan.baselineVideoWorkflow === "ready" ? "✓" : "○"} Video generation</li>
                {already.map((item) => <li key={item.id}>✓ {item.name}</li>)}
                {needed.map((item) => <li key={item.id}>○ {item.name}</li>)}
              </ul>
            )}
            <div className="row-actions">
              <button type="button" className="ghost" onClick={() => setStep("welcome")}>Back</button>
              <button type="button" className="primary" disabled={scanning || !scan} onClick={() => setStep("needs")}>Next</button>
            </div>
          </>
        )}

        {!exitAsk && step === "needs" && (
          <>
            <h3>Essential components</h3>
            <p>Already available</p>
            <ul>
              {already.length === 0 ? <li>None yet</li> : already.map((item) => <li key={item.id}>✓ {item.name}</li>)}
            </ul>
            <p>Needs installation</p>
            <ul>
              {needed.length === 0
                ? <li>No essential files are missing.</li>
                : needed.map((item) => <li key={item.id}>○ {item.name}</li>)}
            </ul>
            <p className="muted">Optional items stay on the Setup page after this install.</p>
            <div className="row-actions">
              <button type="button" className="ghost" onClick={() => setStep("scan")}>Back</button>
              <button type="button" className="primary" onClick={() => setStep("review")}>Next</button>
            </div>
          </>
        )}

        {!exitAsk && step === "review" && (
          <>
            <h3>Review setup plan</h3>
            {needed.length === 0 ? (
              <p>Every essential file is already on this computer. Adept UI will reuse them and check the image and video workflows.</p>
            ) : (
              <>
                <p>Adept UI will install:</p>
                <ul>{needed.map((item) => <li key={item.id}>{item.name}</li>)}</ul>
                <p>Already installed components will be reused.</p>
              </>
            )}
            <p>Estimated download: {formatBytes(scan?.estimatedDownloadBytes ?? 0)}</p>
            <p>Estimated storage: {formatBytes(scan?.estimatedInstallBytes ?? 0)}</p>
            {scan?.storageShortfall && (
              <p className="setup-issue">There is not enough free space for this install. Free some space, then scan again. Nothing has been downloaded.</p>
            )}
            <div className="row-actions">
              <button type="button" className="ghost" onClick={() => setStep("needs")}>Back</button>
              <button
                type="button"
                className="primary"
                data-testid="setup-wizard-begin"
                disabled={Boolean(scan?.storageShortfall) || installing}
                onClick={() => void runInstall().catch(() => setStep("blocked"))}
              >
                Begin Setup
              </button>
            </div>
          </>
        )}

        {!exitAsk && step === "install" && (
          <>
            <h3>Installing</h3>
            <p>Preparing Adept UI…</p>
            <ul>
              {[...already, ...needed].map((item) => {
                const component = byId.get(item.id);
                const known = typeof component?.progress === "number";
                const percent = known
                  ? Math.round((component?.progress ?? 0) <= 1 ? (component?.progress ?? 0) * 100 : (component?.progress ?? 0))
                  : null;
                return (
                  <li key={item.id}>
                    {item.name} · {lineState(component, already.some((row) => row.id === item.id))}
                    {percent != null ? ` · ${percent}%` : ""}
                  </li>
                );
              })}
            </ul>
            {overall != null && <p>Overall progress: {overall}%</p>}
          </>
        )}

        {!exitAsk && step === "verify" && (
          <>
            <h3>Verifying</h3>
            <p>Checking essential image and video workflows…</p>
          </>
        )}

        {!exitAsk && step === "done" && (
          <>
            <h3>Setup complete</h3>
            <p>Adept UI is ready.</p>
            <ul>
              <li>✓ Essential runtime ready</li>
              <li>✓ Image generation ready</li>
              <li>✓ Video generation ready</li>
              <li>✓ Setup verified</li>
              <li>Essential blockers: {scan?.essentialBlockerCount ?? 0}</li>
            </ul>
            <div className="row-actions">
              <button type="button" className="primary" data-testid="setup-wizard-finish" onClick={onFinish}>
                Finish
              </button>
            </div>
          </>
        )}

        {!exitAsk && step === "blocked" && (
          <>
            <h3>Setup still needs attention</h3>
            <ul>{needed.map((item) => <li key={item.id}>{plainNeed(item)}</li>)}</ul>
            {(scan?.essentialBlockerCount ?? 0) > 0 && needed.length === 0 && (
              <p>The files are present, but an essential workflow is not ready yet. Adept UI will check again.</p>
            )}
            <p>Essential blockers: {scan?.essentialBlockerCount ?? 0}</p>
            <button type="button" className="linkish" onClick={() => setDetailsOpen((open) => !open)}>
              {detailsOpen ? "Hide details" : "View details"}
            </button>
            {detailsOpen && (
              <ul>
                {needed.map((item) => (
                  <li key={item.id}>{item.name}{item.status ? ` (${item.status})` : ""}</li>
                ))}
              </ul>
            )}
            <div className="row-actions">
              <button
                type="button"
                className="primary"
                onClick={() => void runInstall().catch(() => setStep("blocked"))}
              >
                Retry
              </button>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
