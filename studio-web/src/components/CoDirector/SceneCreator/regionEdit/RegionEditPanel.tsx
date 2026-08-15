import { useEffect, useMemo, useState } from "react";
import { api } from "../../../../api";
import type { SceneCinematographerPack } from "../cinematographer/cameraCommandEngine";
import type { SceneShot } from "../types";
import { useInpaintSession } from "./inpaintSession";
import {
  EXPAND_PRESETS,
  FEATHER_PRESETS,
  formatInpaintCollapsedSummary,
  formatMaskSummary,
  inferRegionEditStage,
  isMaskStale,
  listRegionEditSources,
  MASK_TOO_SMALL_PERCENT,
  operationRecommendCopy,
  recommendOperationFamily,
  REGION_EDIT_OPERATIONS,
  regionEditCapability,
  type ExpandPreset,
  type FeatherPreset,
  type RegionEditOperation,
} from "./regionEdit";

export type RegionEditRequest = {
  operation: RegionEditOperation;
  prompt: string;
  maskAssetId: string;
  sourceAssetId: string;
  stage: "preview" | "final";
  local_family: string;
  local_enabled: boolean;
  api_enabled: boolean;
  expand?: ExpandPreset;
  feather?: FeatherPreset;
};

export function RegionEditPanel({
  projectId,
  shot,
  cinematographer,
  selectedCameraId,
  localFamily,
  localEnabled,
  busy,
  onGenerate,
  onSwitchFamily,
}: {
  projectId: string;
  shot: SceneShot | null;
  cinematographer?: SceneCinematographerPack | null;
  selectedCameraId?: string;
  localFamily: string;
  localEnabled: boolean;
  busy?: boolean;
  onGenerate: (body: RegionEditRequest) => Promise<void>;
  onSwitchFamily?: (family: string) => void;
}) {
  const session = useInpaintSession();
  const [saving, setSaving] = useState(false);
  const [coreRecommend, setCoreRecommend] = useState<{
    message: string;
    recommendedFamily: string;
    keepCurrentAllowed: boolean;
  } | null>(null);

  const sources = useMemo(
    () => listRegionEditSources({ shot, cinematographer, selectedCameraId }),
    [shot, cinematographer, selectedCameraId],
  );
  const source = sources.find((item) => item.id === session.sourceId) || sources[0] || null;
  const caps = regionEditCapability(localFamily);
  const unsupported = caps.label === "Unsupported";
  const stale = isMaskStale({
    maskSourceAssetId: session.maskSourceAssetId,
    currentSourceAssetId: source?.assetId || "",
    maskCameraVersion: session.maskCameraVersion,
    currentCameraVersion: source?.cameraStateVersion ?? null,
  });
  const coverage = session.hasMask ? session.coverage || session.maskRef.current?.measureCoverage() || 0 : 0;
  const tooSmall = session.hasMask && coverage < MASK_TOO_SMALL_PERCENT;
  const collapsed = formatInpaintCollapsedSummary(shot, session.hasMask);

  useEffect(() => {
    if (!sources.length) return;
    if (!session.sourceId || !sources.some((item) => item.id === session.sourceId)) {
      session.setSourceId(sources[0].id);
    }
  }, [sources, session.sourceId, session.setSourceId]);

  useEffect(() => {
    let cancelled = false;
    api
      .imageCoreRecommend(session.operation, localFamily)
      .then((row) => {
        if (!cancelled) {
          setCoreRecommend({
            message: row.message || "",
            recommendedFamily: row.recommendedFamily || "",
            keepCurrentAllowed: row.keepCurrentAllowed !== false,
          });
        }
      })
      .catch(() => {
        if (!cancelled) setCoreRecommend(null);
      });
    return () => {
      cancelled = true;
    };
  }, [session.operation, localFamily]);

  const fallbackRec = recommendOperationFamily(session.operation);
  const recommendCopy = coreRecommend?.message || operationRecommendCopy(session.operation, localFamily);
  const recFamily = coreRecommend?.recommendedFamily || fallbackRec.family;
  const recLabel = recFamily === "flux" ? "FLUX" : recFamily === "zimage" ? "Z-Image" : fallbackRec.label;

  const generate = async () => {
    if (!source?.assetId || unsupported || !session.hasMask) return;
    const liveCoverage = session.maskRef.current?.measureCoverage() || coverage;
    session.setCoverage(liveCoverage);
    if (liveCoverage < MASK_TOO_SMALL_PERCENT) return;
    const png = (await session.maskRef.current?.exportPng()) || "";
    if (!png) return;
    setSaving(true);
    try {
      const saved = await api.imageProduct.saveMask(projectId, {
        sourceAssetId: source.assetId,
        pngBase64: png,
        role: session.operation === "replace" ? "replace" : "include",
      });
      const parent = shot?.candidates.find((c) => c.id === source.parentCandidateId);
      await onGenerate({
        operation: session.operation,
        prompt: session.prompt,
        maskAssetId: saved.maskId,
        sourceAssetId: source.assetId,
        stage: inferRegionEditStage(
          { sourceAssetId: source.assetId, fromPreview: source.fromPreview, parentCandidateId: source.parentCandidateId },
          parent,
        ),
        local_family: localFamily,
        local_enabled: localEnabled,
        api_enabled: false,
        expand: session.expand,
        feather: session.feather,
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <details
      className="scene-creator-tool-accordion scene-creator-inpaint"
      data-testid="scene-creator-inpaint-accordion"
      onToggle={(event) => session.setAccordionOpen(event.currentTarget.open)}
    >
      <summary>
        Inpaint / Region Edit
        {collapsed ? (
          <span className="muted cine-orient-collapsed-meta" data-testid="scene-creator-inpaint-collapsed-line">
            {collapsed}
          </span>
        ) : null}
      </summary>
      <div className="scene-creator-inpaint__body">
        <p className="muted" data-testid="scene-creator-inpaint-capability">
          {caps.label}
          {caps.label === "Native Inpaint"
            ? " — paint the area to change on the main image."
            : caps.label === "Image Edit"
              ? " — this generator can edit the image, but it is not Native Inpaint."
              : " — this generator cannot edit a region. Choose Z-Image for Native Inpaint."}
        </p>
        {!source?.assetId ? (
          <p className="muted">Generate a look first, then paint the region on the main image.</p>
        ) : (
          <label className="scene-creator-core__label">
            Source
            <select
              data-testid="scene-creator-inpaint-source"
              value={source.id}
              onChange={(e) => session.setSourceId(e.target.value)}
            >
              {sources.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
        )}
        <div className="scene-creator-core__row">
          <span className="scene-creator-core__label">Tool</span>
          <button
            type="button"
            className={session.tool === "brush" ? "primary" : "ghost"}
            data-testid="scene-creator-inpaint-brush"
            onClick={() => session.setTool("brush")}
          >
            Brush
          </button>
          <button
            type="button"
            className={session.tool === "erase" ? "primary" : "ghost"}
            data-testid="scene-creator-inpaint-erase"
            onClick={() => session.setTool("erase")}
          >
            Erase
          </button>
          <button type="button" disabled data-testid="scene-creator-inpaint-smart-select">
            Smart Select (Not available)
          </button>
        </div>
        <label className="scene-creator-core__label">
          Brush Size
          <input
            type="range"
            min={4}
            max={96}
            data-testid="scene-creator-inpaint-brush-size"
            value={session.brushSize}
            onChange={(e) => session.setBrushSize(Number(e.target.value))}
          />
        </label>
        <label className="scene-creator-core__label">
          Operation
          <select
            data-testid="scene-creator-inpaint-operation"
            value={session.operation}
            onChange={(e) => session.setOperation(e.target.value as RegionEditOperation)}
          >
            {REGION_EDIT_OPERATIONS.map((op) => (
              <option key={op.id} value={op.id}>
                {op.label}
              </option>
            ))}
          </select>
        </label>
        {recommendCopy ? (
          <div className="scene-creator-model-guard" data-testid="scene-creator-operation-recommend">
            <p>{recommendCopy}</p>
            <div className="scene-creator-core__row">
              <button
                type="button"
                className="primary"
                data-testid="scene-creator-use-recommended-family"
                onClick={() => onSwitchFamily?.(recFamily)}
              >
                Use {recLabel}
              </button>
              <button type="button" className="ghost" data-testid="scene-creator-keep-current-family">
                Keep Current Model
              </button>
            </div>
          </div>
        ) : null}
        <div className="scene-creator-core__row">
          <span className="scene-creator-core__label">Expand</span>
          {EXPAND_PRESETS.map((preset) => (
            <button
              key={preset.id}
              type="button"
              className={session.expand === preset.id ? "primary" : "ghost"}
              data-testid={`scene-creator-inpaint-expand-${preset.id}`}
              onClick={() => session.setExpand(preset.id)}
            >
              {preset.label}
            </button>
          ))}
        </div>
        <div className="scene-creator-core__row">
          <span className="scene-creator-core__label">Edge</span>
          {FEATHER_PRESETS.map((preset) => (
            <button
              key={preset.id}
              type="button"
              className={session.feather === preset.id ? "primary" : "ghost"}
              data-testid={`scene-creator-inpaint-feather-${preset.id}`}
              onClick={() => session.setFeather(preset.id)}
            >
              {preset.label}
            </button>
          ))}
        </div>
        <label className="scene-creator-core__label">
          Prompt
          <textarea
            className="scene-creator-core__prompt"
            data-testid="scene-creator-inpaint-prompt"
            value={session.prompt}
            onChange={(e) => session.setPrompt(e.target.value)}
            placeholder="Remove the background extra behind Korri."
          />
        </label>
        {session.hasMask ? (
          <p
            className={tooSmall ? "scene-creator-inpaint-warning" : "muted"}
            data-testid="scene-creator-inpaint-mask-summary"
          >
            {formatMaskSummary({
              coverage,
              sourceLabel: source?.label || "Preview",
              operation: session.operation,
              tooSmall,
            })}
          </p>
        ) : null}
        {stale ? (
          <p className="muted" data-testid="scene-creator-inpaint-mask-stale">
            This mask was painted on an older camera look. Paint again on the current frame.
          </p>
        ) : null}
        <button
          type="button"
          className="ghost"
          data-testid="scene-creator-inpaint-clear"
          disabled={!session.hasMask}
          onClick={() => {
            session.maskRef.current?.clear();
            session.setHasMask(false);
            session.setCoverage(0);
          }}
        >
          Clear Mask
        </button>
        <button
          type="button"
          className="primary"
          data-testid="scene-creator-inpaint-generate"
          disabled={
            unsupported ||
            !source?.assetId ||
            !session.hasMask ||
            tooSmall ||
            stale ||
            !session.prompt.trim() ||
            busy ||
            saving ||
            !localEnabled
          }
          onClick={() => void generate()}
        >
          Generate Inpaint
        </button>
      </div>
    </details>
  );
}
