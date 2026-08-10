const DEFAULT_MINIMAX_H3_TERRITORY = "CA";

function normalizeTerritory(value: string | null | undefined): string {
  return String(value || "")
    .trim()
    .toUpperCase();
}

/**
 * Resolve the territory used for H3 capability and preflight checks.
 *
 * The current H3 clearance work is audited for Canadian local development.
 * Production deployments should override this with an explicit runtime
 * territory instead of inheriting the development default.
 */
export function resolveMiniMaxH3Territory(explicitTerritory?: string | null): string {
  const explicit = normalizeTerritory(explicitTerritory);
  if (explicit) return explicit;

  const configured = normalizeTerritory(import.meta.env.VITE_MINIMAX_H3_TERRITORY);
  if (configured) return configured;

  return DEFAULT_MINIMAX_H3_TERRITORY;
}
