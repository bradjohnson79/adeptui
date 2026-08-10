import { useEffect, useMemo, useState } from "react";
import { api } from "../../api";
import type { InstallJob } from "../../contracts/installJobs";
import type {
  LifecycleCloudProvider,
  LifecycleInstallPlan,
  SetupComponentStatus,
  SetupStatusResponse,
} from "../types";

function matchesIntent(component: SetupComponentStatus, brief: string): boolean {
  const q = brief.trim().toLowerCase();
  if (!q) return true;
  const parts = [
    component.name,
    component.description,
    ...(component.capabilityTags || []),
    ...(component.badges || []),
    ...(component.bestFor || []),
    ...(component.strengths || []),
  ]
    .join(" ")
    .toLowerCase();
  // Creator briefs are phrases ("anime poster"); match if any meaningful term hits metadata.
  const stop = new Set(["a", "an", "the", "for", "and", "or", "to", "of", "with"]);
  const terms = q.split(/\s+/).filter((term) => term && !stop.has(term));
  if (!terms.length) return true;
  return terms.some((term) => parts.includes(term));
}

function creatorRecommendation(component: SetupComponentStatus, brief: string): string {
  const text = brief.toLowerCase();
  if (component.id === "flux1_kontext_dev_local" && (text.includes("photoreal") || text.includes("character"))) {
    return "Best match for photoreal character work with reference-following edits.";
  }
  if (
    ["sana_15_local", "qwen_image_2512_models", "zimage_models", "pack_essential_anime"].includes(component.id)
    && text.includes("anime")
  ) {
    return "Strong fit for anime and stylized illustration work.";
  }
  if (component.id === "flux1_schnell_local" && (text.includes("preview") || text.includes("fast"))) {
    return "Best fit for quick creative previews before a final-quality pass.";
  }
  return component.lifecycle?.recommendations?.[0] || "Matches this setup goal and current certified posture.";
}

function statusTone(component: SetupComponentStatus): string {
  const label = (component.lifecycle_status_label || component.lifecycle?.statusLabel || "").toLowerCase();
  if (label.includes("ready")) return "ready";
  if (label.includes("repair")) return "attention";
  if (label.includes("update")) return "attention";
  return "missing";
}

export function AiGuidedSetupPanel({
  projectId,
  focusComponentId,
  status,
  installJobsByComponent,
  onInstall,
  onRepair,
  onVerify,
}: {
  projectId?: string;
  focusComponentId?: string;
  status: SetupStatusResponse;
  installJobsByComponent: Record<string, InstallJob>;
  onInstall: (component: SetupComponentStatus) => void;
  onRepair: (component: SetupComponentStatus) => void;
  onVerify: (component: SetupComponentStatus) => void;
}) {
  const [brief, setBrief] = useState("photoreal character");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [plan, setPlan] = useState<LifecycleInstallPlan | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [cloudProviders, setCloudProviders] = useState<LifecycleCloudProvider[]>([]);
  const [monitorItems, setMonitorItems] = useState<Array<{ componentId: string; statusLabel: string; findings: Array<{ message: string }> }>>([]);

  useEffect(() => {
    void Promise.all([
      api.setupLifecycleCloudProviders().then((data) => setCloudProviders(data.items || [])),
      api.setupLifecycleMonitor().then((data) => setMonitorItems(data.items || [])),
    ]).catch((error: unknown) => setMessage(error instanceof Error ? error.message : String(error)));
  }, [projectId]);

  const focusedComponent = useMemo(
    () => status.components.find((component) => component.id === focusComponentId) || null,
    [focusComponentId, status.components],
  );

  const grouped = useMemo(() => {
    const buckets = new Map<string, Map<string, SetupComponentStatus[]>>();
    status.components.forEach((component) => {
      const groups = component.surfaceGroups?.length ? component.surfaceGroups : [component.group || "Utilities"];
      const subgroup = component.subgroup || "General";
      groups.forEach((group) => {
        if (!buckets.has(group)) buckets.set(group, new Map());
        const groupMap = buckets.get(group)!;
        if (!groupMap.has(subgroup)) groupMap.set(subgroup, []);
        const items = groupMap.get(subgroup)!;
        if (!items.some((item) => item.id === component.id)) items.push(component);
      });
    });
    return Array.from(buckets.entries());
  }, [status.components]);

  const recommended = useMemo(() => {
    const ranked = status.components
      .filter((component) => matchesIntent(component, brief))
      .sort((a, b) => {
        const preferred = (id: string) =>
          id === "flux1_kontext_dev_local" ? 0
          : id === "sana_15_local" ? 1
          : id === "qwen_image_2512_models" ? 2
          : id === "zimage_models" ? 3
          : 9;
        return preferred(a.id) - preferred(b.id);
      });
    if (focusedComponent && !ranked.some((component) => component.id === focusedComponent.id)) {
      ranked.unshift(focusedComponent);
    }
    return ranked.slice(0, 4);
  }, [brief, focusedComponent, status.components]);

  const toggleSelected = (componentId: string) => {
    setSelectedIds((current) =>
      current.includes(componentId)
        ? current.filter((item) => item !== componentId)
        : current.length >= 2
          ? [current[1], componentId]
          : [...current, componentId]
    );
  };

  const openPlan = async (componentId: string, action = "install") => {
    try {
      setPlan(await api.setupLifecycleInstallPlan({ componentId, action }));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    }
  };

  const compareSummary = useMemo(() => {
    if (selectedIds.length < 2) return null;
    const first = status.components.find((item) => item.id === selectedIds[0]);
    const second = status.components.find((item) => item.id === selectedIds[1]);
    if (!first || !second) return null;
    return `${first.name} vs ${second.name}`;
  }, [selectedIds, status.components]);

  return (
    <section
      className="setup-component-section"
      aria-labelledby="ai-guided-setup-heading"
      data-project-id={projectId || undefined}
    >
      <div className="setup-section-heading">
        <div>
          <h2 id="ai-guided-setup-heading">AI-Guided Setup</h2>
          <p>Describe the kind of work you want to do, then review certified options, install plans, and safety checks.</p>
        </div>
      </div>

      <div className="panel">
        <label className="field">
          <span>What are you trying to create?</span>
          <input
            value={brief}
            onChange={(event) => setBrief(event.target.value)}
            placeholder="photoreal character, anime poster, fast preview, product mockup"
          />
        </label>
        <p className="muted">Try prompts like `photoreal character`, `anime poster`, or `fast preview`.</p>
        {focusedComponent ? (
          <p className="muted">
            Opened for <strong>{focusedComponent.name}</strong>. Review the plan here, then let Source Manager run the approved install or repair.
          </p>
        ) : null}
      </div>

      {message && <div className="setup-message" role="status">{message}</div>}

      <div className="setup-component-section">
        <div className="setup-section-heading">
          <div>
            <h3>Recommended For This Goal</h3>
            <p>Recommendations prefer certified recipes and creator-facing fit, not uncertified upstream latest.</p>
          </div>
          {compareSummary && <span>{compareSummary}</span>}
        </div>
        <div className="setup-component-grid">
          {recommended.map((component) => (
            <article key={component.id} className={`setup-component-card status-${statusTone(component)}`}>
              <header className="setup-card-header">
                <div>
                  <h3>{component.name}</h3>
                  <span className="setup-requirement">{component.lifecycle_status_label || component.lifecycle?.statusLabel || "Not Installed"}</span>
                </div>
                <button type="button" className="linkish" onClick={() => toggleSelected(component.id)}>
                  {selectedIds.includes(component.id) ? "Selected" : "Compare"}
                </button>
              </header>
              <p className="setup-component-description">{creatorRecommendation(component, brief)}</p>
              <div className="setup-card-meta">
                {component.parameterCount && <span>{component.parameterCount}</span>}
                {component.vramRecommendationGb != null && <span>{component.vramRecommendationGb} GB VRAM</span>}
                {component.typicalGenerationSpeed && <span>{component.typicalGenerationSpeed}</span>}
                {component.certified_version && <span>Certified {component.certified_version}</span>}
              </div>
              {component.badges?.length ? <p className="muted">{component.badges.join(" · ")}</p> : null}
              {component.bestFor?.length ? <p><strong>Best For</strong> {component.bestFor.join(" · ")}</p> : null}
              <div className="row-actions">
                <button
                  type="button"
                  className="primary"
                  onClick={() => (
                    component.status === "error" || (component.lifecycle_status_label || "").toLowerCase().includes("repair")
                      ? onRepair(component)
                      : onInstall(component)
                  )}
                >
                  {component.status === "error" || (component.lifecycle_status_label || "").toLowerCase().includes("repair") ? "Repair" : "Install"}
                </button>
                <button type="button" className="linkish" onClick={() => void openPlan(component.id, component.status === "error" ? "repair" : "install")}>
                  Review Plan
                </button>
                <button type="button" className="linkish" onClick={() => onVerify(component)}>
                  Verify
                </button>
                <button
                  type="button"
                  className="linkish"
                  onClick={() => {
                    void api.setupLifecycleCalibrate(component.id)
                      .then(() => api.setupLifecycleCertify(component.id))
                      .then(() => setMessage(`${component.name} calibration and certification recorded.`))
                      .catch((error: unknown) => setMessage(error instanceof Error ? error.message : String(error)));
                  }}
                >
                  Calibrate + Certify
                </button>
              </div>
              {installJobsByComponent[component.id] && (
                <p className="muted">
                  Current progress: {installJobsByComponent[component.id].progress?.phaseLabel || installJobsByComponent[component.id].state}
                </p>
              )}
            </article>
          ))}
        </div>
      </div>

      {plan && (
        <details className="panel" open>
          <summary>{plan.componentName} plan</summary>
          <p className="muted">
            {plan.requiresRuntimeConfirmation ? "Runtime confirmation required." : "Runtime confirmation not required."}{" "}
            {plan.requiresModelDownloadConfirmation ? "Model download confirmation required." : "No extra model download confirmation required."}
          </p>
          <ul>
            {plan.steps.map((step) => <li key={step}>{step}</li>)}
          </ul>
          {plan.warnings.length > 0 && <p className="setup-issue"><strong>Warnings</strong> {plan.warnings.join(" · ")}</p>}
        </details>
      )}

      <div className="setup-component-section">
        <div className="setup-section-heading">
          <div>
            <h3>Lifecycle Groups</h3>
            <p>Expandable groups keep the catalog creator-friendly while still exposing all certified and experimental options.</p>
          </div>
        </div>
        {grouped.map(([group, subgroups]) => (
          <details key={group} className="panel" open={group === "Image"}>
            <summary>{group}</summary>
            {Array.from(subgroups.entries()).map(([subgroup, components]) => (
              <div key={`${group}-${subgroup}`} className="setup-component-section">
                <div className="setup-section-heading">
                  <div>
                    <h3>{subgroup}</h3>
                    <p>{subgroup === "Cloud Providers" ? "Commercial providers stay separate from local installs." : "Use verified installs and certified recipes where available."}</p>
                  </div>
                </div>
                <div className="setup-component-grid">
                  {components.slice(0, 8).map((component) => (
                    <article key={component.id} className={`setup-component-card status-${statusTone(component)}`}>
                      <header className="setup-card-header">
                        <div>
                          <h3>{component.name}</h3>
                          <span className="setup-requirement">{component.lifecycle_status_label || component.lifecycle?.statusLabel || component.status}</span>
                        </div>
                      </header>
                      <p className="setup-component-description">{component.description}</p>
                      <div className="setup-card-meta">
                        {component.downloadSizeLabel && <span>{component.downloadSizeLabel}</span>}
                        {component.diskUsageLabel && <span>{component.diskUsageLabel}</span>}
                        {component.vramRecommendationGb != null && <span>{component.vramRecommendationGb} GB VRAM</span>}
                      </div>
                      {(component.monitor_findings || []).length ? (
                        <p className="setup-issue"><strong>Monitor</strong> {(component.monitor_findings || []).map((item) => item.message).join(" · ")}</p>
                      ) : null}
                    </article>
                  ))}
                </div>
              </div>
            ))}
          </details>
        ))}
      </div>

      <div className="setup-component-section">
        <div className="setup-section-heading">
          <div>
            <h3>Cloud Providers</h3>
            <p>These stay separate from local installs and never silently replace local certified recipes.</p>
          </div>
        </div>
        <div className="setup-component-grid">
          {cloudProviders.map((provider) => (
            <article key={provider.providerId} className="setup-component-card">
              <header className="setup-card-header">
                <div>
                  <h3>{provider.displayName}</h3>
                  <span className="setup-requirement">{provider.statusLabel}</span>
                </div>
              </header>
              <p className="setup-component-description">
                {(provider.modelFamilies || []).join(" · ") || "Commercial image provider"}
              </p>
              <div className="setup-card-meta">
                <span>{provider.configured ? "Configured" : "Needs credentials"}</span>
                {(provider.operations || []).length > 0 && <span>{provider.operations?.join(", ")}</span>}
              </div>
            </article>
          ))}
        </div>
      </div>

      {monitorItems.length > 0 && (
        <div className="panel">
          <h3>Monitor Warnings</h3>
          <ul>
            {monitorItems.map((item) => (
              <li key={item.componentId}>
                <strong>{item.componentId}</strong> {item.statusLabel}: {item.findings.map((finding) => finding.message).join(" · ")}
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="setup-nav-strip">
        Source Manager runs verified sources, download jobs, and reviewed install actions after you
        approve them here in Setup.
      </p>
    </section>
  );
}

