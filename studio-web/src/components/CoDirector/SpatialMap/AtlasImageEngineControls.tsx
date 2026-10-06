/**
 * Option 1 Atlas image engine + Advanced · Look.
 * Look controls appearance only. Geometry stays with the reconstruction compiler.
 */
import {
  ERS_GENERATOR_OPTIONS,
  ersGeneratorOptionDisabled,
  generatorBlockReason,
  type ErsGeneratorId,
} from "./ersGenerator";
import { AtlasLookControls } from "./AtlasLookControls";
import type { SpatialAtlasLook } from "./atlasLook";

type Props = {
  selectedGenerator: ErsGeneratorId;
  onSelectGenerator: (id: ErsGeneratorId) => void;
  qwenReady: boolean | null;
  qwenI2IReady: boolean | null;
  gptReady: boolean | null;
  gptI2IReady: boolean | null;
  look: SpatialAtlasLook;
  onLookChange: (next: SpatialAtlasLook) => void;
  lookMode?: "express" | "standard";
  disabled?: boolean;
};

export function AtlasImageEngineControls({
  selectedGenerator,
  onSelectGenerator,
  qwenReady,
  qwenI2IReady,
  gptReady,
  gptI2IReady,
  look,
  onLookChange,
  lookMode = "standard",
  disabled = false,
}: Props) {
  const blockReason = generatorBlockReason(
    selectedGenerator,
    qwenReady,
    gptReady,
    qwenI2IReady,
    gptI2IReady,
  );
  const unsupported = selectedGenerator === "gpt-image-2" ? ["sourceAppearance", "showGrid"] : [];

  return (
    <div className="spatial-map__atlas-engine" data-testid="atlas-image-engine">
      <label className="spatial-map__ers-generator-label" htmlFor="atlas-image-engine-select">
        Image Engine
        <span
          className="spatial-map__scene-desc-tip"
          title="Choose the local accelerator or API engine that turns your location photo into the top-down Spatial Map."
        >
          (?)
        </span>
      </label>
      <select
        id="atlas-image-engine-select"
        className="spatial-map__ers-generator-select"
        data-testid="atlas-image-engine-select"
        aria-label="Image Engine"
        value={selectedGenerator}
        disabled={disabled}
        onChange={(e) => onSelectGenerator(e.target.value as ErsGeneratorId)}
      >
        {ERS_GENERATOR_OPTIONS.map((opt) => {
          const optionDisabled = ersGeneratorOptionDisabled(opt.id, qwenI2IReady, gptI2IReady);
          return (
            <option key={opt.id} value={opt.id} disabled={optionDisabled}>
              {optionDisabled ? `${opt.label} (not ready)` : opt.label}
            </option>
          );
        })}
      </select>
      {blockReason ? (
        <p className="spatial-map__ers-generator-hint" data-testid="atlas-image-engine-reason" role="status">
          {blockReason}
        </p>
      ) : (
        <p className="spatial-map__ers-generator-hint">
          Local engines run on this computer. API engines use your connected image service.
        </p>
      )}
      <details className="spatial-map__atlas-engine-advanced" data-testid="atlas-image-engine-advanced">
        <summary>Advanced · Look</summary>
        <AtlasLookControls
          look={look}
          onChange={onLookChange}
          mode={lookMode}
          disabled={disabled}
          unsupported={unsupported}
        />
      </details>
    </div>
  );
}
