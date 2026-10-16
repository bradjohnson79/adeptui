import { useState } from "react";
import type { InstallJob } from "../contracts/installJobs";
import { componentStateLabel, formatComponentSize, progressPercent } from "./helpers";
import type { SetupComponentStatus } from "./types";

export function isSetupModel(component: { category?: string | null }): boolean {
  return /model/i.test(component.category || "");
}

const ACTIVE_JOB = new Set([
  "queued",
  "preparing",
  "downloading",
  "verifying_download",
  "installing",
  "configuring",
  "verifying_install",
  "updating",
]);

export function SetupLocalModels({
  profile,
  components,
  selectedIds,
  jobs,
  busy,
  scanning,
  onInstall,
  onRemove,
  onUpdate,
  onToggleSelected,
  onRescan,
}: {
  profile: string;
  components: SetupComponentStatus[];
  selectedIds: string[];
  jobs: Record<string, InstallJob | undefined>;
  busy: boolean;
  scanning: boolean;
  onInstall: (component: SetupComponentStatus) => void;
  onRemove: (component: SetupComponentStatus) => Promise<void> | void;
  onUpdate: (component: SetupComponentStatus) => void;
  onToggleSelected: (component: SetupComponentStatus, selected: boolean) => void;
  onRescan: () => void;
}) {
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const models = components.filter(isSetupModel);
  const apiOnly = profile === "api";

  return (
    <section className="panel" aria-label="Local Models" data-testid="setup-local-models">
      <h2>Local Models</h2>
      {apiOnly ? (
        <p>Local models are not required for Full API Installation. You can add them after choosing Hybrid or Full Local.</p>
      ) : (
        <p>Installed models stay on this computer. Removing a model asks you to confirm before any files are deleted.</p>
      )}
      <div className="row-actions">
        <button type="button" data-testid="setup-models-rescan" disabled={scanning || busy} onClick={onRescan}>
          {scanning ? "Scanning…" : "Re-scan local models"}
        </button>
      </div>
      {!models.length ? <p className="empty">No local models are listed yet. Re-scan to look again.</p> : null}
      <ul className="setup-model-list">
        {models.map((component) => {
          const job = jobs[component.id];
          const active = Boolean(job && ACTIVE_JOB.has(job.state));
          const percent = progressPercent(job?.progress?.percent ?? component.progress);
          const size = formatComponentSize(component);
          const selected = selectedIds.includes(component.id);
          const usable = component.status === "ready";
          return (
            <li key={component.id} data-testid={`setup-model-${component.id}`}>
              <div>
                <strong>{component.name}</strong>
                <p>
                  {usable ? "Available" : componentStateLabel(component)}
                  {size ? ` · ${size}` : ""}
                  {selected ? " · Selected" : ""}
                </p>
                {active || component.status === "installing" ? (
                  <p role="status">Installing… {Math.round(percent)}%</p>
                ) : null}
              </div>
              <div className="row-actions">
                <label>
                  <input
                    type="checkbox"
                    checked={selected}
                    disabled={busy || apiOnly}
                    data-testid={`setup-model-select-${component.id}`}
                    onChange={(event) => onToggleSelected(component, event.target.checked)}
                  />
                  {" "}Selected
                </label>
                {component.status === "update_available" ? (
                  <button type="button" disabled={busy} data-testid={`setup-model-update-${component.id}`} onClick={() => onUpdate(component)}>
                    Update
                  </button>
                ) : null}
                {usable ? null : (
                  <button type="button" className="primary" disabled={busy || apiOnly} data-testid={`setup-model-install-${component.id}`} onClick={() => onInstall(component)}>
                    Install
                  </button>
                )}
                {usable ? (
                  confirmId === component.id ? (
                    <>
                      <span>Remove {component.name}? Installed files for this model will be deleted.</span>
                      <button
                        type="button"
                        data-testid={`setup-model-remove-confirm-${component.id}`}
                        disabled={busy}
                        onClick={() => {
                          setConfirmId(null);
                          void onRemove(component);
                        }}
                      >
                        Remove this model
                      </button>
                      <button type="button" onClick={() => setConfirmId(null)}>Cancel</button>
                    </>
                  ) : (
                    <button type="button" data-testid={`setup-model-remove-${component.id}`} disabled={busy} onClick={() => setConfirmId(component.id)}>
                      Remove
                    </button>
                  )
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
