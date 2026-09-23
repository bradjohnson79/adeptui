import { useEffect, useRef, useState } from "react";
import { useTimelineContextPackage } from "./useTimelineContextPackage";
import type { Project, Scene } from "../../types";
import type { TimelinePreflightFinding, TimelinePreflightStatus } from "../../timelineMaster/useTimelinePreflight";

type DepartmentStatus = "ready" | "not_required" | "blocked" | "advisory";

type Department = {
  category: string;
  status: DepartmentStatus;
  reason: string;
  resolved: number;
  required: number;
  items: string[];
  missing: string[];
};

function statusLabel(status: DepartmentStatus | undefined, fallbackReady: boolean) {
  if (status === "ready") return "READY";
  if (status === "not_required") return "NOT REQUIRED";
  if (status === "advisory") return "ADVISORY";
  if (status === "blocked") return "BLOCKED";
  return fallbackReady ? "READY" : "ADVISORY";
}

function DepartmentBlock({
  title,
  testId,
  dept,
  fallbackReady,
}: {
  title: string;
  testId: string;
  dept?: Department;
  fallbackReady: boolean;
}) {
  const status = statusLabel(dept?.status, fallbackReady);
  return (
    <div data-testid={testId}>
      <strong>{title}</strong>
      <div className="scene-meta" data-testid={`${testId}-status`}>
        {status}
      </div>
      {dept?.reason ? <div className="scene-meta">{dept.reason}</div> : null}
      {dept?.status === "ready" && dept.items.length > 0 ? (
        <ul className="scene-meta" data-testid={`${testId}-items`}>
          {dept.items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : null}
      {(dept?.status === "blocked" || dept?.status === "advisory") && dept.missing.length > 0 ? (
        <ul className="scene-meta" data-testid={`${testId}-missing`}>
          {dept.missing.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

/**
 * SceneProductionReadinessPanel — live scene bindings, not chat snapshots.
 * Preflight can force a fresh evaluation; opening Timeline already computes it.
 */
export function SceneProductionReadinessPanel({
  project,
  scene,
  reloadKey = 0,
  preflightStatus = "idle",
  preflightSummary = "",
  preflightFindings = [],
  onRunPreflight,
}: {
  project: Project;
  scene: Scene;
  reloadKey?: number;
  preflightStatus?: TimelinePreflightStatus;
  preflightSummary?: string;
  preflightFindings?: TimelinePreflightFinding[];
  onRunPreflight?: () => void | Promise<void>;
}) {
  const { pkg, loading, error, refresh } = useTimelineContextPackage(
    project.id,
    scene.id,
    "production",
    reloadKey,
  );
  const [running, setRunning] = useState(false);
  const checking = running || preflightStatus === "checking";
  const prevPreflightStatus = useRef(preflightStatus);

  useEffect(() => {
    const prev = prevPreflightStatus.current;
    prevPreflightStatus.current = preflightStatus;
    if (
      prev === "checking" &&
      (preflightStatus === "ready" || preflightStatus === "blocked" || preflightStatus === "error")
    ) {
      refresh();
    }
  }, [preflightStatus, refresh]);

  const run = async () => {
    if (!onRunPreflight || checking) return;
    setRunning(true);
    try {
      await onRunPreflight();
    } finally {
      setRunning(false);
    }
  };

  const p = pkg?.package ?? (pkg?.ok && pkg.package ? pkg.package : null);
  const r = p?.readiness;
  const departments = r?.departments || [];
  const byCategory = (category: string) => departments.find((d) => d.category === category);
  const advisoryCount = departments.filter((d) => d.status === "advisory").length;
  const technicalLock = p?.gateLevel === "PRODUCTION_LOCK" && advisoryCount === 0 && r?.status === "BLOCKED";
  const statusText =
    technicalLock
      ? String(r?.status || "BLOCKED")
      : advisoryCount > 0
        ? `Ready with ${advisoryCount} advisories`
        : r?.status === "READY"
          ? "Ready"
          : r?.status || "—";
  const gateLabel = technicalLock ? "Locked" : advisoryCount > 0 ? "Open" : p?.gateLevel === "PRODUCTION_WARNING" ? "Open" : p ? "Open" : "—";
  const advisoryFindings = preflightFindings.filter((finding) =>
    ["warning", "advisory", "info"].includes(String(finding.severity || "").toLowerCase()),
  );
  const generatorFinding = preflightFindings.find((f) =>
    /^(missing_generator|generator_not_ready)$/i.test(String(f.code || "")),
  );
  const promptFinding = preflightFindings.find((f) =>
    /^(missing_prompt|empty_prompt)$/i.test(String(f.code || "")),
  );
  const continuityFinding = preflightFindings.find((f) =>
    /continuity|stale|bridge/i.test(`${f.code || ""} ${f.message || ""}`),
  );

  return (
    <div className="timeline-inspector__stack" data-testid="scene-readiness-panel">
      <strong>Production Readiness</strong>
      <div className="timeline-inspector__label">
        <button
          type="button"
          className="primary"
          data-testid="timeline-inspector-preflight"
          title="Check this scene now — Cast, Location, References, Voice, generator, and prompts"
          disabled={!onRunPreflight || checking}
          onClick={() => void run()}
        >
          {checking ? "Checking…" : "Preflight"}
        </button>
      </div>
      {preflightStatus === "error" ? (
        <p className="scene-meta" data-testid="timeline-preflight-offline">
          {preflightSummary || "Preflight is offline. The button stays here — try again when Runtime is back."}
        </p>
      ) : advisoryFindings.length > 0 && preflightSummary ? (
        <details className="timeline-preflight-advisory" data-testid="timeline-preflight-advisory">
          <summary className="scene-meta" data-testid="timeline-preflight-summary">
            {preflightSummary}
          </summary>
          <ul className="scene-meta" data-testid="timeline-preflight-advisory-list">
            {advisoryFindings.map((finding, index) => (
              <li key={`${finding.code || "advisory"}-${index}`}>{finding.message}</li>
            ))}
          </ul>
        </details>
      ) : preflightSummary ? (
        <p className="scene-meta" data-testid="timeline-preflight-summary">
          {preflightSummary}
        </p>
      ) : null}
      {loading && !r ? <p className="scene-meta">Checking readiness…</p> : null}
      {error && !r ? (
        <p className="scene-meta" data-testid="scene-readiness-unavailable">
          {error}
        </p>
      ) : null}
      {r ? (
        <>
          <div className="scene-meta">
            Status: <span data-testid="scene-readiness-status">{statusText}</span>
            {technicalLock ? (
              <>
                {" "}
                · Gate: <span data-testid="scene-readiness-gate">{gateLabel}</span>
              </>
            ) : (
              <>
                {" "}
                · Gate: <span data-testid="scene-readiness-gate">{gateLabel}</span>
              </>
            )}
          </div>
          {r.blockerSummary ? (
            <p className="scene-meta" data-testid="scene-readiness-blocker">
              {r.blockerSummary}
            </p>
          ) : null}
          <div className="timeline-inspector__meta-grid">
            <DepartmentBlock
              title="Location"
              testId="scene-readiness-location"
              dept={byCategory("location")}
              fallbackReady={Boolean(r.locationReady)}
            />
            <DepartmentBlock
              title="References"
              testId="scene-readiness-references"
              dept={byCategory("references")}
              fallbackReady={Boolean(r.imageReferencesReady)}
            />
            <DepartmentBlock
              title="Cast"
              testId="scene-readiness-cast"
              dept={byCategory("cast")}
              fallbackReady={Boolean(r.castReady)}
            />
            <DepartmentBlock
              title="Voice"
              testId="scene-readiness-voice"
              dept={byCategory("voice")}
              fallbackReady={Boolean(r.voiceReady)}
            />
            <div>
              <strong>Generator</strong>
              <div className="scene-meta">
                {generatorFinding
                  ? generatorFinding.message
                  : preflightStatus === "ready"
                    ? "Ready"
                    : preflightStatus === "blocked"
                      ? "Needs attention"
                      : "Run Preflight"}
              </div>
            </div>
            <div>
              <strong>Timed Prompt</strong>
              <div className="scene-meta">
                {promptFinding
                  ? promptFinding.message
                  : "Timed Prompts are authored on the scene timeline."}
              </div>
            </div>
            {continuityFinding ? (
              <div>
                <strong>Continuity</strong>
                <div className="scene-meta">{continuityFinding.message}</div>
              </div>
            ) : null}
          </div>
        </>
      ) : null}
    </div>
  );
}
