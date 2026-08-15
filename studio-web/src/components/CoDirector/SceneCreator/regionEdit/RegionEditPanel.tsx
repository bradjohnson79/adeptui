import { useEffect, useMemo, useState } from "react";
import { api } from "../../../../api";
import type { SceneCinematographerPack } from "../cinematographer/cameraCommandEngine";
import type { SceneShot } from "../types";
import { useInpaintSession } from "./inpaintSession";
import {
  formatInpaintCollapsedSummary,
  inferRegionEditStage,
  isMaskStale,
  listRegionEditSources,
  REGION_EDIT_OPERATIONS,
  regionEditCapability,
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
}: {
  projectId: string;
  shot: SceneShot | null;
  cinematographer?: SceneCinematographerPack | null;
  selectedCameraId?: string;
  localFamily: string;
  localEnabled: boolean;
  busy?: boolean;
  onGenerate: (body: RegionEditRequest) => Promise<void>;
}) {
  const session = useInpaintSession();
  const [saving, setSaving] = useState(false);

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
  const collapsed = formatInpaintCollapsedSummary(shot, session.hasMask);

  useEffect(() => {
    if (!sources.length) return;
    if (!session.sourceId || !sources.some((item) => item.id === session.sourceId)) {
      session.setSourceId(sources[0].id);
    }
  }, [sources, session.sourceId, session.setSourceId]);

  const generate = async () => {
    if (!source?.assetId || unsupported || !session.hasMask) return;
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
