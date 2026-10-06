/**
 * MiniMax H3 prewarm trigger — fire-and-forget hook for generator selection.
 *
 * Owner law (2026-09-07): prewarm starts ONLY on an explicit MiniMax H3 selection
 * (never on page open), is cancelled when the creator switches to a different
 * generator, and is admission-gated server-side (no GPU contention, no eviction
 * of active workloads). Deduped: repeated H3 selections do not re-fire.
 */
import { api } from "../../api";
import { canonicalGeneratorId } from "../../timelineMaster/draftCapabilities";

let lastPrewarmedId: string | null = null;

/** Call on every generator-selection change with the newly selected id. */
export function h3PrewarmOnGeneratorSelect(generatorId: string | null | undefined): void {
  const canonical = canonicalGeneratorId(generatorId);
  if (canonical === "minimax-h3") {
    if (lastPrewarmedId === "minimax-h3") return; // already requested
    lastPrewarmedId = "minimax-h3";
    void api.minimaxH3.prewarm().catch(() => undefined); // opportunistic — never block UI
    return;
  }
  if (lastPrewarmedId) {
    lastPrewarmedId = null;
    void api.minimaxH3.prewarmCancel().catch(() => undefined);
  }
}

/** Test hook — reset dedupe state. */
export function __resetH3PrewarmForTests(): void {
  lastPrewarmedId = null;
}
