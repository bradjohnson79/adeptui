/**
 * GeneratorSourceSelector — shared Local + API generator source selection.
 *
 * Routing hierarchy (explicit):
 *  - Reference attached  → reference-capable Certified generator eligibility FIRST,
 *                          THEN style recommendation. Reference fidelity overrides style.
 *  - No reference        → style recommendation FIRST (anime → Illustrious XL, etc.).
 *
 * Credits are capability-driven: only a numeric balance is shown when the provider
 * actually exposes one; otherwise "Connected" / "Balance unavailable". Never invent.
 *
 * User Control Law: an unchecked source produces zero jobs to that source.
 */
import { useEffect, useMemo, useState } from "react";
import { api } from "../../api";
import type { GeneratorOption, GeneratorSourceState } from "./types";

type Props = {
  projectId: string;
  visualStyle?: string;
  hasReference: boolean;
  disabled?: boolean;
  value: { local: GeneratorSourceState; api: GeneratorSourceState };
  onChange: (next: { local: GeneratorSourceState; api: GeneratorSourceState }) => void;
};

function CreditLabel({ opt }: { opt: GeneratorOption }) {
  if (typeof opt.credits === "number") {
    return <span className="character-core__credits" data-testid="api-credits">{opt.credits} credits</span>;
  }
  return (
    <span className="character-core__credits character-core__credits--na" data-testid="api-credits-na">
      {opt.availability || "Connected"}
    </span>
  );
}

export function GeneratorSourceSelector({
  projectId,
  visualStyle,
  hasReference,
  disabled,
  value,
  onChange,
}: Props) {
  const [localOptions, setLocalOptions] = useState<GeneratorOption[]>([]);
  const [apiOptions, setApiOptions] = useState<GeneratorOption[]>([]);
  const [recommendedLocalId, setRecommendedLocalId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      // --- Local generators ---
      try {
        const rec = await api
          .imageProductRecommend({
            purpose: "character",
            visualStyle: visualStyle || undefined,
            hasReference,
            referenceLocked: hasReference,
          })
          .catch(() => null);

        let recFamily: string | null = null;
        if (rec) {
          const families: string[] =
            (rec as { families?: string[] }).families ||
            ((rec as { family?: string }).family ? [(rec as { family: string }).family] : []);
          recFamily = families[0] || null;
        }

        const models = await api.imagegenModels().catch(() => [] as { id: string; label: string; group: string }[]);
        if (cancelled) return;

        const opts: GeneratorOption[] = (models || []).map((m) => ({
          id: m.id,
          label: m.label,
          family: m.id,
          providerKind: "local",
          executable: true,
          status: "Certified",
        }));
        setLocalOptions(opts);

        // Recommended local = style/reference-aware recommendation, if present in list.
        if (recFamily) {
          const match = opts.find((o) => o.id === recFamily || o.family === recFamily);
          if (match) setRecommendedLocalId(match.id);
        }
      } catch {
        if (!cancelled) setLocalOptions([]);
      }

      // --- API generators ---
      try {
        const discovered = await api
          .hostedProvidersDiscoveredModels("image")
          .catch(() => null);
        const models =
          (discovered as { items?: { id?: string; label?: string; provider?: string }[] })?.items ||
          (discovered as { models?: { id?: string; label?: string; provider?: string }[] })?.models ||
          [];

        // Capability-driven credits: only set when a provider exposes a balance.
        let falBalance: number | null = null;
        try {
          const usage = await api.falUsage(30).catch(() => null);
          const b =
            (usage as { balance?: number })?.balance ??
            (usage as { credits?: number })?.credits ??
            (usage as { summary?: { balance?: number } })?.summary?.balance;
          falBalance = typeof b === "number" ? b : null;
        } catch {
          falBalance = null;
        }

        if (cancelled) return;
        const opts: GeneratorOption[] = models.map((m) => {
          const providerId = (m.provider || "").toLowerCase();
          const credits = providerId === "fal" ? falBalance : null;
          return {
            id: m.id || `${providerId}:${m.label || "model"}`,
            label: m.label || m.id || "API model",
            providerKind: "cloud",
            executable: true,
            credits,
            availability: credits == null ? "Connected" : undefined,
          };
        });
        setApiOptions(opts);
      } catch {
        if (!cancelled) setApiOptions([]);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [projectId, visualStyle, hasReference]);

  const localList = useMemo(() => {
    // Put the recommended local generator first.
    if (!recommendedLocalId) return localOptions;
    const rec = localOptions.find((o) => o.id === recommendedLocalId);
    if (!rec) return localOptions;
    return [rec, ...localOptions.filter((o) => o.id !== recommendedLocalId)];
  }, [localOptions, recommendedLocalId]);

  const setLocal = (patch: Partial<GeneratorSourceState>) =>
    onChange({ local: { ...value.local, ...patch }, api: value.api });
  const setApi = (patch: Partial<GeneratorSourceState>) =>
    onChange({ local: value.local, api: { ...value.api, ...patch } });

  return (
    <div className="character-core__generators">
      <span className="character-core__label">Image Generator</span>

      {/* Local */}
      <div className="character-core__generator-row">
        <label className="character-core__checkbox">
          <input
            type="checkbox"
            data-testid="generator-local-enable"
            checked={value.local.enabled}
            disabled={disabled}
            onChange={(e) => setLocal({ enabled: e.target.checked })}
          />
          <span>Local Generator</span>
        </label>
        <select
          data-testid="generator-local-select"
          value={value.local.selectedId}
          disabled={disabled || !value.local.enabled}
          onChange={(e) => setLocal({ selectedId: e.target.value })}
        >
          <option value="">Select a local generator…</option>
          {localList.map((o) => (
            <option key={o.id} value={o.id}>
              {o.label}
              {o.id === recommendedLocalId ? " (Recommended)" : ""}
            </option>
          ))}
        </select>
      </div>

      {/* API */}
      <div className="character-core__generator-row">
        <label className="character-core__checkbox">
          <input
            type="checkbox"
            data-testid="generator-api-enable"
            checked={value.api.enabled}
            disabled={disabled}
            onChange={(e) => setApi({ enabled: e.target.checked })}
          />
          <span>Cloud Generator (uses credits)</span>
        </label>
        <select
          data-testid="generator-api-select"
          value={value.api.selectedId}
          disabled={disabled || !value.api.enabled}
          onChange={(e) => setApi({ selectedId: e.target.value })}
        >
          <option value="">Select a cloud generator…</option>
          {apiOptions.map((o) => (
            <option key={o.id} value={o.id}>
              {o.label}
            </option>
          ))}
        </select>
        {value.api.enabled && value.api.selectedId ? (
          <CreditLabel opt={apiOptions.find((o) => o.id === value.api.selectedId) || { id: "", label: "", executable: true }} />
        ) : null}
      </div>
    </div>
  );
}
