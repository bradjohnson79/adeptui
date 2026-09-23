import { useEffect, useState } from "react";
import { api } from "../../api";
import type { EngineName } from "../../types";
import { useTimelineVideoGenerators } from "../../timelineMaster/useTimelineVideoGenerators";
import { canonicalGeneratorId } from "../../timelineMaster/draftCapabilities";
import { h3PrewarmOnGeneratorSelect } from "../minimax-h3/prewarmTrigger";
import {
  currentWorkspaceSurface,
  decideEngineOnSurface,
  surfaceWorkflowKey,
  T2V_ENGINE_NAMES,
  type GeneratorSurface,
} from "./engineSurfacePolicy";

/** Persisted scene/project engine tokens → product ids used by the join. */
export const ENGINE_NAME_TO_PRODUCT: Record<EngineName, string> = {
  auto: "",
  "minimax-h3": "minimax-h3",
  "ltx-2.5": "ltx-2.5-distilled",
  "seedance-2.0": "seedance-2.0",
  "seedance-2.5": "seedance-2.5",
  fal_seedance: "seedance-2.0",
  fal_kling: "kling-fal",
  fal_veo: "veo-fal",
  fal_runway: "runway",
};

const ENGINE_LABELS: Record<EngineName, string> = {
  auto: "Auto Select",
  "minimax-h3": "MiniMax H3",
  "ltx-2.5": "LTX 2.5",
  "seedance-2.0": "Seedance 2.0",
  "seedance-2.5": "Seedance 2.5",
  fal_seedance: "Seedance 2.0",
  fal_kling: "Kling",
  fal_veo: "Veo",
  fal_runway: "Runway",
};

/** CREATE defaults. Retired locals and generic Seedance are not listed. */
const CREATE_DEFAULT_ENGINES: EngineName[] = [
  "auto",
  "minimax-h3",
  "ltx-2.5",
  "seedance-2.0",
  "seedance-2.5",
  "fal_kling",
  "fal_veo",
  "fal_runway",
];

const LEGACY_ONLY_ENGINES: EngineName[] = ["fal_seedance"];

function matchProduct(productId: string, optionId: string, aliases: string[]) {
  if (!productId) return false;
  const canonical = canonicalGeneratorId(productId);
  return (
    optionId === productId ||
    optionId === canonical ||
    aliases.includes(productId) ||
    aliases.includes(canonical) ||
    canonicalGeneratorId(optionId) === canonical
  );
}

export function EngineAuthoritySelect({
  value,
  onChange,
  id,
  includeAuto = true,
  requireTextToVideo = false,
  surface,
}: {
  value: string;
  onChange: (next: EngineName) => void;
  id?: string;
  includeAuto?: boolean;
  /** When true, treat this picker as the Text to Video surface. */
  requireTextToVideo?: boolean;
  surface?: GeneratorSurface;
}) {
  const options = useTimelineVideoGenerators();
  const [joinIds, setJoinIds] = useState<EngineName[]>(CREATE_DEFAULT_ENGINES);
  const [serverLabels, setServerLabels] = useState<Record<string, string>>({});
  useEffect(() => {
    let cancelled = false;
    void api
      .listEngines()
      .then((rows) => {
        if (cancelled) return;
        // The served registry is authoritative for membership + order. Ids this
        // build knows render through the existing maps; newly approved registry
        // engines are appended with their server label so they appear without a
        // frontend redeploy. CREATE_DEFAULT_ENGINES remains the offline fallback.
        const known = rows
          .map((row) => row.id)
          .filter((id): id is EngineName => (CREATE_DEFAULT_ENGINES as string[]).includes(id));
        const unknown = rows
          .map((row) => row.id)
          .filter((id) => !(CREATE_DEFAULT_ENGINES as string[]).includes(id));
        const next = [...known, ...unknown] as EngineName[];
        if (next.length) {
          setJoinIds(next);
          setServerLabels(Object.fromEntries(rows.map((row) => [row.id, row.label])));
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);
  const resolvedSurface: GeneratorSurface = requireTextToVideo
    ? "text-to-video"
    : surface || currentWorkspaceSurface();
  const engines: EngineName[] = joinIds.filter((item) => includeAuto || item !== "auto");
  if (
    LEGACY_ONLY_ENGINES.includes(value as EngineName) &&
    !engines.includes(value as EngineName)
  ) {
    engines.push(value as EngineName);
  }

  const showOptimizedIndicator =
    value === "minimax-h3" &&
    (resolvedSurface === "text-to-video" || resolvedSurface === "one-frame");

  return (
    <>
      <select
        id={id}
        value={value}
        onChange={(event) => {
          const next = event.target.value as EngineName;
          h3PrewarmOnGeneratorSelect(next);
          onChange(next);
        }}
      >
        {engines.map((engine) => {
          if (engine === "auto") {
            return (
              <option key={engine} value={engine}>
                {ENGINE_LABELS[engine]}
              </option>
            );
          }
          const productId = ENGINE_NAME_TO_PRODUCT[engine] ?? (engine as string);
          const match = options.find((item) => matchProduct(productId, item.id, item.aliases));
          const workflowCapability = match?.workflowCapabilities?.[surfaceWorkflowKey(resolvedSurface)];
          const decision = decideEngineOnSurface({
            engine,
            surface: resolvedSurface,
            executable: Boolean(match?.executable),
            supportsTextToVideo: Boolean(
              resolvedSurface === "text-to-video"
                ? T2V_ENGINE_NAMES.includes(engine) || match?.supportsTextToVideo
                : match?.supportsTextToVideo,
            ),
            requiresLastFrame: Boolean(match?.requiresLastFrame),
            disabledReason: match?.disabledReason || match?.notes || "",
            workflowCapability,
          });
          if (!decision.visible && engine !== value) {
            return null;
          }
          const label = match?.label || ENGINE_LABELS[engine] || serverLabels[engine] || engine;
          const readiness = match?.readiness || match?.capabilityLabel || "";
          return (
            <option
              key={engine}
              value={engine}
              disabled={decision.disabled}
              title={decision.disabled ? decision.reason : readiness || label}
            >
              {label}
              {decision.disabled
                ? ` — ${decision.reason}`
                : readiness && readiness !== "Ready"
                  ? ` (${readiness})`
                  : ""}
            </option>
          );
        })}
      </select>
      {showOptimizedIndicator ? (
        <div
          className="pill"
          data-testid="minimax-h3-acceleration-optimized"
          title="MiniMax H3 uses an optimized acceleration profile."
          style={{ marginTop: "0.4rem", width: "fit-content" }}
        >
          Acceleration: Optimized
        </div>
      ) : null}
    </>
  );
}
