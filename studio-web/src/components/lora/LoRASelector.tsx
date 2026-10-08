import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { buildAiGuidedSetupPath } from "../../setup/navigation";
import { fetchCompatibleLoras, type CompatibleLora } from "./loraClient";

export interface LoraSelection {
  loraId: string;
  name: string;
  strength: number;
}

/**
 * Shared LoRA selector — one consistent pattern across every Adept UI
 * Advanced accordion. Renders nothing when the active model family has no
 * compatible enabled LoRAs (no clutter, no alarming warnings).
 */
const MAX_LORAS = 4;

export function LoRASelector({
  modelFamily,
  modality,
  value,
  onChange,
  onStackChange,
  onManage,
  onAddTrigger,
  disabled = false,
  compact = false,
  multiple = false,
}: {
  modelFamily: string;
  modality?: "image" | "video";
  value?: LoraSelection | LoraSelection[] | null;
  onChange: (selection: LoraSelection | null) => void;
  onStackChange?: (selection: LoraSelection[]) => void;
  onManage?: () => void;
  onAddTrigger?: (text: string) => void;
  disabled?: boolean;
  compact?: boolean;
  multiple?: boolean;
}) {
  const [loras, setLoras] = useState<CompatibleLora[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    setError(null);
    let cancelled = false;
    fetchCompatibleLoras(modelFamily, modality)
      .then((list) => {
        if (!cancelled && mounted.current) {
          setLoras(list);
          // Drop stale selections that are no longer compatible/enabled.
          const selectedIds = Array.isArray(value) ? value.map((item) => item.loraId) : value ? [value.loraId] : [];
          if (selectedIds.some((id) => !list.some((l) => l.id === id))) {
            if (multiple) {
              const kept = (Array.isArray(value) ? value : []).filter((item) => list.some((l) => l.id === item.loraId));
              onStackChange?.(kept);
              onChange(kept[0] ?? null);
            } else if (!Array.isArray(value)) {
              onChange(null);
            }
          }
        }
      })
      .catch(() => {
        if (!cancelled && mounted.current) setError("LoRA registry unavailable.");
      });
    return () => {
      cancelled = true;
      mounted.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modelFamily, modality]);

  const selectedList = useMemo(() => {
    const items = Array.isArray(value) ? value : value ? [value] : [];
    return items;
  }, [value]);

  const selected = useMemo(
    () => (selectedList[0] && loras ? loras.find((l) => l.id === selectedList[0].loraId) ?? null : null),
    [selectedList, loras],
  );

  const selectionFor = useCallback(
    (loraId: string): LoraSelection | null => {
      const lora = loras?.find((l) => l.id === loraId);
      if (!lora) return null;
      return {
        loraId: lora.id,
        name: lora.name,
        strength: Number(lora.recommended_strength ?? 0.8),
      };
    },
    [loras],
  );

  const handleSelect = useCallback(
    (loraId: string) => {
      if (!loraId) {
        if (multiple) onStackChange?.([]);
        onChange(null);
        return;
      }
      const next = selectionFor(loraId);
      if (!next) return;
      if (!multiple) {
        onChange(next);
        return;
      }
      if (selectedList.some((item) => item.loraId === loraId) || selectedList.length >= MAX_LORAS) return;
      const stack = [...selectedList, next];
      onStackChange?.(stack);
      onChange(stack[0] ?? null);
    },
    [multiple, onChange, onStackChange, selectedList, selectionFor],
  );

  if (error) return null;
  if (!loras) return null;
  if (!loras.length) return null;

  const single = !Array.isArray(value) ? value : null;
  const selectedRecord = selected;
  const strengthMin = Number(selectedRecord?.strength_min ?? 0);
  const strengthMax = Number(selectedRecord?.strength_max ?? 1.5);
  const strength = Number(single?.strength ?? selectedRecord?.recommended_strength ?? 0.8);

  const manage =
    onManage ||
    (() => {
      window.location.assign(buildAiGuidedSetupPath({ source: "image_studio" }));
    });

  const updateStrength = (loraId: string, nextStrength: number) => {
    if (multiple) {
      const stack = selectedList.map((item) => (item.loraId === loraId ? { ...item, strength: nextStrength } : item));
      onStackChange?.(stack);
      onChange(stack[0] ?? null);
      return;
    }
    if (single) onChange({ ...single, strength: nextStrength });
  };

  return (
    <div className={compact ? "lora-selector lora-selector--compact" : "lora-selector"} data-testid="lora-selector">
      <div className="field">
        <label title="Optional model adapter for style, identity, motion, or other specialized behavior.">
          {multiple ? "LoRAs" : "LoRA"}
        </label>
        <select
          data-testid="lora-select"
          value={multiple ? "" : single?.loraId ?? ""}
          disabled={disabled || (multiple && selectedList.length >= MAX_LORAS)}
          onChange={(e) => handleSelect(e.target.value)}
        >
          <option value="">{multiple ? "Add LoRA" : "None"}</option>
          {loras
            .filter((l) => !multiple || !selectedList.some((item) => item.loraId === l.id))
            .map((l) => (
              <option key={l.id} value={l.id}>
                {l.name}
              </option>
            ))}
        </select>
      </div>
      {multiple
        ? selectedList.map((item) => {
            const record = loras.find((l) => l.id === item.loraId);
            const min = Number(record?.strength_min ?? 0);
            const max = Number(record?.strength_max ?? 1.5);
            const triggers = record?.trigger_words || [];
            return (
              <div key={item.loraId} className="field" data-testid="lora-selected">
                <label>{item.name}</label>
                <input
                  type="range"
                  data-testid="lora-strength"
                  min={min}
                  max={Math.max(max, min + 0.1)}
                  step={0.05}
                  value={item.strength}
                  disabled={disabled}
                  onChange={(e) => updateStrength(item.loraId, Number(e.target.value))}
                />
                <span className="muted tiny">{Number(item.strength).toFixed(2)}</span>
                <button
                  type="button"
                  className="ghost tiny"
                  onClick={() => {
                    const stack = selectedList.filter((entry) => entry.loraId !== item.loraId);
                    onStackChange?.(stack);
                    onChange(stack[0] ?? null);
                  }}
                >
                  Remove
                </button>
                {triggers.length && onAddTrigger ? (
                  <button type="button" className="ghost tiny" onClick={() => onAddTrigger(triggers.join(", "))}>
                    Add trigger to prompt
                  </button>
                ) : null}
              </div>
            );
          })
        : null}
      {!multiple && single && selectedRecord ? (
        <div className="field">
          <label>Strength</label>
          <input
            type="range"
            data-testid="lora-strength"
            min={strengthMin}
            max={Math.max(strengthMax, strengthMin + 0.1)}
            step={0.05}
            value={strength}
            disabled={disabled}
            onChange={(e) => updateStrength(single.loraId, Number(e.target.value))}
          />
          <span className="muted tiny">{Number(strength).toFixed(2)}</span>
        </div>
      ) : null}
      <button type="button" className="ghost tiny" onClick={manage}>
        Manage LoRAs
      </button>
    </div>
  );
}