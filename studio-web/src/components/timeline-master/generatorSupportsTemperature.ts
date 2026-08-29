/**
 * Timed Prompt `temperature` capability read.
 *
 * Reads the live catalog / picker object's `supportsTemperature` boolean
 * when present (W46 GeneratorCapability + adapter VideoGeneratorCapabilities,
 * served on director-timeline/generators `timelineAdapters`).
 *
 * Fail closed: missing / undefined / unknown = unavailable.
 * MiniMax H3 is known-unsupported and stays false even if the catalog
 * omits the flag.
 *
 * Do not infer support from historical `weight`. Temperature is a new field.
 * Do not invent a frontend true.
 */
const KNOWN_UNSUPPORTED_TOKENS = ["minimax-h3"];

export type TemperatureCapability = {
  supportsTemperature?: boolean;
};

export function generatorSupportsTemperature(
  generatorId?: string | null,
  capability?: TemperatureCapability | Record<string, unknown> | null,
): boolean {
  const id = String(generatorId || "").trim().toLowerCase();
  if (KNOWN_UNSUPPORTED_TOKENS.some((token) => id === token || id.includes(token))) return false;

  const rawFlag = capability && "supportsTemperature" in capability ? capability.supportsTemperature : undefined;
  if (typeof rawFlag === "boolean") return rawFlag;
  return false;
}
