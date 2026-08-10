import { useEffect, useState } from "react";
import { api } from "../../api";
import type { CapabilityBlocker } from "../../capabilities";
import type { SetupComponentStatus } from "../../setup/types";
import { componentStateLabel } from "../../setup/helpers";
import { Button, Drawer } from "../ui";
import "./install-progress.css";

type NodeResolution = {
  nodeType?: string;
  extensionComponentId?: string | null;
  sourceStatus?: string;
  message?: string;
};

type RequirementsPayload = {
  capabilityId?: string;
  missingNodeTypes?: string[];
  requiredNodeTypes?: string[];
  missingComponentIds?: string[];
  nodeResolutions?: NodeResolution[];
  status?: string;
  message?: string;
  recommendedAction?: string | null;
};

export function RequiredComponentsPanel({
  open,
  blockers,
  components,
  onClose,
  onUseOfficial,
  onAddSource,
  onInstall,
  onRepair,
  onVerify,
  actionLabelFor,
}: {
  open: boolean;
  blockers: CapabilityBlocker[];
  components: SetupComponentStatus[];
  onClose: () => void;
  onUseOfficial: (component: SetupComponentStatus) => void;
  onAddSource: (component: SetupComponentStatus) => void;
  onInstall: (component: SetupComponentStatus) => void;
  onRepair: (component: SetupComponentStatus) => void;
  onVerify: (component: SetupComponentStatus) => void;
  actionLabelFor: (component: SetupComponentStatus) => string;
}) {
  const [requirements, setRequirements] = useState<Record<string, RequirementsPayload>>({});
  const [loadingId, setLoadingId] = useState<string | null>(null);

  const extensionIds = Object.values(requirements).flatMap((req) =>
    (req.nodeResolutions || [])
      .map((item) => item.extensionComponentId)
      .filter((id): id is string => Boolean(id)),
  );
  const componentIds = Array.from(
    new Set([
      ...blockers.flatMap((blocker) => blocker.componentIds || []),
      ...extensionIds,
      "comfyui_hunyuan_nodes",
    ]),
  );
  const relevantComponents = componentIds
    .map((componentId) => components.find((component) => component.id === componentId))
    .filter((component): component is SetupComponentStatus => Boolean(component));
  const blockersWithoutComponents = blockers.filter((blocker) => blocker.componentIds.length === 0);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    const load = async () => {
      const next: Record<string, RequirementsPayload> = {};
      for (const blocker of blockers) {
        try {
          const payload = (await api.installJobs.requiredComponents(blocker.capabilityId)) as RequirementsPayload;
          if (!cancelled) next[blocker.capabilityId] = payload;
        } catch {
          /* keep panel usable even if probe fails */
        }
      }
      if (!cancelled) setRequirements(next);
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [open, blockers]);

  const refreshCapability = async (capabilityId: string) => {
    setLoadingId(capabilityId);
    try {
      const payload = (await api.installJobs.requiredComponents(capabilityId)) as RequirementsPayload;
      setRequirements((current) => ({ ...current, [capabilityId]: payload }));
    } finally {
      setLoadingId(null);
    }
  };

  return (
    <Drawer open={open} onClose={onClose} title="Required components" side="right" testId="required-components-panel">
      <div className="required-components-panel">
        <p className="muted">
          These items are blocking creator workflows. Add a source, install, repair, or verify from here. ComfyUI
          extensions only become ready after the active ComfyUI instance registers their node types.
        </p>

        {blockers.map((blocker) => {
          const req = requirements[blocker.capabilityId];
          const missingNodes = req?.missingNodeTypes || [];
          return (
            <article key={blocker.capabilityId} className="install-inline-card" data-testid={`required-capability-${blocker.capabilityId}`}>
              <div className="install-inline-card__header">
                <div>
                  <h3>{blocker.displayName}</h3>
                  <p>{blocker.message}</p>
                </div>
                <span className="install-progress-card__pill">{req?.status || "blocked"}</span>
              </div>
              {missingNodes.length ? (
                <ul className="required-components-panel__nodes" data-testid={`missing-nodes-${blocker.capabilityId}`}>
                  {missingNodes.map((node) => {
                    const resolution = req?.nodeResolutions?.find((item) => item.nodeType === node);
                    return (
                      <li key={node}>
                        <strong>{node}</strong>
                        <span>Missing</span>
                        {resolution?.sourceStatus ? <span>{resolution.sourceStatus.replace(/_/g, " ")}</span> : null}
                      </li>
                    );
                  })}
                </ul>
              ) : null}
              {req?.message ? <p className="muted tiny">{req.message}</p> : null}
              <div className="install-inline-card__actions">
                <Button
                  variant="secondary"
                  disabled={loadingId === blocker.capabilityId}
                  onClick={() => void refreshCapability(blocker.capabilityId)}
                >
                  {loadingId === blocker.capabilityId ? "Checking…" : "Verify nodes after ComfyUI restart"}
                </Button>
              </div>
            </article>
          );
        })}

        {blockersWithoutComponents.length > 0 ? (
          <div className="required-components-panel__blockers">
            {blockersWithoutComponents.map((blocker) => (
              <article key={`${blocker.capabilityId}-orphan`} className="install-inline-card">
                <h3>{blocker.displayName}</h3>
                <p>{blocker.message}</p>
              </article>
            ))}
          </div>
        ) : null}

        <div className="required-components-panel__list" data-testid="required-components-list">
          {relevantComponents.map((component) => {
            const needsSource = !component.source_available || component.source_valid === false;
            const canRepair = component.status === "error" || component.issue_code === "required_files_missing";
            const isReady = component.status === "ready";
            return (
              <article key={component.id} className="install-inline-card" data-testid={`required-component-${component.id}`}>
                <div className="install-inline-card__header">
                  <div>
                    <h3>{component.name}</h3>
                    <p>{component.description}</p>
                  </div>
                  <span className="install-progress-card__pill">{componentStateLabel(component)}</span>
                </div>
                {component.issue_summary ? (
                  <p className="setup-issue">
                    <strong>Issue</strong> {component.issue_summary}
                  </p>
                ) : null}
                <div className="install-inline-card__actions">
                  {needsSource ? (
                    <>
                      <Button variant="secondary" onClick={() => onUseOfficial(component)}>
                        Use Official
                      </Button>
                      <Button variant="primary" onClick={() => onAddSource(component)}>
                        Add Source URL
                      </Button>
                    </>
                  ) : null}
                  {!isReady && !needsSource ? (
                    <Button variant="primary" onClick={() => onInstall(component)}>
                      {actionLabelFor(component)}
                    </Button>
                  ) : null}
                  {canRepair ? (
                    <Button variant="secondary" onClick={() => onRepair(component)}>
                      Repair
                    </Button>
                  ) : null}
                  <Button variant="ghost" onClick={() => onVerify(component)}>
                    Verify
                  </Button>
                </div>
              </article>
            );
          })}
          {!relevantComponents.length && !blockers.length ? (
            <p className="muted">No blocked components right now.</p>
          ) : null}
        </div>
      </div>
    </Drawer>
  );
}
