import {
  VIDEO_TIERS,
  legalCanvasSize,
  isMinimaxMegapixelEngine,
  minimaxMegapixelOptions,
} from "../../video/legalCanvas";

export function VideoResolutionSelect({
  id,
  engine,
  aspect,
  value,
  onChange,
}: {
  id: string;
  engine: string;
  aspect?: string;
  // `string` (not the narrow `VideoTier`) so the MiniMax megapixel labels
  // ("0.9 MP", …) can flow through the same control without widening every
  // consumer. Non-MiniMax engines still only ever receive a `VideoTier`.
  value: string;
  onChange: (tier: string, width: number, height: number) => void;
}) {
  const minimax = isMinimaxMegapixelEngine(engine);
  const options = minimax ? minimaxMegapixelOptions(aspect || "16:9") : null;
  return (
    <select
      id={id}
      data-testid={id}
      value={value}
      onChange={(event) => {
        const tier = event.target.value;
        const canvas = legalCanvasSize(engine, tier, aspect || "16:9");
        onChange(tier, canvas.width, canvas.height);
      }}
    >
      {minimax
        ? options!.map((opt) => (
            <option key={opt.label} value={opt.label} disabled={!opt.available}>
              {opt.available
                ? `${opt.label} (${opt.width}×${opt.height})`
                : `${opt.label} — not available`}
            </option>
          ))
        : VIDEO_TIERS.map((tier) => {
            const canvas = legalCanvasSize(engine, tier, aspect || "16:9");
            return (
              <option key={tier} value={tier} disabled={!canvas.available}>
                {canvas.available
                  ? `${tier} (${canvas.width}×${canvas.height}) · ${canvas.honestyLabel}`
                  : `${tier} — not available`}
              </option>
            );
          })}
    </select>
  );
}
