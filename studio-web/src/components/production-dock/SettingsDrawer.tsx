import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import type { CpuFallbackPolicy, ThemePreference } from "../../modelRegistry/contracts";
import { buildAiGuidedSetupPath } from "../../setup/navigation";
import { Button } from "../ui";
import { DockSpendPanel } from "./DockSpendPanel";
import type { ProductionDockApi } from "./useProductionDock";

export function SettingsDrawer({
  open,
  dock,
  onClose,
  onOpenDiagnostics,
}: {
  open: boolean;
  dock: ProductionDockApi;
  onClose: () => void;
  onOpenDiagnostics: () => void;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const prefs = dock.preferences;

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    panelRef.current?.focus();
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  const openFullSettings = () => {
    sessionStorage.setItem("adept_settings_tab", "integrations");
    navigate(
      buildAiGuidedSetupPath({
        projectId: dock.projectId,
        source: "production_dock",
      }),
    );
    onClose();
  };

  return (
    <div
      ref={panelRef}
      className="production-dock-drawer"
      role="dialog"
      aria-modal="true"
      aria-label="Production settings"
      tabIndex={-1}
      data-testid="production-dock-settings"
    >
      <div className="production-dock-drawer__header">
        <h3>Settings</h3>
        <button type="button" className="production-dock-collapse-btn" aria-label="Close settings" onClick={onClose}>
          ×
        </button>
      </div>
      <div className="production-dock-settings-grid">
        <label>
          Theme
          <select
            value={prefs?.theme ?? "aurora-night"}
            aria-label="Theme preference"
            onChange={(e) => void dock.patchPreferences({ theme: e.target.value as ThemePreference })}
          >
            <option value="aurora-night">Aurora Night</option>
            <option value="aurora-day">Aurora Day</option>
            <option value="system">Follow System</option>
          </select>
        </label>
        <label>
          CPU fallback
          <select
            value={prefs?.cpuFallbackPolicy ?? "disabled"}
            aria-label="CPU fallback policy"
            onChange={(e) =>
              void dock.patchPreferences({ cpuFallbackPolicy: e.target.value as CpuFallbackPolicy })
            }
          >
            <option value="disabled">Disabled — GPU only</option>
            <option value="ask">Ask before CPU fallback</option>
            <option value="lightweight_only">Lightweight CPU tasks only</option>
          </select>
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <input
            type="checkbox"
            checked={prefs?.dockAutoCollapse ?? true}
            aria-label="Auto-collapse dock when idle"
            onChange={(e) => void dock.patchPreferences({ dockAutoCollapse: e.target.checked })}
          />
          Auto-collapse dock when idle
        </label>
      </div>
      <DockSpendPanel projectId={dock.projectId} />
      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.85rem" }}>
        <Button variant="secondary" aria-label="Open diagnostics" onClick={onOpenDiagnostics}>
          Diagnostics
        </Button>
        <Button variant="secondary" aria-label="Open full settings" onClick={openFullSettings}>
          Full Settings
        </Button>
        <Button
          variant="secondary"
          aria-label="Open local runtime settings"
          onClick={() => {
            navigate("/settings/local-runtime");
            onClose();
          }}
        >
          Local Runtime
        </Button>
        <Button
          variant="secondary"
          aria-label="Set up hosted provider"
          onClick={() => {
            dock.setProviderModalOpen(true);
            onClose();
          }}
        >
          Hosted Provider
        </Button>
      </div>
    </div>
  );
}
