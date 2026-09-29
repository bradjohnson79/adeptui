import { HelpTip } from "../HelpTip";
import {
  generatorQualityControl,
  resolveNativeAudioState,
  type TimelineGeneratorOption,
} from "../../timelineMaster/draftCapabilities";
import {
  formatH3Megapixels,
  H3_AUTO_MEGAPIXEL_FAST,
  H3_AUTO_MEGAPIXEL_QUALITY,
  H3_MEGAPIXEL_GRID,
  H3_SUPPORTED_ASPECTS,
  LTX_DEFAULT_QUALITY,
  LTX_TIMELINE_QUALITY_TIERS,
  normalizeH3Aspect,
  normalizeLtxTimelineQuality,
  resolveH3MegapixelCanvas,
  resolveH3TimelineCanvas,
  resolveLtxTimelineCanvas,
  type LtxTimelineQuality,
} from "../../timelineMaster/legalCanvas";

type H3Resolution = { mode?: "auto" | "manual"; megapixels?: number } | null | undefined;

export function GeneratorQualityControls({
  option,
  h3Resolution,
  ltxQuality,
  draftMode,
  megapixelsTestId,
  megapixelsSelectTestId,
  megapixelsAutoTestId,
  qualityTestId,
  qualitySelectTestId,
  megapixelsLabel,
  megapixelsTip,
  qualityLabel,
  qualityTip,
  seedanceResolution,
  onH3Change,
  onLtxChange,
  onSeedanceChange,
  aspectRatio,
}: {
  option: TimelineGeneratorOption | null | undefined;
  h3Resolution: H3Resolution;
  ltxQuality: string | null | undefined;
  seedanceResolution: string | null | undefined;
  draftMode: boolean;
  megapixelsTestId: string;
  megapixelsSelectTestId: string;
  megapixelsAutoTestId: string;
  qualityTestId: string;
  qualitySelectTestId: string;
  megapixelsLabel: string;
  megapixelsTip: string;
  qualityLabel: string;
  qualityTip: string;
  onH3Change: (next: { mode: "auto" | "manual"; megapixels: number }) => void;
  onLtxChange: (tier: LtxTimelineQuality) => void;
  onSeedanceChange: (resolution: string) => void;
  aspectRatio?: string | null;
}) {
  const kind = generatorQualityControl(option);
  if (kind === "h3_megapixels") {
    // B5: MiniMax H3 has no dims for a picture shape outside its capability set
    // (backend require_h3_timeline_aspect → H3_ASPECT_UNSUPPORTED). Fail closed
    // with an explicit notice instead of resolving 16:9 dims the backend refuses.
    const h3Aspect = normalizeH3Aspect(aspectRatio);
    if (!h3Aspect) {
      return (
        <label className="field" data-testid={megapixelsTestId}>
          <span>
            {megapixelsLabel}
            <HelpTip text={megapixelsTip} />
          </span>
          <select data-testid={megapixelsSelectTestId} value="" disabled>
            <option value="">Unavailable</option>
          </select>
          <p className="scene-meta" role="alert" data-testid={megapixelsAutoTestId}>
            {String(aspectRatio || "").trim()} is not a MiniMax H3 picture shape. Available:{" "}
            {H3_SUPPORTED_ASPECTS.join(", ")}.
          </p>
        </label>
      );
    }
    return (
      <label className="field" data-testid={megapixelsTestId}>
        <span>
          {megapixelsLabel}
          <HelpTip text={megapixelsTip} />
        </span>
        <select
          data-testid={megapixelsSelectTestId}
          value={h3Resolution?.mode === "manual" ? String(h3Resolution.megapixels) : ""}
          onChange={(event) => {
            const value = event.target.value;
            if (value === "") {
              onH3Change({
                mode: "auto",
                megapixels: draftMode ? H3_AUTO_MEGAPIXEL_FAST : H3_AUTO_MEGAPIXEL_QUALITY,
              });
              return;
            }
            onH3Change({ mode: "manual", megapixels: Number(value) });
          }}
        >
          <option value="">Auto</option>
          {H3_MEGAPIXEL_GRID.map(([mp]) => {
            const canvas = resolveH3MegapixelCanvas(mp, h3Aspect);
            return (
              <option key={mp} value={String(mp)}>
                {formatH3Megapixels(mp)} · {canvas.width}×{canvas.height}
              </option>
            );
          })}
        </select>
        {h3Resolution?.mode !== "manual" ? (
          (() => {
            const canvas = resolveH3TimelineCanvas(
              h3Resolution
                ? {
                    mode: h3Resolution.mode ?? "auto",
                    megapixels: h3Resolution.megapixels ?? H3_AUTO_MEGAPIXEL_QUALITY,
                  }
                : null,
              draftMode,
              h3Aspect,
            );
            return (
              <p className="scene-meta" data-testid={megapixelsAutoTestId}>
                Auto · {canvas.width}×{canvas.height} ({draftMode ? "Fast" : "Quality"})
              </p>
            );
          })()
        ) : null}
      </label>
    );
  }
  if (kind === "ltx_quality") {
    return (
      <label className="field" data-testid={qualityTestId}>
        <span>
          {qualityLabel}
          <HelpTip text={qualityTip} />
        </span>
        <select
          data-testid={qualitySelectTestId}
          value={normalizeLtxTimelineQuality(ltxQuality || LTX_DEFAULT_QUALITY)}
          onChange={(event) => {
            const tier = normalizeLtxTimelineQuality(event.target.value) as LtxTimelineQuality;
            if (!resolveLtxTimelineCanvas(tier, aspectRatio).available) return;
            onLtxChange(tier);
          }}
        >
          {LTX_TIMELINE_QUALITY_TIERS.map((tier) => {
            const canvas = resolveLtxTimelineCanvas(tier, aspectRatio);
            return (
              <option key={tier} value={tier} disabled={!canvas.available}>
                {canvas.available
                  ? `${tier} — ${canvas.width} × ${canvas.height}`
                  : `${tier} — UNAVAILABLE`}
              </option>
            );
          })}
        </select>
      </label>
    );
  }
  if (kind === "seedance_resolution") {
    const ladder = ["480p", "720p", "1080p", "4k"];
    const offered = new Set(
      (option?.supportedResolutions?.length ? option.supportedResolutions : ladder).map((token) =>
        token.toLowerCase(),
      ),
    );
    const current = String(seedanceResolution || "720p").toLowerCase() === "2160p"
      ? "4k"
      : String(seedanceResolution || "720p").toLowerCase();
    const labelFor = (token: string) => (token === "4k" ? "4K" : token);
    return (
      <label className="field" data-testid={qualityTestId}>
        <span>
          {qualityLabel}
          <HelpTip text="How sharp this Seedance clip is. 720p is the usual choice. Higher settings take longer and cost more. Grey sizes are not available on the engine you have selected." />
        </span>
        <select
          data-testid={qualitySelectTestId}
          value={offered.has(current) ? current : "720p"}
          onChange={(event) => onSeedanceChange(event.target.value)}
        >
          {ladder.map((token) => (
            <option key={token} value={token} disabled={!offered.has(token)}>
              {offered.has(token) ? labelFor(token) : `${labelFor(token)} — not on this engine`}
            </option>
          ))}
        </select>
      </label>
    );
  }
  return null;
}

export function NativeAudioCapability({
  option,
  loadState,
  hasTimelineAudio,
}: {
  option: TimelineGeneratorOption | null | undefined;
  loadState: "loading" | "ready" | "error";
  hasTimelineAudio?: boolean;
}) {
  const state = resolveNativeAudioState(option, loadState);
  return (
    <div className="field" data-testid="timeline-native-audio">
      <span>Native Audio</span>
      <span className="scene-meta" data-testid="timeline-native-audio-status">
        {state.label}
      </span>
      <p className="scene-meta" data-testid="timeline-native-audio-detail">
        {state.detail}
      </p>
      {hasTimelineAudio ? (
        <p className="scene-meta" data-testid="timeline-native-audio-timeline-tracks">
          This scene also has Timeline audio tracks. Those stay separate from generator-native audio.
        </p>
      ) : null}
    </div>
  );
}
