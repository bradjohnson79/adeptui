import { useMemo } from "react";
import type { ImageProviderDescriptor } from "../../contracts/cinematicImageStudio";
import { installGuidanceHref, licenseShortName, providerSubLabel } from "./providerDisplay";

function readinessLabel(provider: ImageProviderDescriptor): string {
  if (provider.readiness === "ready") return provider.source === "hosted" ? "API" : "Ready";
  if (provider.readiness === "not_installed") return "Not installed";
  if (provider.readiness === "needs_auth") return "Needs auth";
  if (provider.readiness === "draft") return "Draft";
  return provider.readiness.replace(/_/g, " ");
}

function sourceBadge(provider: ImageProviderDescriptor): "Local" | "API" | "Docker" {
  if (provider.source === "hosted") return "API";
  if (provider.source === "docker") return "Docker";
  return "Local";
}

export function ImageProviderBrowser({
  providers,
  selectedIds,
  bestMatchId,
  onChange,
}: {
  providers: ImageProviderDescriptor[];
  selectedIds: string[];
  bestMatchId?: string | null;
  onChange: (ids: string[]) => void;
}) {
  const selected = useMemo(() => new Set(selectedIds), [selectedIds]);
  const local = providers.filter((p) => p.source === "local" || p.source === "docker");
  const api = providers.filter((p) => p.source === "hosted");

  const setAll = (list: ImageProviderDescriptor[]) => onChange(list.map((p) => p.id));
  const toggle = (id: string) => {
    if (selected.has(id)) onChange(selectedIds.filter((item) => item !== id));
    else onChange([...selectedIds, id]);
  };

  const renderGroup = (title: string, list: ImageProviderDescriptor[]) => (
    <div className="cis-provider-group">
      <h4>{title}</h4>
      <ul>
        {list.map((provider) => {
          const on = selected.has(provider.id);
          const badge = sourceBadge(provider);
          const subLabel = providerSubLabel(provider);
          const licenseShort = licenseShortName(provider.licenseNote);
          const installHref =
            provider.readiness === "not_installed" ? installGuidanceHref(provider) : null;
          return (
            <li key={provider.id}>
              <button
                type="button"
                className={`cis-provider-row${on ? " is-selected" : ""}${
                  provider.readiness !== "ready" ? " is-dim" : ""
                }`}
                onClick={() => toggle(provider.id)}
                aria-pressed={on}
                data-testid={`cis-provider-${provider.id}`}
              >
                <span className="cis-provider-row__check" aria-hidden>
                  {on ? "✓" : ""}
                </span>
                <span className="cis-provider-row__icon" aria-hidden>
                  {badge === "API" ? "☁" : "◆"}
                </span>
                <span className="cis-provider-row__body">
                  <strong>{provider.displayName}</strong>
                  {subLabel ? <span className="cis-provider-row__sublabel">{subLabel}</span> : null}
                  <span className="cis-provider-row__meta">
                    <span className={`cis-pill cis-pill--${badge.toLowerCase()}`}>{badge}</span>
                    <span>{readinessLabel(provider)}</span>
                    {provider.costHint ? <span>{provider.costHint}</span> : null}
                    {bestMatchId === provider.id ? <span className="cis-pill cis-pill--best">Best Match</span> : null}
                  </span>
                  {licenseShort ? (
                    <span
                      className="cis-provider-row__license"
                      title={provider.licenseNote || undefined}
                    >
                      {licenseShort}
                    </span>
                  ) : null}
                </span>
              </button>
              {installHref ? (
                <a className="cis-provider-row__install" href={installHref}>
                  Install guide
                </a>
              ) : null}
            </li>
          );
        })}
      </ul>
    </div>
  );

  return (
    <div className="cis-provider-browser" data-testid="cis-provider-browser">
      <div className="cis-provider-browser__actions">
        <button type="button" onClick={() => setAll(providers.filter((p) => p.readiness === "ready"))}>
          Select All Ready
        </button>
        <button type="button" onClick={() => onChange([])}>
          Deselect All
        </button>
        <button type="button" onClick={() => setAll(local.filter((p) => p.readiness === "ready"))}>
          Only Local
        </button>
        <button type="button" onClick={() => setAll(api.filter((p) => p.readiness === "ready"))}>
          Only API
        </button>
        <button
          type="button"
          onClick={() => onChange(bestMatchId ? [bestMatchId] : [])}
          disabled={!bestMatchId}
        >
          Best Match
        </button>
      </div>
      {renderGroup("Local", local)}
      {renderGroup("API", api)}
      {!providers.length ? <p className="muted">No image providers discovered yet.</p> : null}
    </div>
  );
}
