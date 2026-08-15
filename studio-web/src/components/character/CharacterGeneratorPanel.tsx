/**
 * Character-only generator panel: local multi-select + Auto Select exclusivity,
 * API shortlist from Setup discovery, and a visible Generation Plan.
 *
 * Do not use this in Prop Creator. Prop Creator keeps GeneratorSourceSelector.
 */
import { useEffect, useId, useMemo, useState } from "react";
import { api } from "../../api";
import { fetchDiscoveredHostedModelRows } from "../generators/discoveredModels";
import {
  conditioningModeLabel,
  identityDisabledReason,
  isIdentityEligible,
  type GeneratorOption,
} from "../generators/types";
import {
  CHARACTER_SHEET_BATCH_MAX,
  CHARACTER_SHEET_BATCH_MIN,
  clampBatchCount,
  cloudModelStatusLabel,
  groupDiscoveredImageModelsByProvider,
  isAutoSelectActive,
  mergePlanWithInventory,
  normalizeDiscoveredImageModel,
  returnToAutoSelectOnly,
  summarizeGenerationPlan,
  type CharacterGeneratorPlan,
  type NormalizedDiscoveredImageModel,
} from "./characterGeneratorPlan";
import "../generators/generatorSource.css";

type Props = {
  projectId: string;
  visualStyle?: string;
  hasReference: boolean;
  disabled?: boolean;
  value: CharacterGeneratorPlan;
  onChange: (
    next: CharacterGeneratorPlan | ((prev: CharacterGeneratorPlan) => CharacterGeneratorPlan),
  ) => void;
  onInventory?: (inv: { localOptions: GeneratorOption[]; apiOptions: GeneratorOption[] }) => void;
};

function BatchSelect({
  value,
  disabled,
  testId,
  label,
  onChange,
}: {
  value: number;
  disabled?: boolean;
  testId: string;
  label: string;
  onChange: (n: number) => void;
}) {
  return (
    <label className="character-core__batch">
      <span>Batches</span>
      <select
        data-testid={testId}
        aria-label={`Batches for ${label}`}
        value={clampBatchCount(value)}
        disabled={disabled}
        onChange={(e) => onChange(clampBatchCount(Number(e.target.value)))}
      >
        {Array.from({ length: CHARACTER_SHEET_BATCH_MAX - CHARACTER_SHEET_BATCH_MIN + 1 }, (_, i) => {
          const n = CHARACTER_SHEET_BATCH_MIN + i;
          return (
            <option key={n} value={n}>
              {n}
            </option>
          );
        })}
      </select>
    </label>
  );
}



export function CharacterGeneratorPanel({
  projectId,
  visualStyle,
  hasReference,
  disabled,
  value,
  onChange,
  onInventory,
}: Props) {
  const [localOptions, setLocalOptions] = useState<GeneratorOption[]>([]);
  const [apiModels, setApiModels] = useState<NormalizedDiscoveredImageModel[]>([]);
  const [recommendedLocalId, setRecommendedLocalId] = useState<string | null>(null);

  const styleOptions = localOptions.filter((o) => o.supportsEditing);
  const autoActive = isAutoSelectActive(value);
  const summary = summarizeGenerationPlan(value, localOptions);
  const apiGroups = useMemo(() => groupDiscoveredImageModelsByProvider(apiModels), [apiModels]);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      let nextLocal: GeneratorOption[] = [];
      let nextApi: NormalizedDiscoveredImageModel[] = [];
      try {
        const rec = await api
          .imageProductRecommend({
            purpose: "character",
            visualStyle: visualStyle || undefined,
            hasReference,
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
        const models = await api.imagegenModels().catch(() => []);
        if (cancelled) return;
        nextLocal = (models || [])
          .filter((m) => m.group !== "auto")
          .map((m) => ({
            id: m.id,
            label: m.label,
            family: m.id,
            providerKind: "local" as const,
            executable: m.executable !== false,
            status: m.status || "Certified",
            supportsReferences: !!m.supportsReferences,
            supportsEditing: !!(m as { supportsEditing?: boolean }).supportsEditing,
          }));
        if (recFamily) {
          const match = nextLocal.find((o) => o.id === recFamily || o.family === recFamily);
          if (match) setRecommendedLocalId(match.id);
        }
        setLocalOptions(nextLocal);
      } catch {
        if (!cancelled) setLocalOptions([]);
      }

      try {
        const rows = await fetchDiscoveredHostedModelRows("image").catch(() => []);
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
        nextApi = rows
          .map((row) => normalizeDiscoveredImageModel(row, falBalance))
          .filter((row): row is NormalizedDiscoveredImageModel => !!row);
        setApiModels(nextApi);
      } catch {
        if (!cancelled) setApiModels([]);
      }

      if (!cancelled) {
        const apiOptions: GeneratorOption[] = nextApi.map((m) => ({
          id: `${m.providerId}:${m.modelId}`,
          label: m.displayName,
          providerKind: "cloud",
          providerId: m.providerId,
          modelId: m.modelId,
          executable: m.executable,
          credits: m.credits,
          availability: m.availability,
          capabilities: m.capabilities,
          supportsReferences: m.supportsReferences,
        }));
        onInventory?.({ localOptions: nextLocal, apiOptions });
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [projectId, visualStyle, hasReference, onInventory]);

  useEffect(() => {
    if (!localOptions.length && !apiModels.length) return;
    onChange((prev) => mergePlanWithInventory(prev, localOptions, apiModels));
  }, [localOptions, apiModels, onChange]);

  const identityList = useMemo(() => {
    if (!recommendedLocalId) return localOptions;
    const rec = localOptions.find((o) => o.id === recommendedLocalId);
    if (!rec) return localOptions;
    return [rec, ...localOptions.filter((o) => o.id !== recommendedLocalId)];
  }, [localOptions, recommendedLocalId]);

  const patch = (next: CharacterGeneratorPlan) => onChange(next);
  const headingId = useId();

  return (
    <section className="character-core__generators" data-testid="character-generator-panel" aria-labelledby={headingId}>
      <span className="character-core__label" id={headingId}>Image Generator</span>

      <div className="character-core__generator-row">
        <label className="character-core__checkbox">
          <input
            type="checkbox"
            data-testid="generator-local-enable"
            checked={value.localEnabled}
            disabled={disabled}
            onChange={(e) =>
              patch({
                ...value,
                localEnabled: e.target.checked,
                stage2Enabled: e.target.checked ? value.stage2Enabled : false,
              })
            }
          />
          <span>Local Identity Engine</span>
        </label>
      </div>

      <div className="character-core__generator-group" role="group" aria-label="Local generators">
      <div
        className={`character-core__source-row${autoActive ? "" : " is-inactive"}`}
        data-testid="generator-auto-row"
        data-active={autoActive ? "true" : "false"}
      >
        <label className="character-core__checkbox">
          <input
            type="checkbox"
            data-testid="generator-auto-enable"
            checked={autoActive}
            disabled={disabled || !value.localEnabled}
            onChange={(e) => {
              if (e.target.checked) patch(returnToAutoSelectOnly(value));
              else patch({ ...value, autoSelect: { ...value.autoSelect, enabled: false } });
            }}
          />
          <span>Auto Select</span>
        </label>
        <BatchSelect
          value={value.autoSelect.batchCount}
          disabled={disabled || !value.localEnabled || !autoActive}
          testId="generator-auto-batch"
          label="Auto Select"
          onChange={(n) => patch({ ...value, autoSelect: { ...value.autoSelect, batchCount: n } })}
        />
        {!autoActive && value.localEnabled ? (
          <p className="character-core__hint" data-testid="generator-auto-inactive-hint">
            Auto Select is off while a specific generator is chosen. Turn Auto Select back on to let Adept pick.
          </p>
        ) : null}
      </div>

      {identityList.map((opt) => {
        const row = value.localFamilies.find((r) => r.family === opt.id) || {
          family: opt.id,
          enabled: false,
          batchCount: 1,
        };
        const ineligible = !isIdentityEligible(opt);
        const mode = conditioningModeLabel(opt, hasReference, "Profile Guided");
        return (
          <div key={opt.id} className="character-core__source-row" data-testid={`generator-local-row-${opt.id}`}>
            <label className="character-core__checkbox">
              <input
                type="checkbox"
                data-testid={`generator-local-enable-${opt.id}`}
                checked={value.localEnabled && row.enabled}
                disabled={disabled || !value.localEnabled || ineligible}
                onChange={(e) =>
                  patch({
                    ...value,
                    localFamilies: value.localFamilies.some((existing) => existing.family === opt.id)
                      ? value.localFamilies.map((existing) =>
                          existing.family === opt.id ? { ...existing, enabled: e.target.checked } : existing,
                        )
                      : [...value.localFamilies, { family: opt.id, enabled: e.target.checked, batchCount: 1 }],
                  })
                }
              />
              <span>
                {opt.label}
                {opt.id === recommendedLocalId ? " (Recommended)" : ""}
                {mode ? ` — ${mode}` : ""}
              </span>
            </label>
            <BatchSelect
              value={row.batchCount}
              disabled={disabled || !value.localEnabled || !row.enabled || ineligible}
              testId={`generator-local-batch-${opt.id}`}
              label={opt.label}
              onChange={(n) =>
                patch({
                  ...value,
                  localFamilies: value.localFamilies.map((existing) =>
                    existing.family === opt.id ? { ...existing, batchCount: n } : existing,
                  ),
                })
              }
            />
            {ineligible ? (
              <p className="character-core__hint">{identityDisabledReason(opt)}</p>
            ) : null}
          </div>
        );
      })}

      </div>

      {value.localEnabled && styleOptions.length > 0 ? (
        <div className="character-core__generator-row character-core__generator-row--stage2">
          <label className="character-core__checkbox">
            <input
              type="checkbox"
              data-testid="generator-style-enable"
              checked={!!value.stage2Enabled}
              disabled={disabled || !value.localEnabled}
              onChange={(e) =>
                patch({
                  ...value,
                  stage2Enabled: e.target.checked,
                  stage2Family: e.target.checked ? value.stage2Family || styleOptions[0]?.id || "" : "",
                })
              }
            />
            <span>Style Engine (optional)</span>
          </label>
          <select
            data-testid="generator-style-select"
            aria-label="Style engine"
            value={value.stage2Family || styleOptions[0]?.id || ""}
            disabled={disabled || !value.localEnabled || !value.stage2Enabled}
            onChange={(e) => patch({ ...value, stage2Family: e.target.value })}
          >
            {styleOptions.map((o) => (
              <option key={o.id} value={o.id} data-testid={`generator-style-option-${o.id}`}>
                {o.label}
              </option>
            ))}
          </select>
          <p className="character-core__hint" data-testid="generator-style-hint">
            Refines the finished look after identity is generated. Does not create extra character sheets.
          </p>
        </div>
      ) : null}

      <div className="character-core__generator-row">
        <label className="character-core__checkbox">
          <input
            type="checkbox"
            data-testid="generator-api-enable"
            checked={value.apiEnabled}
            disabled={disabled}
            onChange={(e) => patch({ ...value, apiEnabled: e.target.checked })}
          />
          <span>Cloud Generators (uses credits)</span>
        </label>
      </div>

      {apiGroups.length === 0 ? (
        <p className="character-core__hint" data-testid="generator-api-empty">
          No cloud image models are connected. Add a provider in Setup to use Cloud Generators.
        </p>
      ) : (
        <div
          className="character-core__generator-group"
          role="group"
          aria-label="Cloud generators"
          data-testid="generator-api-list"
        >
        {apiGroups.map((group) => {
          const showHeading = group.models.length > 0;
          const rows = group.models.map((m) => {
          const row = value.apiModels.find((r) => r.providerId === m.providerId && r.modelId === m.modelId) || {
            providerId: m.providerId,
            modelId: m.modelId,
            model: m.model,
            displayName: m.displayName,
            enabled: false,
            batchCount: 1,
          };
          const mode = hasReference
            ? m.supportsReferences
              ? "Reference Conditioned"
              : "Profile Guided"
            : null;
          return (
            <div
              key={`${m.providerId}:${m.modelId}`}
              className="character-core__source-row"
              data-testid={`generator-api-row-${m.providerId}-${m.modelId}`}
            >
              <label className="character-core__checkbox">
                <input
                  type="checkbox"
                  data-testid={`generator-api-enable-${m.providerId}-${m.modelId}`}
                  checked={value.apiEnabled && row.enabled}
                  disabled={disabled || !value.apiEnabled || !m.executable}
                  onChange={(e) =>
                    patch({
                      ...value,
                      apiModels: value.apiModels.map((existing) =>
                        existing.providerId === m.providerId && existing.modelId === m.modelId
                          ? { ...existing, enabled: e.target.checked }
                          : existing,
                      ),
                    })
                  }
                />
                <span>
                  {m.displayName}
                  {mode ? ` — ${mode}` : ""}
                </span>
              </label>
              <BatchSelect
                value={row.batchCount}
                disabled={disabled || !value.apiEnabled || !row.enabled || !m.executable}
                testId={`generator-api-batch-${m.providerId}-${m.modelId}`}
                label={m.displayName}
                onChange={(n) =>
                  patch({
                    ...value,
                    apiModels: value.apiModels.map((existing) =>
                      existing.providerId === m.providerId && existing.modelId === m.modelId
                        ? { ...existing, batchCount: n }
                        : existing,
                    ),
                  })
                }
              />
              <span className={`character-core__credits${m.adapterAvailable ? "" : " character-core__credits--na"}`}>
                {cloudModelStatusLabel(m)}
              </span>
            </div>
          );
          });
          return (
            <div
              key={group.providerId}
              className="character-core__api-group"
              role="group"
              aria-label={`${group.providerLabel} image generators`}
              data-testid={`generator-api-provider-${group.providerId}`}
            >
              <div className="character-core__api-group-label">{group.providerLabel}</div>
              {rows}
            </div>
          );
        })}
        </div>
      )}

      <div className="character-core__generation-plan" data-testid="character-generation-plan">
        <div className="character-core__generation-plan-title">Generation Plan</div>
        <div className="character-core__generation-plan-total">
          {summary.totalSheets} Character Sheet{summary.totalSheets === 1 ? "" : "s"}
          {" · "}
          {summary.totalViews} total views
        </div>
        {summary.localLines.length ? (
          <div data-testid="character-generation-plan-local">
            Local: {summary.localLines.map((l) => `${l.label} × ${l.count}`).join(", ")}
          </div>
        ) : null}
        {summary.apiLines.length ? (
          <div data-testid="character-generation-plan-api">
            API: {summary.apiLines.map((l) => `${l.label} × ${l.count}`).join(", ")}
          </div>
        ) : null}
        {summary.apiSheetCount > 0 ? (
          <div data-testid="character-generation-plan-api-count">
            {summary.apiSheetCount} API Character Sheet{summary.apiSheetCount === 1 ? "" : "s"}
          </div>
        ) : null}
      </div>
    </section>
  );
}
