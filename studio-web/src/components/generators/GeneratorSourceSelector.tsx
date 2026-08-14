/**
 * GeneratorSourceSelector — shared Local + API generator source selection.
 *
 * Used by Character Creator Express and Prop Creator Express. Inventory comes
 * from the authoritative image-generation registry (api.imagegenModels), not
 * a product-only list.
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
 *
 * Mode labels are product-specific:
 *  - Character: text-to-image = "Profile Guided"
 *  - Prop:      text-to-image = "Description Guided"
 * Reference-capable families are always "Reference Conditioned".
 */
import { useEffect, useMemo, useState } from "react";
import { api } from "../../api";
import {
  conditioningModeLabel,
  identityDisabledReason,
  isIdentityEligible,
  type GeneratorOption,
  type GeneratorSourceState,
} from "./types";
import "./generatorSource.css";

export type GeneratorSourceSelectorProps = {
  projectId: string;
  visualStyle?: string;
  hasReference: boolean;
  disabled?: boolean;
  value: { local: GeneratorSourceState; api: GeneratorSourceState };
  onChange: (next: { local: GeneratorSourceState; api: GeneratorSourceState }) => void;
  /** Recommend API purpose. Default "character". Prop Creator passes "prop". */
  purpose?: string;
  /**
   * Creator-facing label for text-to-image mode.
   * Character: "Profile Guided". Prop: "Description Guided".
   */
  textModeLabel?: string;
  /** Section heading. Default "Image Generator". */
  sectionLabel?: string;
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
  purpose = "character",
  textModeLabel = "Profile Guided",
  sectionLabel = "Image Generator",
}: GeneratorSourceSelectorProps) {
  const [localOptions, setLocalOptions] = useState<GeneratorOption[]>([]);
  const [apiOptions, setApiOptions] = useState<GeneratorOption[]>([]);
  const [recommendedLocalId, setRecommendedLocalId] = useState<string | null>(null);

  // Identity engine options: all Certified local generators.
  const identityOptions = localOptions;
  // Style engine options: only editing-capable local generators (real img2img/edit workflows).
  const styleOptions = localOptions.filter((o) => o.supportsEditing);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      // --- Local generators ---
      try {
        const rec = await api
          .imageProductRecommend({
            purpose,
            visualStyle: visualStyle || undefined,
            hasReference,
            // Attached reference is a mode split, not a lock against Profile Guided families.
            referenceLocked: false,
          })
          .catch(() => null);

        let recFamily: string | null = null;
        if (rec) {
          const families: string[] =
            (rec as { families?: string[] }).families ||
            ((rec as { family?: string }).family ? [(rec as { family: string }).family] : []);
          recFamily = families[0] || null;
        }

        const models = await api
          .imagegenModels()
          .catch(
            () =>
              [] as {
                id: string;
                label: string;
                group: string;
                status?: string;
                supportsReferences?: boolean;
                executable?: boolean;
              }[],
          );
        if (cancelled) return;

        const opts: GeneratorOption[] = (models || [])
          .filter((m) => m.group !== "auto")
          .map((m) => ({
            id: m.id,
            label: m.label,
            family: m.id,
            providerKind: "local",
            executable: m.executable !== false,
            status: m.status || "Certified",
            supportsReferences: !!m.supportsReferences,
            supportsEditing: !!(m as { supportsEditing?: boolean }).supportsEditing,
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
  }, [projectId, visualStyle, hasReference, purpose]);

  const identityList = useMemo(() => {
    // Put the recommended local generator first.
    if (!recommendedLocalId) return identityOptions;
    const rec = identityOptions.find((o) => o.id === recommendedLocalId);
    if (!rec) return identityOptions;
    return [rec, ...identityOptions.filter((o) => o.id !== recommendedLocalId)];
  }, [identityOptions, recommendedLocalId]);

  const setLocal = (patch: Partial<GeneratorSourceState>) =>
    onChange({ local: { ...value.local, ...patch }, api: value.api });
  const setApi = (patch: Partial<GeneratorSourceState>) =>
    onChange({ local: value.local, api: { ...value.api, ...patch } });

  const canEnableStage2 = value.local.enabled && styleOptions.length > 0;
  const selectedStyle = styleOptions.find((o) => o.id === value.local.stage2SelectedId) ||
    styleOptions[0];

  return (
    <div className="character-core__generators">
      <span className="character-core__label">{sectionLabel}</span>

      {/* Identity Engine (Stage 1) */}
      <div className="character-core__generator-row">
        <label className="character-core__checkbox">
          <input
            type="checkbox"
            data-testid="generator-local-enable"
            checked={value.local.enabled}
            disabled={disabled}
            onChange={(e) =>
              setLocal({
                enabled: e.target.checked,
                stage2Enabled: e.target.checked ? value.local.stage2Enabled : false,
              })
            }
          />
          <span>Local Identity Engine</span>
        </label>
        <select
          data-testid="generator-local-select"
          value={value.local.selectedId}
          disabled={disabled || !value.local.enabled}
          onChange={(e) =>
            setLocal({
              selectedId: e.target.value,
              // Auto-pick the first style engine if the selected identity engine does not itself edit.
              stage2SelectedId:
                value.local.stage2SelectedId ||
                (styleOptions[0]?.id ?? ""),
            })
          }
        >
          <option value="">Auto Select</option>
          {identityList.map((o) => {
            const ineligible = !isIdentityEligible(o);
            const mode = conditioningModeLabel(o, hasReference, textModeLabel);
            return (
              <option
                key={o.id}
                value={o.id}
                disabled={ineligible}
                data-testid={`generator-local-option-${o.id}`}
                data-disabled-reason={identityDisabledReason(o) || undefined}
                title={identityDisabledReason(o) || mode || undefined}
              >
                {o.label}
                {o.id === recommendedLocalId ? " (Recommended)" : ""}
                {mode ? ` — ${mode}` : ""}
                {ineligible ? " — unavailable" : ""}
              </option>
            );
          })}
        </select>
        {value.local.enabled &&
        value.local.selectedId &&
        identityDisabledReason(
          identityOptions.find((o) => o.id === value.local.selectedId) || {
            id: "",
            label: "",
            executable: true,
          },
        ) ? (
          <p className="character-core__hint" data-testid="generator-local-disabled-reason">
            {identityDisabledReason(
              identityOptions.find((o) => o.id === value.local.selectedId) || {
                id: "",
                label: "",
                executable: true,
              },
            )}
          </p>
        ) : null}
        {value.local.enabled && hasReference ? (
          <p className="character-core__hint" data-testid="generator-local-mode">
            {!value.local.selectedId
              ? `Mode: Auto Select may mix ${textModeLabel} and Reference Conditioned`
              : identityOptions.find((o) => o.id === value.local.selectedId)?.supportsReferences
                ? "Mode: Reference Conditioned. Uses the attached Character Reference as the primary visual guide."
                : `Mode: ${textModeLabel}. Uses the saved Character Profile and style. The attached Character Reference is not used by this generator.`}
          </p>
        ) : null}
      </div>

      {/* Style Engine (Stage 2) — optional real img2img/edit refinement */}
      {canEnableStage2 ? (
        <div className="character-core__generator-row character-core__generator-row--stage2">
          <label className="character-core__checkbox">
            <input
              type="checkbox"
              data-testid="generator-style-enable"
              checked={!!value.local.stage2Enabled}
              disabled={disabled || !value.local.enabled}
              onChange={(e) =>
                setLocal({
                  stage2Enabled: e.target.checked,
                  stage2SelectedId: e.target.checked
                    ? (value.local.stage2SelectedId || styleOptions[0]?.id || "")
                    : "",
                })
              }
            />
            <span>Style Engine (optional)</span>
          </label>
          <select
            data-testid="generator-style-select"
            value={value.local.stage2SelectedId || selectedStyle?.id || ""}
            disabled={disabled || !value.local.enabled || !value.local.stage2Enabled}
            onChange={(e) => setLocal({ stage2SelectedId: e.target.value })}
          >
            {styleOptions.map((o) => (
              <option key={o.id} value={o.id} data-testid={`generator-style-option-${o.id}`}>
                {o.label}
              </option>
            ))}
          </select>
          <p className="character-core__hint" data-testid="generator-style-hint">
            Runs a real img2img/edit pass on the identity result. Only offered when the selected runtime has a certified editing workflow.
          </p>
        </div>
      ) : null}

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
              {hasReference ? (o.supportsReferences ? " — Reference Conditioned" : ` — ${textModeLabel}`) : ""}
            </option>
          ))}
        </select>
        {value.api.enabled && value.api.selectedId ? (
          <CreditLabel opt={apiOptions.find((o) => o.id === value.api.selectedId) || { id: "", label: "", executable: true }} />
        ) : null}
        {value.api.enabled && hasReference ? (
          <p className="character-core__hint" data-testid="generator-api-mode">
            {apiOptions.find((o) => o.id === value.api.selectedId)?.supportsReferences
              ? "Mode: Reference Conditioned. Uses the attached Character Reference as the primary visual guide."
              : `Mode: ${textModeLabel}. Uses the saved Character Profile and style. The attached Character Reference is not used by this generator.`}
          </p>
        ) : null}
      </div>
    </div>
  );
}
