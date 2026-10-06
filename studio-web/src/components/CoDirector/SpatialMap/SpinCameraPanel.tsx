/**
 * Spin Camera card + package progress + view thumbnails.
 *
 * Creator-facing language only. One primary action per section.
 */
import { api } from "../../../api";
import { useMemo } from "react";
import { createSpinImagesDisabledReason, spinViewIsFailed, spinViewIsPending, type SpinProviderOption } from "./spinCameraGating";
import { SpinProviderSelector } from "./SpinProviderSelector";
import { formatMeters, spinViewLabel, SPIN_VIEW_ORDER } from "./spinCameraGeometry";
import type { SpinCameraPlacement, SpinPackageManifest, SpinViewKey } from "./types";

type Props = {
  projectId: string;
  mapId: string;
  spinCamera: SpinCameraPlacement | null;
  centerStatus: { centered: boolean; distanceMeters: number; toleranceMeters: number } | null;
  packages: SpinPackageManifest[];
  activePackage: SpinPackageManifest | null;
  activePackageId: string | null;
  onSelectPackage: (packageId: string) => void;
  providerOptions: SpinProviderOption[];
  selectedProviderId: string;
  onChangeProvider: (next: string) => void;
  ersAssetId: string | null;
  hasBackgroundAssetId: boolean;
  busy: boolean;
  error: string | null;
  onCreatePackage: (providerId: string, confirmPaidCloud: boolean) => void;
  onRegenerateDirection: (packageId: string, direction: SpinViewKey, confirmPaidCloud: boolean) => void;
  onBuildErs: (packageId: string) => void;
  onOpenInLibrary: (assetId: string) => void;
  onRemoveSpinCamera: () => void;
};

export function SpinCameraPanel({
  projectId,
  spinCamera,
  centerStatus,
  packages,
  activePackage,
  activePackageId,
  onSelectPackage,
  providerOptions,
  selectedProviderId,
  onChangeProvider,
  ersAssetId,
  hasBackgroundAssetId,
  busy,
  error,
  onCreatePackage,
  onRegenerateDirection,
  onBuildErs,
  onOpenInLibrary,
  onRemoveSpinCamera,
}: Props) {
  const hasPackageInFlight = useMemo(() => {
    if (!activePackage) return false;
    return Object.values(activePackage.views || {}).some(
      (v) => v.status === "queued" || v.status === "generating",
    );
  }, [activePackage]);

  const allViewsDone = useMemo(() => {
    if (!activePackage) return false;
    return SPIN_VIEW_ORDER.every((d) => activePackage.views?.[d]?.status === "done");
  }, [activePackage]);

  const disabledReason = createSpinImagesDisabledReason(
    spinCamera,
    centerStatus,
    selectedProviderId,
    providerOptions,
    hasBackgroundAssetId,
  );

  const statusText = !spinCamera
    ? "Not placed"
    : centerStatus?.centered
      ? "Centered ✓"
      : "Move closer to scene center";

  const packageVersions = packages.length > 1;

  return (
    <div className="spatial-map__spin" data-testid="spin-camera-panel">
      {!spinCamera ? (
        <p className="spatial-map__hint" data-testid="spin-camera-guidance">
          Place the Spin Camera near the center of the scene before creating the ERS directional views.
        </p>
      ) : null}

      <div className="spatial-map__spin-card" data-testid="spin-camera-card">
        <div className="spatial-map__spin-card-head">
          <span className="spatial-map__spin-card-title">SPIN CAMERA</span>
          {spinCamera ? (
            <button
              type="button"
              className="spatial-map__slot-remove"
              onClick={() => onRemoveSpinCamera()}
              disabled={busy}
              data-testid="spin-camera-remove"
              aria-label="Remove Spin Camera"
            >
              Remove
            </button>
          ) : null}
        </div>

        {spinCamera ? (
          <div className="spatial-map__spin-fields">
            <p className="spatial-map__spin-meta" data-testid="spin-camera-position">
              Position: X {formatMeters(spinCamera.x)} m · Z {formatMeters(spinCamera.z)} m
            </p>
            <p className={`spatial-map__spin-status${centerStatus?.centered ? " is-centered" : ""}`} data-testid="spin-camera-status">
              {statusText}
              {centerStatus && !centerStatus.centered ? (
                <span className="spatial-map__spin-status-distance" data-testid="spin-camera-status-distance">
                  {" "}
                  ({formatMeters(centerStatus.distanceMeters)} / {formatMeters(centerStatus.toleranceMeters)} m tolerance)
                </span>
              ) : null}
            </p>
          </div>
        ) : (
          <p className="spatial-map__hint" data-testid="spin-camera-place-hint">
            Click a cell on the map to place the Spin Camera.
          </p>
        )}

        <SpinProviderSelector
          projectId={projectId}
          value={selectedProviderId}
          disabled={busy || !spinCamera}
          onChange={onChangeProvider}
        />

        {disabledReason ? (
          <p className="spatial-map__hint" data-testid="spin-create-disabled-reason">
            {disabledReason}
          </p>
        ) : null}

        <button
          type="button"
          className="ui-btn ui-btn--primary"
          disabled={busy || !!disabledReason}
          onClick={() => {
            if (!selectedProviderId) return;
            const confirmed = window.confirm(
              "Creating the Spin Package will run 5 paid cloud image generations. Continue?",
            );
            if (confirmed) onCreatePackage(selectedProviderId, true);
          }}
          data-testid="spin-create-package"
        >
          {busy && !activePackage ? "Placing…" : "Create Spin Images"}
        </button>
      </div>

      {activePackage ? (
        <div className="spatial-map__spin-package" data-testid="spin-active-package">
          {packageVersions ? (
            <label className="spatial-map__spin-field">
              <span>Package version</span>
              <select
                value={activePackageId || ""}
                onChange={(e) => onSelectPackage(e.target.value)}
                data-testid="spin-package-version-select"
              >
                {packages.map((p) => (
                  <option key={p.spinPackageId} value={p.spinPackageId} data-testid={`spin-package-version-${p.spinPackageId}`}>
                    Spin Package v{p.version} · {p.provider}
                  </option>
                ))}
              </select>
            </label>
          ) : null}

          <div className="spatial-map__spin-progress" data-testid="spin-progress">
            {SPIN_VIEW_ORDER.map((direction) => {
              const view = activePackage.views?.[direction];
              const status = view?.status || "pending";
              const isPending = !view || status === "pending";
              const isGenerating = spinViewIsPending(status);
              const isDone = status === "done";
              const isFailed = spinViewIsFailed(status);
              return (
                <div
                  key={direction}
                  className={`spatial-map__spin-progress-row${isDone ? " is-done" : ""}${isFailed ? " is-failed" : ""}${isGenerating ? " is-generating" : ""}`}
                  data-testid={`spin-progress-${direction}`}
                >
                  <span className="spatial-map__spin-progress-label">{spinViewLabel(direction)}</span>
                  <span className="spatial-map__spin-progress-state" data-testid={`spin-progress-state-${direction}`}>
                    {isDone ? "✓" : isFailed ? "FAILED" : isGenerating ? "Generating…" : isPending ? "Pending" : status}
                  </span>
                  {isFailed ? (
                    <button
                      type="button"
                      className="spatial-map__slot-action"
                      onClick={() => {
                        const confirmed = window.confirm(
                          `Regenerating ${spinViewLabel(direction)} will use cloud credits. Continue?`,
                        );
                        if (confirmed) onRegenerateDirection(activePackage.spinPackageId, direction, true);
                      }}
                      disabled={busy}
                      data-testid={`spin-retry-${direction}`}
                    >
                      Retry
                    </button>
                  ) : null}
                </div>
              );
            })}
          </div>

          {hasPackageInFlight ? (
            <p className="spatial-map__hint" data-testid="spin-package-in-flight">
              Generating directional views…
            </p>
          ) : null}

          {activePackage.ersStale ? (
            <div className="spatial-map__spin-stale" data-testid="spin-ers-stale">
              <p>Spin Package changed</p>
              <button
                type="button"
                className="ui-btn ui-btn--secondary"
                disabled={busy}
                onClick={() => onBuildErs(activePackage.spinPackageId)}
                data-testid="spin-rebuild-ers"
              >
                Rebuild ERS
              </button>
            </div>
          ) : null}

          {allViewsDone ? (
            <div className="spatial-map__spin-thumbnails" data-testid="spin-thumbnails">
              {SPIN_VIEW_ORDER.map((direction) => {
                const view = activePackage.views?.[direction];
                const assetId = view?.assetId;
                if (!assetId) return null;
                const url = api.assetUrl(assetId);
                return (
                  <div key={direction} className="spatial-map__spin-thumb" data-testid={`spin-thumb-${direction}`}>
                    <img src={url} alt={spinViewLabel(direction)} loading="lazy" />
                    <span className="spatial-map__spin-thumb-label">{spinViewLabel(direction)}</span>
                    <div className="spatial-map__spin-thumb-actions">
                      <button
                        type="button"
                        className="spatial-map__slot-action"
                        onClick={() => window.open(url, "_blank", "noopener,noreferrer")}
                        data-testid={`spin-view-${direction}`}
                      >
                        View
                      </button>
                      <button
                        type="button"
                        className="spatial-map__slot-action"
                        onClick={() => onOpenInLibrary(assetId)}
                        data-testid={`spin-open-library-${direction}`}
                      >
                        Open in Library
                      </button>
                      <button
                        type="button"
                        className="spatial-map__slot-action"
                        onClick={() => {
                          const confirmed = window.confirm(
                            `Regenerating ${spinViewLabel(direction)} will use cloud credits. Continue?`,
                          );
                          if (confirmed) onRegenerateDirection(activePackage.spinPackageId, direction, true);
                        }}
                        disabled={busy}
                        data-testid={`spin-regenerate-${direction}`}
                      >
                        Regenerate Direction
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : null}
        </div>
      ) : null}

      {ersAssetId ? (
        <div className="spatial-map__spin-ers" data-testid="spin-ers-result">
          <p className="eyebrow">Environment Reference Sheet</p>
          <img className="spatial-map__ers-img" src={api.assetUrl(ersAssetId)} alt="ERS composite" loading="lazy" />
        </div>
      ) : null}

      {error ? (
        <p className="spatial-map__hint spatial-map__hint--error" data-testid="spin-error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
