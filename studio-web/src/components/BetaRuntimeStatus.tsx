import { useEffect, useState } from "react";
import { api } from "../api";
import { StatusBadge } from "./ui";

type BetaStatus = Awaited<ReturnType<typeof api.betaRuntimeStatus>>;

function kindFor(ok: boolean | undefined, overall?: string) {
  if (overall === "FAILED") return "NeedsAttention" as const;
  if (ok === true) return "Ready" as const;
  if (ok === false) return "NeedsAttention" as const;
  return "Checking" as const;
}

/**
 * Compact V1.1 Beta runtime status — informational only; hidden when not launched via Start-AdeptUI-Beta.
 * Compact / Status menu: overall badge only (API/Comfy live in SystemStatusStrip).
 * Non-compact Home footer: Worker + Web supervisor children (not API/Comfy duplicates).
 */
export function BetaRuntimeStatus({ compact = false }: { compact?: boolean }) {
  const [status, setStatus] = useState<BetaStatus | null>(null);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const s = await api.betaRuntimeStatus();
        if (alive) setStatus(s);
      } catch {
        if (alive) setStatus(null);
      }
    };
    void tick();
    const id = setInterval(() => void tick(), 15000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  if (!status?.active) return null;

  const svc = status.services || {};
  const overall = status.state || "UNKNOWN";
  // Compact Status menu: overall only (API/Comfy already in SystemStatusStrip).
  // Home footer: Worker + Web supervisor children — never duplicate API/Comfy.
  const slim = compact;

  return (
    <div
      className={compact ? "beta-runtime-status compact" : "beta-runtime-status"}
      data-testid="beta-runtime-status"
      role="status"
      aria-label="Beta runtime status"
      style={{
        display: "flex",
        flexWrap: "wrap",
        gap: "0.35rem",
        alignItems: "center",
        marginTop: compact ? 0 : "0.5rem",
      }}
    >
      <StatusBadge
        kind={overall === "READY" ? "Ready" : overall === "DEGRADED" ? "NeedsAttention" : "Checking"}
        label={`Beta ${overall}`}
        data-testid="beta-runtime-overall"
        title={[status.updatedAt, status.logsDir].filter(Boolean).join(" · ")}
      />
      {!slim ? (
        <>
          <StatusBadge
            kind={kindFor(svc.worker?.ok, overall)}
            label="Worker"
            data-testid="beta-runtime-worker"
            title={svc.worker?.role || "in-process"}
          />
          <StatusBadge kind={kindFor(svc.web?.ok, overall)} label="Web" data-testid="beta-runtime-web" />
          <span className="muted" style={{ fontSize: "0.8rem" }}>
            Storage · Image/Video/Audio/Lipsync via /api/health
          </span>
        </>
      ) : null}
    </div>
  );
}
