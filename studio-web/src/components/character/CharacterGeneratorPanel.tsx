/**
 * Character Creator CRS generator — Qwen Image 2512 or GPT Image 2 only.
 */
import { useEffect, useId, useMemo, useState } from "react";
import { api } from "../../api";
import { fetchDiscoveredHostedModelRows } from "../generators/discoveredModels";
import { resolveCharacterGenerationMode, type GeneratorOption } from "../generators/types";
import {
  CRS_GPT_IMAGE_2,
  CRS_QWEN_FAMILY,
  DEFAULT_GENERATOR_FAMILY,
  isGptImage2Row,
  mergePlanWithInventory,
  normalizeDiscoveredImageModel,
  selectedCrsGenerator,
  setCrsGenerator,
  type CharacterGeneratorPlan,
  type CrsGeneratorId,
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
  const headingId = useId();

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      let nextLocal: GeneratorOption[] = [];
      let nextApi: NormalizedDiscoveredImageModel[] = [];
      try {
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
        setLocalOptions(nextLocal);
      } catch {
        if (!cancelled) setLocalOptions([]);
      }

      try {
        const rows = await fetchDiscoveredHostedModelRows("image").catch(() => []);
        if (cancelled) return;
        nextApi = rows
          .map((row) => normalizeDiscoveredImageModel(row))
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

  const qwenOpt = localOptions.find((o) => o.id === DEFAULT_GENERATOR_FAMILY || o.family === DEFAULT_GENERATOR_FAMILY);
  const qwenUnavailable = !!qwenOpt && qwenOpt.executable === false;
  const qwenMissing = localOptions.length > 0 && !qwenOpt;
  const gptRow = useMemo(() => apiModels.find((m) => isGptImage2Row(m)), [apiModels]);
  const gptReady = !!gptRow && gptRow.executable !== false && gptRow.adapterAvailable !== false;
  const selected = selectedCrsGenerator(value);
  const qwenMode = resolveCharacterGenerationMode(qwenOpt, hasReference);
  const qwenLabel =
    qwenUnavailable || qwenMissing
      ? "Qwen Image 2512 — Unavailable"
      : qwenMode === "REFERENCE_CONDITIONED"
        ? "Qwen Image 2512 — Uses your photo"
        : "Qwen Image 2512";
  const gptPixels = Boolean(hasReference && gptRow?.supportsReferences && gptReady);
  const gptLabel = gptReady
    ? gptPixels
      ? "GPT Image 2 — Uses your photo"
      : "GPT Image 2 — Cloud"
    : "GPT Image 2 — Needs setup";

  return (
    <section className="character-core__generators" data-testid="character-generator-panel" aria-labelledby={headingId}>
      <span className="character-core__label" id={headingId}>
        Character Reference Sheet
      </span>
      <div className="character-core__generator-compact" data-testid="character-generator-compact">
        <label className="character-core__field">
          <span className="character-core__label">Generator</span>
          <select
            data-testid="character-generator-select"
            aria-label="Character Reference Sheet generator"
            value={selected}
            disabled={disabled}
            onChange={(e) => onChange(setCrsGenerator(value, e.target.value as CrsGeneratorId))}
          >
            <option value={CRS_QWEN_FAMILY}>{qwenLabel}</option>
            <option value={CRS_GPT_IMAGE_2} disabled={!gptReady}>
              {gptLabel}
            </option>
          </select>
        </label>
      </div>
      {(qwenUnavailable || qwenMissing) && selected === CRS_QWEN_FAMILY ? (
        <p className="character-core__hint" data-testid="character-qwen-unavailable">
          Qwen Image 2512 is unavailable on this runtime. Choose GPT Image 2 if it is set up — Adept will not switch automatically.
        </p>
      ) : null}
    </section>
  );
}
