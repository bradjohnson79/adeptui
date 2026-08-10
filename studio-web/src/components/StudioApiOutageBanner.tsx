import { useEffect, useState } from "react";
import {
  getStudioApiConnection,
  retryStudioApiConnection,
  subscribeStudioApiConnection,
  type StudioApiConnectionSnapshot,
} from "../runtime/studioApiConnection";

function copySummary(snap: StudioApiConnectionSnapshot) {
  const lines = [
    "Adept UI — Studio API outage summary",
    `state: ${snap.state}`,
    `failureCode: ${snap.failureCode ?? "none"}`,
    `lastError: ${snap.lastError ?? "none"}`,
    `consecutiveFailures: ${snap.consecutiveFailures}`,
    `lastHealthyAt: ${snap.lastHealthyAt ? new Date(snap.lastHealthyAt).toISOString() : "never"}`,
    `lastCheckedAt: ${snap.lastCheckedAt ? new Date(snap.lastCheckedAt).toISOString() : "never"}`,
  ];
  void navigator.clipboard?.writeText(lines.join("\n"));
}

export function StudioApiOutageBanner() {
  const [snap, setSnap] = useState(getStudioApiConnection);
  const [busy, setBusy] = useState(false);

  useEffect(() => subscribeStudioApiConnection(setSnap), []);

  const visible =
    snap.state === "OFFLINE" || snap.state === "RECONNECTING" || snap.state === "RECOVERED" || snap.state === "DEGRADED";
  if (!visible) return null;

  if (snap.state === "RECONNECTING") {
    // Thin status bar for transient reconnection — no blocking overlay
    return (
      <div
        className="studio-api-outage-banner studio-api-outage-banner--transient"
        data-testid="studio-api-outage-banner"
        data-state={snap.state}
        role="status"
        aria-live="polite"
      >
        <span>Reconnecting to Studio API…</span>
        <button
          type="button"
          data-testid="studio-api-outage-retry"
          disabled={busy}
          onClick={() => {
            setBusy(true);
            void retryStudioApiConnection().finally(() => setBusy(false));
          }}
          style={{ marginLeft: "0.5rem", fontSize: "0.8rem" }}
        >
          Retry
        </button>
      </div>
    );
  }

  if (snap.state === "DEGRADED") {
    // Thin yellow bar — API is alive but some dependencies are slow/unavailable
    return (
      <div
        className="studio-api-outage-banner studio-api-outage-banner--transient"
        data-testid="studio-api-outage-banner"
        data-state={snap.state}
        role="status"
        aria-live="polite"
      >
        <span>Studio API partially available — {snap.lastError || "some services degraded"}</span>
        <button
          type="button"
          data-testid="studio-api-outage-copy"
          onClick={() => copySummary(snap)}
          style={{ marginLeft: "0.5rem", fontSize: "0.8rem" }}
        >
          Copy
        </button>
      </div>
    );
  }

  const title =
    snap.state === "RECOVERED" ? "Studio API reconnected" : "Studio API Offline";

  const body =
    snap.state === "RECOVERED"
      ? "Co-Director, Production Assurance, and project synchronization have resumed."
      : "Studio API is currently unavailable. Co-Director, Production Assurance, and project synchronization are paused while Adept UI reconnects.";

  const isRecovered = snap.state === "RECOVERED";
  return (
    <div
      className="studio-api-outage-banner"
      data-testid="studio-api-outage-banner"
      data-state={snap.state}
      role={isRecovered ? "status" : "alert"}
      aria-live="polite"
    >
      <div className="studio-api-outage-banner__text">
        <strong data-testid="studio-api-outage-title">{title}</strong>
        <p>{body}</p>
        {snap.failureCode ? (
          <p className="studio-api-outage-banner__code" data-testid="studio-api-outage-code">
            {snap.failureCode}
          </p>
        ) : null}
      </div>
      <div className="studio-api-outage-banner__actions">
        {!isRecovered ? (
          <button
            type="button"
            data-testid="studio-api-outage-retry"
            disabled={busy}
            onClick={() => {
              setBusy(true);
              void retryStudioApiConnection().finally(() => setBusy(false));
            }}
          >
            Retry connection
          </button>
        ) : null}
        <button
          type="button"
          data-testid="studio-api-outage-copy"
          onClick={() => copySummary(snap)}
        >
          Copy error summary
        </button>
        <a href="/diagnostics/video-runtime" data-testid="studio-api-outage-diagnostic">
          Open diagnostic
        </a>
      </div>
    </div>
  );
}
