/**
 * Capability readiness UI.
 *
 * Everything here reads `GET /api/capabilities` and renders exactly what the backend
 * reported. Two rules the components must not break:
 *
 * 1. No derived readiness. If the panel wants to say "generation is blocked", it says so
 *    because a capability came back `blocked`, not because it inspected model paths itself.
 * 2. No silent side effects. Blocker actions navigate (Source Manager, the Setup Wizard card
 *    for a component) or re-probe. Nothing here starts a download.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { buildAiGuidedSetupPath } from "../setup/navigation";
import { shouldSuspendDependentPolling } from "../runtime/studioApiConnection";
import {
  type Capability,
  type CapabilityBlocker,
  type CapabilitySnapshot,
  capabilityStatusLabel,
  recommendedActionLabel,
} from "../capabilities";
import { Button, ReadinessMeter, SectionHeader, StatusBadge } from "./ui";
import { mapCapabilityStatus } from "../status";

/** Capability ids the Setup Wizard treats as required before it may claim readiness. */
export const REQUIRED_FOR_GENERATION = [
  "storage.project_data",
  "storage.database",
  "comfyui.health",
  "models.video.ready",
  "workflows.video.ready",
];

export function useCapabilities(options?: { projectId?: string; pollMs?: number }) {
  const projectId = options?.projectId;
  const pollMs = options?.pollMs ?? 0;
  const [snapshot, setSnapshot] = useState<CapabilitySnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(
    async (refresh = false) => {
      setBusy(true);
      try {
        const next = refresh
          ? await api.refreshCapabilities(projectId)
          : await api.capabilities({ projectId });
        setSnapshot(next);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not read capabilities.");
      } finally {
        setBusy(false);
      }
    },
    [projectId],
  );

  useEffect(() => {
    let alive = true;
    const tick = () => {
      if (!alive) return;
      if (shouldSuspendDependentPolling()) return;
      void load();
    };
    tick();
    if (!pollMs) return () => {
      alive = false;
    };
    const id = setInterval(tick, pollMs);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [load, pollMs]);

  return { snapshot, error, busy, reload: load };
}

/**
 * Where a blocker's recommended action should take the operator. Component-specific actions
 * deep-link to the Setup Wizard card for the first named component; everything else lands on
 * the Source Manager, which is where sources are added.
 */
function actionTarget(blocker: CapabilityBlocker, projectId?: string): string | null {
  const componentId = blocker.componentIds[0];
  const setupTarget = buildAiGuidedSetupPath({
    projectId,
    componentId,
    source: "source_manager",
  });
  switch (blocker.recommendedAction) {
    case "open_source_manager":
      return projectId
        ? `/source-manager?projectId=${encodeURIComponent(projectId)}`
        : "/source-manager";
    case "add_source_url":
      return setupTarget;
    case "install_comfyui_extensions":
      return setupTarget;
    case "verify_model_path":
    case "run_diagnostics":
      return setupTarget;
    default:
      return null;
  }
}

function BlockerRow({ blocker, projectId }: { blocker: CapabilityBlocker; projectId?: string }) {
  const target = actionTarget(blocker, projectId);
  const actionLabel = recommendedActionLabel(blocker.recommendedAction);
  return (
    <li className="capability-blocker" data-testid={`capability-blocker-${blocker.capabilityId}`}>
      <div className="capability-blocker-head">
        <StatusBadge kind={mapCapabilityStatus(blocker.status)} label={capabilityStatusLabel(blocker.status)} />
        <strong>{blocker.displayName}</strong>
        {blocker.reasonCode && <code className="capability-reason">{blocker.reasonCode}</code>}
      </div>
      <p className="capability-blocker-message">{blocker.message}</p>
      {blocker.componentIds.length > 0 && (
        <p className="muted capability-components">
          Components: {blocker.componentIds.join(", ")}
        </p>
      )}
      {actionLabel && target && (
        <Link className="capability-action" to={target} data-testid={`capability-action-${blocker.capabilityId}`}>
          {actionLabel}
        </Link>
      )}
      {actionLabel && !target && <span className="muted">{actionLabel}</span>}
    </li>
  );
}

/**
 * Full readiness card: status counts, blockers with actions, and an explicit re-probe.
 * Used on Home (system status) and on the Source Manager page.
 */
export function CapabilityReadinessPanel({
  projectId,
  subsystems,
  title = "Capability Readiness",
  limit = 8,
}: {
  projectId?: string;
  /** When set, only blockers from these subsystems are listed. */
  subsystems?: string[];
  title?: string;
  limit?: number;
}) {
  const { snapshot, error, busy, reload } = useCapabilities({ projectId, pollMs: 30000 });

  const blockers = useMemo(() => {
    if (!snapshot) return [];
    const all = snapshot.blockers;
    return subsystems ? all.filter((item) => subsystems.includes(item.subsystem)) : all;
  }, [snapshot, subsystems]);

  const readinessTotal = snapshot?.readinessTotal ?? snapshot?.capabilities.length ?? 0;
  const readyCount = snapshot?.callable.length ?? 0;
  const blockedCount = blockers.length;
  const deferredCount = snapshot?.deferred?.length ?? snapshot?.counts.deferred_version_1_2 ?? 0;
  const notInstalledCount = Math.max(0, readinessTotal - readyCount - blockedCount);
  const [showReadinessHelp, setShowReadinessHelp] = useState(false);
  const unavailableByDesign = deferredCount;
  const notApplicable = Math.max(
    0,
    (snapshot?.capabilities.length ?? 0) - readinessTotal,
  );
  const notTested = snapshot?.counts?.unknown ?? 0;

  return (
    <section className="dash-card ds-surface capability-panel" data-testid="capability-panel">
      <SectionHeader
        title={title}
        actions={
          <Button
            type="button"
            variant="secondary"
            compact
            onClick={() => void reload(true)}
            disabled={busy}
            data-testid="capability-refresh"
          >
            {busy ? "Checking…" : "Refresh"}
          </Button>
        }
      />

      {error && (
        <p className="setup-issue" data-testid="capability-error">
          {error}
        </p>
      )}

      {!snapshot && !error && <p className="muted">Checking what this studio can do…</p>}

      {snapshot && (
        <>
          <p className="capability-summary" data-testid="capability-summary">
            <strong data-testid="capability-callable-count">{readyCount}</strong> Ready
            {" · "}
            <strong data-testid="capability-blocker-count">{blockedCount}</strong> Blocked
            {" · "}
            <strong data-testid="capability-deferred-count">{deferredCount}</strong> Deferred
            {" · "}
            <strong data-testid="capability-not-installed-count">{notInstalledCount}</strong> Not installed
            {snapshot.readinessTotal ? ` · ${readinessTotal} readiness-tracked` : ` · ${snapshot.capabilities.length} total`}
            .
            {" "}
            <button
              type="button"
              className="linkish"
              onClick={() => setShowReadinessHelp((value) => !value)}
              data-testid="capability-readiness-help-toggle"
            >
              {showReadinessHelp ? "Hide count details" : "What do these counts mean?"}
            </button>
          </p>
          {showReadinessHelp ? (
            <div className="capability-readiness-help" data-testid="capability-readiness-help">
              <p>
                Counts use the readiness-tracked denominator ({readinessTotal}), not every future or
                platform-inapplicable capability in the full registry.
              </p>
              <ul>
                <li><strong>Ready</strong> — usable now ({readyCount})</li>
                <li><strong>Blocked</strong> — missing install, source, or runtime ({blockedCount})</li>
                <li><strong>Not installed</strong> — tracked but not yet ready ({notInstalledCount})</li>
                <li><strong>Unavailable by design</strong> — deferred / roadmap ({unavailableByDesign})</li>
                <li><strong>Not applicable</strong> — outside this platform readiness set ({notApplicable})</li>
                <li><strong>Not tested</strong> — probe unknown / incomplete ({notTested})</li>
              </ul>
            </div>
          ) : null}
          <ReadinessMeter
            readyCount={readyCount}
            totalCount={readinessTotal}
            blockedCount={blockedCount}
            kind={blockedCount ? "NeedsAttention" : "Ready"}
            summary="Capability readiness"
          />

          {blockedCount === 0 ? (
            <p className="muted" data-testid="capability-no-blockers">
              Nothing is blocked. Anything not listed as usable is simply not implemented or not
              verified yet — see the capability matrix.
            </p>
          ) : (
            <ul className="capability-blockers" data-testid="capability-blockers">
              {blockers.slice(0, limit).map((blocker) => (
                <BlockerRow key={blocker.capabilityId} blocker={blocker} projectId={projectId} />
              ))}
            </ul>
          )}

          {blockers.length > limit && (
            <p className="muted">…and {blockers.length - limit} more blocked capabilities.</p>
          )}

          {snapshot.probeWarnings.length > 0 && (
            <p className="muted" data-testid="capability-probe-warnings">
              Some checks could not complete: {snapshot.probeWarnings.join(", ")}. Affected
              capabilities are reported as unknown rather than guessed.
            </p>
          )}

          <p className="muted capability-footnote">
            Last checked {new Date(snapshot.generatedAt).toLocaleTimeString()}. Refresh re-probes
            the environment; it never starts a download.
          </p>
        </>
      )}
    </section>
  );
}

/**
 * Compact readiness pill for the app chrome. Deliberately reports the count of blocked
 * capabilities rather than a single "OK" — a green light with a blocked dependency behind it
 * is the failure mode this whole registry exists to prevent.
 */
export function CapabilityStatusBadge({
  projectId,
  onClick,
}: {
  projectId?: string;
  onClick?: () => void;
}) {
  const { snapshot, error } = useCapabilities({ projectId, pollMs: 30000 });

  const interactive = onClick ? { onClick } : {};
  if (error) {
    return (
      <StatusBadge
        kind="Unknown"
        label="Capabilities unknown"
        data-testid="capability-badge"
        {...interactive}
      />
    );
  }
  if (!snapshot) {
    return (
      <StatusBadge
        kind="Checking"
        label="Capabilities…"
        data-testid="capability-badge"
        {...interactive}
      />
    );
  }
  const blocked = snapshot.blockers.length;
  const title = blocked
    ? snapshot.blockers.map((item) => `${item.displayName}: ${item.message}`).join("\n")
    : "No blocked capabilities";
  return (
    <StatusBadge
      kind={blocked ? "NeedsAttention" : "Ready"}
      label={blocked ? `${blocked} Capability Blocker${blocked === 1 ? "" : "s"}` : "Capabilities Ready"}
      data-testid="capability-badge"
      title={title}
      {...interactive}
    />
  );
}

/** Blockers among the capabilities the Setup Wizard treats as required. */
export function requiredBlockers(snapshot: CapabilitySnapshot | null): CapabilityBlocker[] {
  if (!snapshot) return [];
  return snapshot.blockers.filter((blocker) => REQUIRED_FOR_GENERATION.includes(blocker.capabilityId));
}

export function capabilityById(
  snapshot: CapabilitySnapshot | null,
  capabilityId: string,
): Capability | null {
  if (!snapshot) return null;
  return snapshot.capabilities.find((item) => item.id === capabilityId) ?? null;
}
