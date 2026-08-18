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
export function LoRASelector({
  modelFamily,
  modality,
  value,
  onChange,
  onManage,
  disabled = false,
  compact = false,
}: {
  modelFamily: string;
  modality?: "image" | "video";
  value?: LoraSelection | null;
  onChange: (selection: LoraSelection | null) => void;
  onManage?: () => void;
  disabled?: boolean;
  compact?: boolean;
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
          if (value && !list.some((l) => l.id === value.loraId)) {
            onChange(null);
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

  const selected = useMemo(
    () => (value && loras ? loras.find((l) => l.id === value.loraId) ?? null : null),
    [value, loras],
  );

  const handleSelect = useCallback(
    (loraId: string) => {
      if (!loraId) {
        onChange(null);
        return;
      }
      const lora = loras?.find((l) => l.id === loraId);
      if (!lora) return;
      onChange({
        loraId: lora.id,
        name: lora.name,
        strength: Number(lora.recommended_strength ?? 0.8),
      });
    },
    [loras, onChange],
  );

  if (error) return null;
  if (!loras) return null;
  if (!loras.length) return null;

  const selectedRecord = selected;
  const strengthMin = Number(selectedRecord?.strength_min ?? 0);
  const strengthMax = Number(selectedRecord?.strength_max ?? 1.5);
  const strength = Number(value?.strength ?? selectedRecord?.recommended_strength ?? 0.8);

  const manage =
    onManage ||
    (() => {
      window.location.assign(buildAiGuidedSetupPath({ source: "image_studio" }));
    });

  return (
    <div className={compact ? "lora-selector lora-selector--compact" : "lora-selector"}>
      <div className="field">
        <label title="Optional model adapter for style, identity, motion, or other specialized behavior.">
          LoRA
        </label>
        <select
          data-testid="lora-select"
          value={value?.loraId ?? ""}
          disabled={disabled}
          onChange={(e) => handleSelect(e.target.value)}
        >
          <option value="">None</option>
          {loras.map((l) => (
            <option key={l.id} value={l.id}>
              {l.name}
            </option>
          ))}
        </select>
      </div>
      {value && selectedRecord ? (
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
            onChange={(e) => onChange({ ...value, strength: Number(e.target.value) })}
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