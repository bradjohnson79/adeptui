import type { ProductionDockApi } from "./useProductionDock";

export function RuntimeSourceControls({ dock }: { dock: ProductionDockApi }) {
  const localOn = dock.preferences?.runtimeLocalEnabled ?? true;
  const apiOn = dock.preferences?.runtimeApiEnabled ?? true;
  const localReady = dock.status?.localAvailable ?? false;
  const apiReady = dock.status?.apiAvailable ?? false;

  return (
    <div className="production-dock-runtime" data-testid="production-dock-runtime">
      <button
        type="button"
        className={localOn ? "is-on" : ""}
        aria-label="Toggle local runtime"
        aria-pressed={localOn}
        onClick={() => void dock.setRuntimeFlags(!localOn, apiOn)}
      >
        Local
        <span
          className={`production-dock-status-dot${localReady ? " is-ready" : localOn ? " is-warn" : ""}`}
          aria-hidden
        />
      </button>
      <button
        type="button"
        className={apiOn ? "is-on" : ""}
        aria-label="Toggle API runtime"
        aria-pressed={apiOn}
        onClick={() => void dock.setRuntimeFlags(localOn, !apiOn)}
      >
        API
        <span
          className={`production-dock-status-dot${apiReady ? " is-ready" : apiOn ? " is-warn" : ""}`}
          aria-hidden
        />
      </button>
    </div>
  );
}
