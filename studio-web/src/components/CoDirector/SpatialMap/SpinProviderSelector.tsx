/**
 * Spin Camera cloud provider selector.
 *
 * Mirrors the GeneratorSourceSelector API section pattern: live discovered
 * image models, disabled when not executable, and a "uses credits" label.
 */
import { useEffect, useState } from "react";
import { api } from "../../../api";
import type { SpinProviderOption } from "./spinCameraGating";

type Props = {
  projectId: string;
  value: string;
  disabled?: boolean;
  onChange: (next: string) => void;
};

export function SpinProviderSelector({ projectId, value, disabled, onChange }: Props) {
  const [options, setOptions] = useState<SpinProviderOption[]>([]);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const discovered = await api.hostedProvidersDiscoveredModels("image").catch(() => null);
        const items =
          ((discovered as { items?: { id?: string; label?: string; executable?: boolean; supportsReferences?: boolean }[] } | null)?.items) ||
          ((discovered as { models?: { id?: string; label?: string; executable?: boolean; supportsReferences?: boolean }[] } | null)?.models) ||
          [];
        if (cancelled) return;
        setOptions(
          items.map((m) => ({
            id: String(m.id || ""),
            label: String(m.label || m.id || ""),
            executable: m.executable === true,
            supportsReferences: m.supportsReferences === true,
          })),
        );
      } catch {
        if (!cancelled) setOptions([]);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const selected = options.find((o) => o.id === value);

  return (
    <label className="spatial-map__spin-field">
      <span>Provider</span>
      <select
        value={value}
        disabled={disabled || options.length === 0}
        onChange={(e) => onChange(e.target.value)}
        data-testid="spin-provider-select"
      >
        {options.length === 0 ? (
          <option value="">No image generators discovered</option>
        ) : (
          <option value="">Select a cloud generator…</option>
        )}
        {options.map((o) => (
          <option key={o.id} value={o.id} disabled={!o.executable} data-testid={`spin-provider-option-${o.id}`}>
            {o.label}
            {!o.executable ? " — unavailable" : ""}
          </option>
        ))}
      </select>
      {selected ? <span className="spatial-map__spin-credits">uses credits</span> : null}
    </label>
  );
}
