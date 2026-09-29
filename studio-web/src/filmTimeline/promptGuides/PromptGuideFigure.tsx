import type { PromptPreset } from "./types";

/** One shared room and figure. Lens, crop, and palette change the drawing. No network images. */
export function PromptGuideFigure({ lens, shot, light }: { lens?: PromptPreset | null; shot?: PromptPreset | null; light?: PromptPreset | null }) {
  const fov = lens?.fov ?? 50;
  const crop = shot?.crop ?? 0.62;
  const [sky, fill, shadow] = light?.palette || ["#cbd5e1", "#f8fafc", "#334155"];
  const room = 18 + (114 - Math.min(114, Math.max(12, fov))) * 0.35;
  const figure = 10 + crop * 28;
  const head = 4 + crop * 6;
  return (
    <svg className="prompt-guide__figure" viewBox="0 0 160 100" role="img" aria-hidden="true">
      <rect width="160" height="100" fill={shadow} />
      <polygon points={`${20 - room / 4},78 ${80},18 ${140 + room / 4},78`} fill={sky} opacity="0.85" />
      <rect x={58 - room / 5} y="28" width={18 + room / 6} height="22" fill={fill} opacity="0.55" />
      <rect x="70" y={78 - figure} width="8" height={figure} rx="2" fill={fill} />
      <circle cx="74" cy={78 - figure - head / 2} r={head / 2} fill={fill} />
      <rect x={80 - 46 * crop} y={50 - 28 * crop} width={92 * crop} height={56 * crop} fill="none" stroke="#f8fafc" strokeOpacity="0.85" />
    </svg>
  );
}
