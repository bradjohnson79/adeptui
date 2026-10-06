/**
 * Advanced · Look — appearance only. Does not move walls or doors.
 */
import {
  DETAIL_OPTIONS,
  LIGHTING_OPTIONS,
  PRESENTATION_OPTIONS,
  STRENGTH_OPTIONS,
  STYLE_OPTIONS,
  type SpatialAtlasLook,
} from "./atlasLook";

type Props = {
  look: SpatialAtlasLook;
  onChange: (next: SpatialAtlasLook) => void;
  mode?: "express" | "standard";
  disabled?: boolean;
  unsupported?: string[];
};

export function AtlasLookControls({
  look,
  onChange,
  mode = "standard",
  disabled = false,
  unsupported = [],
}: Props) {
  const hide = (key: string) => unsupported.includes(key);
  const set = <K extends keyof SpatialAtlasLook>(key: K, value: SpatialAtlasLook[K]) => {
    onChange({ ...look, [key]: value });
  };

  return (
    <div className="spatial-map__atlas-look" data-testid="atlas-look-controls">
      <p className="spatial-map__atlas-look-hint">
        Changes how the Atlas looks. The room layout stays the same.
      </p>
      {!hide("style") ? (
        <label className="spatial-map__atlas-look-field">
          <span>
            Atlas Style
            <span className="spatial-map__scene-desc-tip" title="The visual style of the top-down map. Auto matches the location photo.">
              (?)
            </span>
          </span>
          <select
            data-testid="atlas-look-style"
            aria-label="Atlas Style"
            value={look.style}
            disabled={disabled}
            onChange={(e) => set("style", e.target.value as SpatialAtlasLook["style"])}
          >
            {STYLE_OPTIONS.map((opt) => (
              <option key={opt.id} value={opt.id}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      {!hide("detail") ? (
        <label className="spatial-map__atlas-look-field">
          <span>
            Detail Level
            <span className="spatial-map__scene-desc-tip" title="How much surface decoration to draw. Does not add rooms.">
              (?)
            </span>
          </span>
          <select
            data-testid="atlas-look-detail"
            aria-label="Detail Level"
            value={look.detail}
            disabled={disabled}
            onChange={(e) => set("detail", e.target.value as SpatialAtlasLook["detail"])}
          >
            {DETAIL_OPTIONS.map((opt) => (
              <option key={opt.id} value={opt.id}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      {!hide("sourceAppearance") ? (
        <label className="spatial-map__atlas-look-field">
          <span>
            Source Appearance
            <span className="spatial-map__scene-desc-tip" title="How strongly the Atlas borrows colors and materials from your location photo. It will not copy the camera angle.">
              (?)
            </span>
          </span>
          <input
            type="range"
            min={0}
            max={2}
            step={1}
            data-testid="atlas-look-source"
            aria-label="Source Appearance"
            disabled={disabled}
            value={look.sourceAppearance === "low" ? 0 : look.sourceAppearance === "strong" ? 2 : 1}
            onChange={(e) =>
              set("sourceAppearance", (["low", "balanced", "strong"] as const)[Number(e.target.value)])
            }
          />
          <span className="spatial-map__atlas-look-range" data-testid="atlas-look-source-label">
            {STRENGTH_OPTIONS.find((opt) => opt.id === look.sourceAppearance)?.label}
          </span>
        </label>
      ) : null}
      {mode === "standard" && !hide("presentation") ? (
        <label className="spatial-map__atlas-look-field">
          <span>
            Atlas Presentation
            <span className="spatial-map__scene-desc-tip" title="Roofless is the usual Spatial Map view.">
              (?)
            </span>
          </span>
          <select
            data-testid="atlas-look-presentation"
            aria-label="Atlas Presentation"
            value={look.presentation}
            disabled={disabled}
            onChange={(e) => set("presentation", e.target.value as SpatialAtlasLook["presentation"])}
          >
            {PRESENTATION_OPTIONS.map((opt) => (
              <option key={opt.id} value={opt.id}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      {mode === "standard" && !hide("lighting") ? (
        <label className="spatial-map__atlas-look-field">
          <span>
            Lighting
            <span className="spatial-map__scene-desc-tip" title="Lighting for readability. Bright Planning keeps walls and doors easy to see.">
              (?)
            </span>
          </span>
          <select
            data-testid="atlas-look-lighting"
            aria-label="Lighting"
            value={look.lighting}
            disabled={disabled}
            onChange={(e) => set("lighting", e.target.value as SpatialAtlasLook["lighting"])}
          >
            {LIGHTING_OPTIONS.map((opt) => (
              <option key={opt.id} value={opt.id}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      {mode === "standard" && !hide("showGrid") ? (
        <label className="spatial-map__atlas-look-check">
          <input
            type="checkbox"
            data-testid="atlas-look-grid"
            aria-label="Show 1 m Grid"
            checked={look.showGrid}
            disabled={disabled}
            onChange={(e) => set("showGrid", e.target.checked)}
          />
          <span>
            Show 1 m Grid
            <span className="spatial-map__scene-desc-tip" title="Draws a real 1-meter grid on a finished top-down Atlas. It will not put a grid on an eye-level photo.">
              (?)
            </span>
          </span>
        </label>
      ) : null}
    </div>
  );
}
